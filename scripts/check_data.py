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

        cursor.execute("SELECT * FROM items")
        items_rows = cursor.fetchall()

        cursor.execute("SELECT * FROM routes")
        routes_rows = cursor.fetchall()

        cursor.execute("SELECT * FROM type_batches")
        type_batches_rows = cursor.fetchall()

        cursor.execute("SELECT * FROM batch_items")
        batch_items_rows = cursor.fetchall()

        cursor.execute("SELECT * FROM batch_item_stages")
        batch_item_stages_rows = cursor.fetchall()

        print("Projects:")
        for row in projects:
            print(row)

        print("\nTypes:")
        for row in types_rows:
            print(row)

        print("\nItems:")
        for row in items_rows:
            print(row)

        print("\nRoutes:")
        for row in routes_rows:
            print(row)

        print("\nType Batches:")
        for row in type_batches_rows:
            print(row)

        print("\nBatch Items:")
        for row in batch_items_rows:
            print(row)

        print("\nBatch Item Stages:")
        for row in batch_item_stages_rows:
            print(row)

        print(f"\nКоличество проектов: {len(projects)}")
        print(f"Количество types: {len(types_rows)}")
        print(f"Количество items: {len(items_rows)}")
        print(f"Количество routes: {len(routes_rows)}")
        print(f"Количество type_batches: {len(type_batches_rows)}")
        print(f"Количество batch_items: {len(batch_items_rows)}")
        print(f"Количество batch_item_stages: {len(batch_item_stages_rows)}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
