import sqlite3
from collections import defaultdict

from app.routers.summary import _get_active_batch_blocks, _get_quantity_column, _resolve_batch_stage_info

STAGE_LABELS = {
    "laser": "Лазер",
    "bend": "Гибка",
    "weld": "Сварка",
    "completed": "Завершено",
    "blocked": "Заблокировано",
}

STATUS_LABELS = {
    "pending": "В ожидании",
    "in_progress": "В работе",
    "blocked": "Заблокировано",
    "done": "Завершено",
    "no_stages": "Нет этапов",
}


def humanize_stage(stage_name: str | None) -> str:
    if not stage_name:
        return "-"
    return STAGE_LABELS.get(stage_name.strip().lower(), stage_name)


def collect_batch_details(connection: sqlite3.Connection, batch_ids: list[int]) -> dict[int, dict[str, object]]:
    if not batch_ids:
        return {}

    placeholders = ",".join("?" for _ in batch_ids)
    batch_items = connection.execute(
        f"SELECT id, batch_id FROM batch_items WHERE batch_id IN ({placeholders}) ORDER BY id",
        batch_ids,
    ).fetchall()
    item_ids = [row["id"] for row in batch_items]

    stages: list[sqlite3.Row] = []
    if item_ids:
        item_placeholders = ",".join("?" for _ in item_ids)
        stages = connection.execute(
            f"SELECT id, batch_item_id, stage_name, status FROM batch_item_stages WHERE batch_item_id IN ({item_placeholders}) ORDER BY id",
            item_ids,
        ).fetchall()

    transfers = connection.execute(
        f"SELECT id, batch_id, location_id, comment, date FROM transfers WHERE batch_id IN ({placeholders}) ORDER BY id",
        batch_ids,
    ).fetchall()
    locations = connection.execute("SELECT id, name FROM locations").fetchall()
    active_blocks = _get_active_batch_blocks(connection)

    item_ids_by_batch: dict[int, list[int]] = defaultdict(list)
    for row in batch_items:
        item_ids_by_batch[row["batch_id"]].append(row["id"])

    stages_by_item: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for stage in stages:
        stages_by_item[stage["batch_item_id"]].append(stage)

    latest_transfer_by_batch: dict[int, sqlite3.Row] = {}
    for transfer in transfers:
        latest_transfer_by_batch[transfer["batch_id"]] = transfer

    location_names = {loc["id"]: loc["name"] for loc in locations}

    result: dict[int, dict[str, object]] = {}
    for batch_id in batch_ids:
        batch_stages: list[sqlite3.Row] = []
        for item_id in item_ids_by_batch.get(batch_id, []):
            batch_stages.extend(stages_by_item.get(item_id, []))

        current_stage_raw, batch_status = _resolve_batch_stage_info(batch_stages)
        done_count = sum(1 for s in batch_stages if (s["status"] or "").lower() == "done")
        total_count = len(batch_stages)
        progress = int((done_count / total_count) * 100) if total_count else 0

        block = active_blocks.get(batch_id)
        blocked = block is not None
        if blocked:
            batch_status = "blocked"
            if current_stage_raw == "completed":
                current_stage_raw = "blocked"

        latest_transfer = latest_transfer_by_batch.get(batch_id)
        location_name = "-"
        last_transfer_comment = "-"
        if latest_transfer is not None:
            location_name = location_names.get(latest_transfer["location_id"], "-")
            last_transfer_comment = latest_transfer["comment"] or "-"

        result[batch_id] = {
            "current_stage_key": current_stage_raw,
            "current_stage": humanize_stage(current_stage_raw),
            "batch_status": batch_status,
            "batch_status_label": STATUS_LABELS.get(batch_status, batch_status),
            "blocked": blocked,
            "block_reason": block["reason"] if block is not None else "-",
            "current_location": location_name,
            "last_transfer_comment": last_transfer_comment,
            "progress_percent": progress,
            "done_stages": done_count,
            "total_stages": total_count,
            "raw_stages": batch_stages,
        }

    return result


def quantity_expr(connection: sqlite3.Connection) -> str:
    return _get_quantity_column(connection) or "NULL"
