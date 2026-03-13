import sqlite3
from pathlib import Path


def get_batch_item_stage_columns(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(batch_item_stages)")
    return {row[1] for row in cursor.fetchall()}


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM batch_items
            WHERE item_id = 1
            ORDER BY id
            """
        )
        batch_items = [row[0] for row in cursor.fetchall()]

        if not batch_items:
            raise ValueError("Не найдены batch_items для item_id = 1")

        cursor.execute(
            """
            SELECT stage_name
            FROM routes
            WHERE item_id = 1
            ORDER BY order_index, id
            """
        )
        route_stages = [row[0] for row in cursor.fetchall()]

        if not route_stages:
            raise ValueError("Не найден маршрут в routes для item_id = 1")

        placeholders = ", ".join("?" for _ in batch_items)
        cursor.execute(
            f"DELETE FROM batch_item_stages WHERE batch_item_id IN ({placeholders})",
            batch_items,
        )

        columns = get_batch_item_stage_columns(cursor)
        with_qty_fields = {"qty_done", "qty_in_progress"}.issubset(columns)

        created_count = 0
        for batch_item_id in batch_items:
            for stage_name in route_stages:
                if with_qty_fields:
                    cursor.execute(
                        """
                        INSERT INTO batch_item_stages (
                            batch_item_id,
                            stage_name,
                            status,
                            qty_done,
                            qty_in_progress
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (batch_item_id, stage_name, "pending", 0, 0),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO batch_item_stages (batch_item_id, stage_name, status)
                        VALUES (?, ?, ?)
                        """,
                        (batch_item_id, stage_name, "pending"),
                    )
                created_count += 1

        connection.commit()

    print(f"Количество созданных batch_item_stages: {created_count}")


if __name__ == "__main__":
    main()
