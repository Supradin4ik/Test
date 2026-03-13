import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM projects")
        projects = cursor.fetchall()

        cursor.execute("SELECT * FROM types")
        types_rows = cursor.fetchall()

        print("Projects:")
        for row in projects:
            print(row)

        print("\nTypes:")
        for row in types_rows:
            print(row)

        print(f"\nКоличество проектов: {len(projects)}")
        print(f"Количество types: {len(types_rows)}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
