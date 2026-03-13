import sqlite3
from collections import defaultdict

from fastapi import APIRouter

from app.database.db import get_connection

router = APIRouter()


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _get_quantity_column(connection: sqlite3.Connection) -> str | None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(type_batches)").fetchall()
    }

    if "qty_planned" in columns:
        return "qty_planned"

    for candidate in ("quantity", "qty", "quantity_plan"):
        if candidate in columns:
            return candidate

    return None


def _get_active_batch_blocks(connection: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    if not _table_exists(connection, "blocks"):
        return {}

    rows = connection.execute(
        """
        SELECT id, object_id, reason
        FROM blocks
        WHERE object_type = 'type_batch' AND status = 'active'
        ORDER BY id
        """
    ).fetchall()

    blocks_by_batch: dict[int, sqlite3.Row] = {}
    for row in rows:
        object_id = row["object_id"]
        if object_id is None or object_id in blocks_by_batch:
            continue
        blocks_by_batch[object_id] = row

    return blocks_by_batch


def _resolve_batch_stage_info(stages: list[sqlite3.Row]) -> tuple[str, str]:
    if not stages:
        return "no_stages", "pending"

    normalized = [
        ((row["stage_name"] or "unknown_stage"), (row["status"] or "pending").strip().lower())
        for row in stages
    ]
    statuses = [status for _, status in normalized]

    current_stage = next(
        (stage_name for stage_name, status in normalized if status in {"in_progress", "pending"}),
        None,
    )

    if statuses and all(status == "done" for status in statuses):
        return "completed", "done"

    if any(status == "in_progress" for status in statuses):
        return current_stage or "unknown_stage", "in_progress"

    if any(status == "done" for status in statuses) and any(status == "pending" for status in statuses):
        return current_stage or "unknown_stage", "in_progress"

    if statuses and all(status == "pending" for status in statuses):
        return current_stage or "unknown_stage", "pending"

    return current_stage or "unknown_stage", "pending"


@router.get("/summary/production")
def get_production_summary() -> list[dict[str, object]]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        projects = connection.execute(
            """
            SELECT id, name, client, deadline, status
            FROM projects
            ORDER BY id
            """
        ).fetchall()
        types_rows = connection.execute(
            """
            SELECT id, project_id, type_name, quantity_plan, stage_size
            FROM types
            ORDER BY project_id, id
            """
        ).fetchall()
        batches = connection.execute(
            """
            SELECT id, type_id, batch_number, qty_planned
            FROM type_batches
            ORDER BY type_id, id
            """
        ).fetchall()
        batch_items = connection.execute(
            """
            SELECT id, batch_id
            FROM batch_items
            ORDER BY batch_id, id
            """
        ).fetchall()
        stages = connection.execute(
            """
            SELECT id, batch_item_id, stage_name, status
            FROM batch_item_stages
            ORDER BY batch_item_id, id
            """
        ).fetchall()
        transfers = connection.execute(
            """
            SELECT id, batch_id, location_id, comment
            FROM transfers
            ORDER BY id
            """
        ).fetchall()
        locations = connection.execute(
            """
            SELECT id, name
            FROM locations
            ORDER BY id
            """
        ).fetchall()

        types_by_project: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for type_row in types_rows:
            types_by_project[type_row["project_id"]].append(type_row)

        batches_by_type: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for batch in batches:
            batches_by_type[batch["type_id"]].append(batch)

        batch_item_ids_by_batch: dict[int, list[int]] = defaultdict(list)
        for batch_item in batch_items:
            batch_item_ids_by_batch[batch_item["batch_id"]].append(batch_item["id"])

        stages_by_batch_item: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for stage in stages:
            stages_by_batch_item[stage["batch_item_id"]].append(stage)

        location_names = {location["id"]: location["name"] for location in locations}

        latest_transfer_by_batch: dict[int, sqlite3.Row] = {}
        for transfer in transfers:
            batch_id = transfer["batch_id"]
            if batch_id is None:
                continue

            current_latest = latest_transfer_by_batch.get(batch_id)
            if current_latest is None or transfer["id"] > current_latest["id"]:
                latest_transfer_by_batch[batch_id] = transfer

        response: list[dict[str, object]] = []
        for project in projects:
            project_types_payload: list[dict[str, object]] = []

            for type_row in types_by_project.get(project["id"], []):
                type_batches_payload: list[dict[str, object]] = []

                for batch in batches_by_type.get(type_row["id"], []):
                    batch_stages: list[dict[str, str | None]] = []
                    for batch_item_id in batch_item_ids_by_batch.get(batch["id"], []):
                        for stage in stages_by_batch_item.get(batch_item_id, []):
                            batch_stages.append(
                                {
                                    "stage_name": stage["stage_name"],
                                    "status": stage["status"],
                                }
                            )

                    last_transfer = latest_transfer_by_batch.get(batch["id"])
                    current_location = None
                    last_transfer_comment = None

                    if last_transfer is not None:
                        current_location = location_names.get(last_transfer["location_id"])
                        last_transfer_comment = last_transfer["comment"]

                    type_batches_payload.append(
                        {
                            "batch_number": batch["batch_number"],
                            "quantity": batch["qty_planned"],
                            "stages": batch_stages,
                            "current_location": current_location,
                            "last_transfer_comment": last_transfer_comment,
                        }
                    )

                project_types_payload.append(
                    {
                        "type": {
                            "id": type_row["id"],
                            "type_name": type_row["type_name"],
                            "quantity_plan": type_row["quantity_plan"],
                            "stage_size": type_row["stage_size"],
                        },
                        "batches": type_batches_payload,
                    }
                )

            response.append(
                {
                    "project": {
                        "id": project["id"],
                        "name": project["name"],
                        "client": project["client"],
                        "deadline": project["deadline"],
                        "status": project["status"],
                    },
                    "types": project_types_payload,
                }
            )

        return response
    finally:
        connection.close()


@router.get("/summary/batch-status")
def get_batch_status_summary() -> list[dict[str, object]]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        quantity_column = _get_quantity_column(connection)
        quantity_expr = quantity_column if quantity_column else "NULL"

        batches = connection.execute(
            f"""
            SELECT id, batch_number, {quantity_expr} AS quantity
            FROM type_batches
            ORDER BY batch_number, id
            """
        ).fetchall()

        if not batches:
            return []

        batch_items = connection.execute(
            "SELECT id, batch_id FROM batch_items ORDER BY batch_id, id"
        ).fetchall()
        stages = connection.execute(
            """
            SELECT id, batch_item_id, stage_name, status
            FROM batch_item_stages
            ORDER BY batch_item_id, id
            """
        ).fetchall()
        active_blocks_by_batch = _get_active_batch_blocks(connection)

        batch_item_ids_by_batch: dict[int, list[int]] = defaultdict(list)
        for batch_item in batch_items:
            batch_id = batch_item["batch_id"]
            if batch_id is None:
                continue
            batch_item_ids_by_batch[batch_id].append(batch_item["id"])

        stages_by_batch_item: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for stage in stages:
            batch_item_id = stage["batch_item_id"]
            if batch_item_id is None:
                continue
            stages_by_batch_item[batch_item_id].append(stage)

        response: list[dict[str, object]] = []
        for batch in batches:
            batch_id = batch["id"]
            batch_stages: list[sqlite3.Row] = []

            for batch_item_id in batch_item_ids_by_batch.get(batch_id, []):
                batch_stages.extend(stages_by_batch_item.get(batch_item_id, []))

            current_stage, batch_status = _resolve_batch_stage_info(batch_stages)

            active_block = active_blocks_by_batch.get(batch_id)
            blocked = active_block is not None
            block_reason = active_block["reason"] if active_block is not None else None

            if blocked:
                batch_status = "blocked"
                if current_stage == "completed":
                    current_stage = "blocked"

            response.append(
                {
                    "batch_id": batch_id,
                    "batch_number": batch["batch_number"],
                    "quantity": batch["quantity"],
                    "current_stage": current_stage,
                    "batch_status": batch_status,
                    "blocked": blocked,
                    "block_reason": block_reason,
                }
            )

        return response
    finally:
        connection.close()
