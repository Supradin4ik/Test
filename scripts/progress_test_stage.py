import sqlite3
from pathlib import Path
from typing import Iterable


TARGET_BATCH_ITEM_ID = 1
TARGET_STAGE_NAME = "laser"


def get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> list[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def find_qty_required_column(columns: Iterable[str]) -> str | None:
    columns_list = list(columns)
    lower_map = {column.lower(): column for column in columns_list}

    priority = [
        "qty_required",
        "required_qty",
        "quantity_required",
        "qty_need",
        "qty_target",
        "qty_planned",
        "quantity_plan",
        "total_qty",
    ]
    for name in priority:
        if name in lower_map:
            return lower_map[name]

    for column in columns_list:
        lowered = column.lower()
        if ("qty" in lowered or "quantity" in lowered) and (
            "required" in lowered
            or "plan" in lowered
            or "target" in lowered
            or "total" in lowered
        ):
            return column

    return None


def find_batch_completed_column(columns: Iterable[str]) -> str | None:
    columns_list = list(columns)
    lower_map = {column.lower(): column for column in columns_list}

    priority = [
        "qty_completed",
        "completed_qty",
        "quantity_completed",
        "qty_done",
        "done_qty",
    ]
    for name in priority:
        if name in lower_map:
            return lower_map[name]

    for column in columns_list:
        lowered = column.lower()
        if ("qty" in lowered or "quantity" in lowered) and (
            "completed" in lowered or "done" in lowered
        ):
            return column

    return None


def resolve_stage_qty_columns(columns: Iterable[str]) -> dict[str, str]:
    columns_list = list(columns)
    lower_map = {column.lower(): column for column in columns_list}

    result: dict[str, str] = {}

    if "qty_done" in lower_map:
        result["qty_done"] = lower_map["qty_done"]
    if "qty_completed" in lower_map:
        result["qty_completed"] = lower_map["qty_completed"]
    if "qty_in_progress" in lower_map:
        result["qty_in_progress"] = lower_map["qty_in_progress"]

    for column in columns_list:
        lowered = column.lower()
        if column in result.values():
            continue
        if ("qty" in lowered or "quantity" in lowered) and (
            "done" in lowered or "completed" in lowered
        ) and "progress" not in lowered:
            result[f"extra_done::{column}"] = column

    return result


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    if not db_path.exists():
        print(f"Файл БД не найден: {db_path}")
        return

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name IN ('batch_items', 'batch_item_stages')
            """
        )
        existing_tables = {row[0] for row in cursor.fetchall()}
        required_tables = {"batch_items", "batch_item_stages"}
        if required_tables - existing_tables:
            missing = ", ".join(sorted(required_tables - existing_tables))
            print(f"В БД отсутствуют обязательные таблицы: {missing}")
            return

        stage_columns = get_table_columns(cursor, "batch_item_stages")
        batch_columns = get_table_columns(cursor, "batch_items")

        cursor.execute(
            """
            SELECT *
            FROM batch_item_stages
            WHERE batch_item_id = ? AND stage_name = ?
            LIMIT 1
            """,
            (TARGET_BATCH_ITEM_ID, TARGET_STAGE_NAME),
        )
        stage_row = cursor.fetchone()
        if stage_row is None:
            print(
                "Не найдена запись в batch_item_stages "
                f"для batch_item_id={TARGET_BATCH_ITEM_ID}, stage_name='{TARGET_STAGE_NAME}'."
            )
            return

        stage_id = stage_row[stage_columns.index("id")]

        cursor.execute(
            """
            SELECT *
            FROM batch_items
            WHERE id = ?
            LIMIT 1
            """,
            (TARGET_BATCH_ITEM_ID,),
        )
        batch_item_row = cursor.fetchone()
        if batch_item_row is None:
            print(f"Не найдена запись в batch_items для id={TARGET_BATCH_ITEM_ID}.")
            return

        qty_required_column = find_qty_required_column(batch_columns)
        qty_required_value = 0
        if qty_required_column is not None:
            raw_value = batch_item_row[batch_columns.index(qty_required_column)]
            qty_required_value = int(raw_value or 0)

        stage_qty_columns = resolve_stage_qty_columns(stage_columns)

        updates: list[str] = ["status = ?"]
        params: list[object] = ["done"]

        if "qty_done" in stage_qty_columns:
            updates.append(f"{stage_qty_columns['qty_done']} = ?")
            params.append(qty_required_value)

        if "qty_completed" in stage_qty_columns:
            updates.append(f"{stage_qty_columns['qty_completed']} = ?")
            params.append(qty_required_value)

        if "qty_in_progress" in stage_qty_columns:
            updates.append(f"{stage_qty_columns['qty_in_progress']} = ?")
            params.append(0)

        for key, column in stage_qty_columns.items():
            if key.startswith("extra_done::"):
                updates.append(f"{column} = ?")
                params.append(qty_required_value)

        params.append(stage_id)
        cursor.execute(
            f"UPDATE batch_item_stages SET {', '.join(updates)} WHERE id = ?",
            params,
        )

        batch_completed_column = find_batch_completed_column(batch_columns)
        if batch_completed_column is not None:
            cursor.execute(
                f"UPDATE batch_items SET {batch_completed_column} = ? WHERE id = ?",
                (qty_required_value, TARGET_BATCH_ITEM_ID),
            )

        connection.commit()

        cursor.execute(
            """
            SELECT status
            FROM batch_item_stages
            WHERE id = ?
            """,
            (stage_id,),
        )
        new_status = cursor.fetchone()[0]

        print(f"id stage: {stage_id}")
        print(f"stage_name: {TARGET_STAGE_NAME}")
        print(f"new status: {new_status}")
        print(f"итоговое количество выполнения: {qty_required_value}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
