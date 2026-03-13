import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO items (
                type_id,
                part_number,
                name,
                metal,
                thickness,
                qty_per_product,
                total_qty
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "PART-001", "Дверь", "steel", 1.0, 1, 50),
        )
        connection.commit()

        new_item_id = cursor.lastrowid
        print("Деталь успешно добавлена.")
        print(f"ID новой детали: {new_item_id}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
