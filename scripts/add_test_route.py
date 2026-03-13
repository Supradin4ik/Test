import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        stages = [
            (1, "laser", 1),
            (1, "bend", 2),
            (1, "weld", 3),
        ]

        cursor.executemany(
            """
            INSERT INTO routes (item_id, stage_name, order_index)
            VALUES (?, ?, ?)
            """,
            stages,
        )
        connection.commit()

        print("Маршрут успешно добавлен.")
        print(f"Количество добавленных этапов: {len(stages)}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
