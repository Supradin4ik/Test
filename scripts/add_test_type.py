import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO types (project_id, type_name, quantity_plan, stage_size)
            VALUES (?, ?, ?, ?)
            """,
            (1, "TYPE-A", 50, 20),
        )
        connection.commit()

        new_type_id = cursor.lastrowid
        print("Type успешно добавлен.")
        print(f"ID нового type: {new_type_id}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
