import sqlite3
from collections import defaultdict
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "production.db"


def get_quantity_column(connection: sqlite3.Connection) -> str | None:
    """Return the preferred quantity column name for type_batches."""
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(type_batches)").fetchall()
    }

    if "qty_planned" in columns:
        return "qty_planned"

    fallbacks = ("quantity", "qty", "quantity_plan")
    for candidate in fallbacks:
        if candidate in columns:
            return candidate

    return None


def resolve_batch_stage_info(stages: list[sqlite3.Row]) -> tuple[str, str]:
    """
    Determine current_stage and batch_status from stage rows.

    Rules:
    - no stages => ("no_stages", "no_stages")
    - all pending => first pending stage, "pending"
    - mixed done + pending => first pending stage, "in_progress"
    - all done => "completed", "done"
    """
    if not stages:
        return "no_stages", "no_stages"

    normalized = [((row["stage_name"] or "unknown_stage"), (row["status"] or "").strip().lower()) for row in stages]
    statuses = [status for _, status in normalized]

    first_pending_stage = next((stage for stage, status in normalized if status == "pending"), None)

    if statuses and all(status == "done" for status in statuses):
        return "completed", "done"

    if first_pending_stage is not None:
        if all(status == "pending" for status in statuses):
            return first_pending_stage, "pending"
        if any(status == "done" for status in statuses):
            return first_pending_stage, "in_progress"
        return first_pending_stage, "in_progress"

    if any(status == "done" for status in statuses):
        return "completed", "done"

    return "unknown", "unknown"


def print_batch_status_summary(connection: sqlite3.Connection) -> None:
    quantity_column = get_quantity_column(connection)
    quantity_expr = quantity_column if quantity_column else "NULL"

    batches = connection.execute(
        f"""
        SELECT id, batch_number, {quantity_expr} AS quantity
        FROM type_batches
        ORDER BY batch_number, id
        """
    ).fetchall()

    if not batches:
        print("Batch не найдены. Таблица type_batches пуста.")
        return

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

    for batch in batches:
        batch_id = batch["id"]
        batch_number = batch["batch_number"]
        quantity = batch["quantity"]

        quantity_text = str(quantity) if quantity is not None else "unknown"

        batch_stages: list[sqlite3.Row] = []
        for batch_item_id in batch_item_ids_by_batch.get(batch_id, []):
            batch_stages.extend(stages_by_batch_item.get(batch_item_id, []))

        current_stage, batch_status = resolve_batch_stage_info(batch_stages)

        print(f"BATCH {batch_number if batch_number is not None else 'unknown'}")
        print(f"- quantity: {quantity_text}")
        print(f"- current_stage: {current_stage}")
        print(f"- batch_status: {batch_status}")
        print()


def main() -> None:
    if not DB_PATH.exists():
        print(f"Файл базы данных не найден: {DB_PATH}")
        return

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        print_batch_status_summary(connection)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
