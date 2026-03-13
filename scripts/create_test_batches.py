import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT quantity_plan, stage_size
            FROM types
            WHERE id = 1
            """
        )
        type_row = cursor.fetchone()

        if type_row is None:
            raise ValueError("Не найден type с id = 1")

        quantity_plan, stage_size = type_row

        if quantity_plan is None or stage_size is None or stage_size <= 0:
            raise ValueError("Некорректные значения quantity_plan/stage_size у type id = 1")

        cursor.execute("DELETE FROM type_batches WHERE type_id = 1")

        created_batches: list[tuple[int, int, int, str]] = []
        batch_number = 1
        remaining = quantity_plan

        while remaining > 0:
            qty_planned = min(stage_size, remaining)
            cursor.execute(
                """
                INSERT INTO type_batches (type_id, batch_number, qty_planned, status)
                VALUES (?, ?, ?, ?)
                """,
                (1, batch_number, qty_planned, "pending"),
            )
            created_batches.append((1, batch_number, qty_planned, "pending"))

            remaining -= qty_planned
            batch_number += 1

        connection.commit()

    print("Созданные batch (type_id, batch_number, qty_planned, status):")
    for row in created_batches:
        print(row)

    print(f"Количество batch: {len(created_batches)}")


if __name__ == "__main__":
    main()
