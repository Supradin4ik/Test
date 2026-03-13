from __future__ import annotations

import math
import sqlite3
from collections import defaultdict


STATUS_LABELS = {
    "done": "Готово",
    "in_progress": "В работе",
    "pending": "Ожидание",
    "blocked": "Нет металла",
}


def _build_batches(quantity_plan: int, stage_size: int) -> list[int]:
    if quantity_plan <= 0 or stage_size <= 0:
        return []

    batches: list[int] = []
    remaining = quantity_plan
    while remaining > 0:
        current = stage_size if remaining >= stage_size else remaining
        batches.append(current)
        remaining -= current
    return batches


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_types_done_manual_column(connection: sqlite3.Connection) -> None:
    if "done_manual" in _columns(connection, "types"):
        return
    connection.execute("ALTER TABLE types ADD COLUMN done_manual INTEGER DEFAULT 0")


def recreate_type_plan(
    connection: sqlite3.Connection,
    *,
    type_id: int,
    quantity_plan: int,
    stage_size: int,
) -> dict[str, int]:
    batch_ids = [
        row[0]
        for row in connection.execute(
            "SELECT id FROM type_batches WHERE type_id = ? ORDER BY id", (type_id,)
        ).fetchall()
    ]

    if batch_ids:
        placeholders = ",".join("?" for _ in batch_ids)
        batch_item_ids = [
            row[0]
            for row in connection.execute(
                f"SELECT id FROM batch_items WHERE batch_id IN ({placeholders})",
                batch_ids,
            ).fetchall()
        ]

        if batch_item_ids:
            stage_placeholders = ",".join("?" for _ in batch_item_ids)
            connection.execute(
                f"DELETE FROM batch_item_stages WHERE batch_item_id IN ({stage_placeholders})",
                batch_item_ids,
            )

        connection.execute(
            f"DELETE FROM batch_items WHERE batch_id IN ({placeholders})",
            batch_ids,
        )
        connection.execute("DELETE FROM type_batches WHERE type_id = ?", (type_id,))

    items = connection.execute(
        """
        SELECT id, qty_per_product
        FROM items
        WHERE type_id = ?
        ORDER BY id
        """,
        (type_id,),
    ).fetchall()

    batches = _build_batches(quantity_plan=quantity_plan, stage_size=stage_size)

    created_batch_count = 0
    created_batch_items = 0
    created_batch_stages = 0

    for idx, batch_qty in enumerate(batches, start=1):
        batch_cursor = connection.execute(
            """
            INSERT INTO type_batches (type_id, batch_number, qty_planned, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (type_id, idx, batch_qty),
        )
        batch_id = batch_cursor.lastrowid
        created_batch_count += 1

        for item_id, qty_per_product in items:
            qty_required = (qty_per_product or 0) * batch_qty
            batch_item_cursor = connection.execute(
                """
                INSERT INTO batch_items (batch_id, item_id, qty_required, qty_completed)
                VALUES (?, ?, ?, 0)
                """,
                (batch_id, item_id, qty_required),
            )
            batch_item_id = batch_item_cursor.lastrowid
            created_batch_items += 1

            routes = connection.execute(
                """
                SELECT stage_name
                FROM routes
                WHERE item_id = ?
                ORDER BY order_index, id
                """,
                (item_id,),
            ).fetchall()

            for route in routes:
                connection.execute(
                    """
                    INSERT INTO batch_item_stages (batch_item_id, stage_name, status)
                    VALUES (?, ?, 'pending')
                    """,
                    (batch_item_id, route[0]),
                )
                created_batch_stages += 1

    return {
        "created_batches": created_batch_count,
        "created_batch_items": created_batch_items,
        "created_batch_item_stages": created_batch_stages,
    }


def _material_status(qty_completed: int, qty_required: int, no_metal: bool) -> tuple[str, str]:
    if no_metal:
        return "blocked", STATUS_LABELS["blocked"]
    if qty_completed >= qty_required and qty_required > 0:
        return "done", STATUS_LABELS["done"]
    if qty_completed == 0:
        return "pending", STATUS_LABELS["pending"]
    return "pending", STATUS_LABELS["pending"]


def _stage_status_from_materials(statuses: list[str], fallback_batch_status: str) -> tuple[str, str]:
    if any(status == "blocked" for status in statuses):
        return "blocked", STATUS_LABELS["blocked"]
    if statuses and all(status == "done" for status in statuses):
        return "done", STATUS_LABELS["done"]
    if any(status == "pending" for status in statuses):
        return "pending", STATUS_LABELS["pending"]
    mapped = fallback_batch_status if fallback_batch_status in STATUS_LABELS else "pending"
    return mapped, STATUS_LABELS[mapped]


def get_type_planning_data(connection: sqlite3.Connection, type_id: int) -> dict[str, object]:
    ensure_types_done_manual_column(connection)

    type_row = connection.execute(
        """
        SELECT id, type_name, quantity_plan, stage_size, COALESCE(done_manual, 0) AS done_manual
        FROM types
        WHERE id = ?
        """,
        (type_id,),
    ).fetchone()
    if type_row is None:
        return {}

    batches = connection.execute(
        """
        SELECT id, batch_number, COALESCE(qty_planned, 0) AS qty_planned, COALESCE(status, 'pending') AS status
        FROM type_batches
        WHERE type_id = ?
        ORDER BY batch_number, id
        """,
        (type_id,),
    ).fetchall()
    batch_ids = [row["id"] for row in batches]

    items = connection.execute(
        """
        SELECT id, COALESCE(metal, '-') AS metal, COALESCE(thickness, 0) AS thickness
        FROM items
        WHERE type_id = ?
        ORDER BY id
        """,
        (type_id,),
    ).fetchall()

    material_keys = []
    material_label_by_item: dict[int, str] = {}
    for item in items:
        thickness = int(item["thickness"]) if float(item["thickness"]).is_integer() else item["thickness"]
        label = f"{item['metal']} {thickness}"
        material_label_by_item[item["id"]] = label
        if label not in material_keys:
            material_keys.append(label)

    batch_items: list[sqlite3.Row] = []
    if batch_ids:
        placeholders = ",".join("?" for _ in batch_ids)
        batch_items = connection.execute(
            f"""
            SELECT id, batch_id, item_id, COALESCE(qty_required, 0) AS qty_required, COALESCE(qty_completed, 0) AS qty_completed
            FROM batch_items
            WHERE batch_id IN ({placeholders})
            ORDER BY id
            """,
            batch_ids,
        ).fetchall()

    batch_item_ids = [row["id"] for row in batch_items]

    no_metal_item_blocks: set[int] = set()
    no_metal_batch_blocks: set[int] = set()
    if batch_item_ids:
        item_placeholders = ",".join("?" for _ in batch_item_ids)
        for row in connection.execute(
            f"""
            SELECT object_id
            FROM blocks
            WHERE status = 'active' AND reason = 'no_metal' AND object_type IN ('batch_item', 'batch_items')
              AND object_id IN ({item_placeholders})
            """,
            batch_item_ids,
        ).fetchall():
            no_metal_item_blocks.add(row[0])

    if batch_ids:
        batch_placeholders = ",".join("?" for _ in batch_ids)
        for row in connection.execute(
            f"""
            SELECT object_id
            FROM blocks
            WHERE status = 'active' AND reason = 'no_metal' AND object_type IN ('type_batch', 'batch')
              AND object_id IN ({batch_placeholders})
            """,
            batch_ids,
        ).fetchall():
            no_metal_batch_blocks.add(row[0])

    statuses_by_material_batch: dict[tuple[str, int], list[str]] = defaultdict(list)
    for batch_item in batch_items:
        material_key = material_label_by_item.get(batch_item["item_id"], "- 0")
        is_blocked = batch_item["id"] in no_metal_item_blocks or batch_item["batch_id"] in no_metal_batch_blocks
        status_key, _ = _material_status(batch_item["qty_completed"], batch_item["qty_required"], is_blocked)
        statuses_by_material_batch[(material_key, batch_item["batch_id"])].append(status_key)

    material_rows = []
    for material_key in material_keys:
        cells = []
        for batch in batches:
            status_list = statuses_by_material_batch.get((material_key, batch["id"]), ["pending"])
            if any(status == "blocked" for status in status_list):
                status_key = "blocked"
            elif status_list and all(status == "done" for status in status_list):
                status_key = "done"
            else:
                status_key = "pending"

            cells.append({"batch_id": batch["id"], "status_key": status_key, "status_label": STATUS_LABELS[status_key]})
        material_rows.append({"material": material_key, "cells": cells})

    stage_rows = []
    done_stages = 0
    for batch in batches:
        material_statuses = []
        for material in material_rows:
            cell = next((c for c in material["cells"] if c["batch_id"] == batch["id"]), None)
            if cell:
                material_statuses.append(cell["status_key"])
        stage_key, stage_label = _stage_status_from_materials(material_statuses, batch["status"])

        if stage_key == "done":
            done_stages += batch["qty_planned"]

        stage_rows.append(
            {
                "batch_id": batch["id"],
                "batch_number": batch["batch_number"],
                "qty_planned": batch["qty_planned"],
                "status_key": stage_key,
                "status_label": stage_label,
            }
        )

    quantity_plan = type_row["quantity_plan"] or 0
    done_manual = type_row["done_manual"] or 0
    done_total = done_stages + done_manual
    remaining = max(quantity_plan - done_total, 0)
    progress_percent = int(math.floor((done_total / quantity_plan) * 100)) if quantity_plan > 0 else 0

    return {
        "type_id": type_row["id"],
        "type_name": type_row["type_name"],
        "quantity_plan": quantity_plan,
        "stage_size": type_row["stage_size"] or 0,
        "done_manual": done_manual,
        "done_stages": done_stages,
        "done_total": done_total,
        "remaining": remaining,
        "progress_percent": min(progress_percent, 100),
        "stages": stage_rows,
        "materials": material_rows,
    }
