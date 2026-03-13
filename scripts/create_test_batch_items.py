import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, qty_per_product
            FROM items
            WHERE id = 1
            """
        )
        item_row = cursor.fetchone()

        if item_row is None:
            raise ValueError("Не найден item с id = 1")

        item_id, qty_per_product = item_row

        if qty_per_product is None or qty_per_product <= 0:
            raise ValueError("Некорректное qty_per_product у item id = 1")

        cursor.execute(
            """
            SELECT id, qty_planned
            FROM type_batches
            WHERE type_id = 1
            ORDER BY batch_number
            """
        )
        batches = cursor.fetchall()

        if not batches:
            raise ValueError("Не найдены batch в type_batches для type_id = 1")

        batch_ids = [batch_id for batch_id, _ in batches]
        placeholders = ", ".join("?" for _ in batch_ids)
        cursor.execute(
            f"DELETE FROM batch_items WHERE item_id = 1 AND batch_id IN ({placeholders})",
            batch_ids,
        )

        created_batch_items: list[tuple[int, int, int, int]] = []

        for batch_id, qty_planned in batches:
            qty_required = qty_planned * qty_per_product
            cursor.execute(
                """
                INSERT INTO batch_items (batch_id, item_id, qty_required, qty_completed)
                VALUES (?, ?, ?, ?)
                """,
                (batch_id, item_id, qty_required, 0),
            )
            created_batch_items.append((batch_id, item_id, qty_required, 0))

        connection.commit()

    print("Созданные batch_items (batch_id, item_id, qty_required, qty_completed):")
    for row in created_batch_items:
        print(row)

    print(f"Количество batch_items: {len(created_batch_items)}")


if __name__ == "__main__":
    main()
