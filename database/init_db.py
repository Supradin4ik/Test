import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
DB_PATH = BASE_DIR.parent / "production.db"

REQUIRED_TABLES = {
    "projects",
    "types",
    "items",
    "routes",
    "type_batches",
    "batch_items",
    "batch_item_stages",
    "transfers",
    "locations",
    "blocks",
}


def get_existing_tables(connection: sqlite3.Connection) -> list[str]:
    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [row[0] for row in cursor.fetchall()]


def init_db() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_sql)
        tables = get_existing_tables(connection)

    missing_tables = sorted(REQUIRED_TABLES - set(tables))

    print("База production.db успешно инициализирована.")
    print("Актуальные таблицы:")
    for table_name in tables:
        print(f"- {table_name}")

    if missing_tables:
        print("Не созданы обязательные таблицы:")
        for table_name in missing_tables:
            print(f"- {table_name}")
    else:
        print("Все обязательные таблицы созданы, включая blocks.")


if __name__ == "__main__":
    init_db()
