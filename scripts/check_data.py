import sqlite3
from pathlib import Path


def get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> list[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def pick_stage_output_columns(all_columns: list[str]) -> list[str]:
    base_columns: list[str] = []
    for name in ("batch_item_id", "stage_name", "status"):
        if name in all_columns:
            base_columns.append(name)

    qty_columns = [
        column
        for column in all_columns
        if ("qty" in column.lower() or "quantity" in column.lower())
        and column not in base_columns
    ]

    return base_columns + qty_columns


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

        print("\nBatch Item Stages (детальный вывод):")
        stage_columns = get_table_columns(cursor, "batch_item_stages")
        output_columns = pick_stage_output_columns(stage_columns)

        if output_columns:
            query = (
                "SELECT "
                + ", ".join(output_columns)
                + " FROM batch_item_stages ORDER BY batch_item_id, id"
            )
            cursor.execute(query)
            detailed_rows = cursor.fetchall()
            print("Колонки:", ", ".join(output_columns))
            for row in detailed_rows:
                print(row)
        else:
            print("Не удалось определить колонки для детального вывода, fallback на SELECT *")
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
