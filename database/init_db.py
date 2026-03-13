import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
DB_PATH = BASE_DIR.parent / "production.db"


def init_db() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(schema_sql)
        cursor = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        tables = [row[0] for row in cursor.fetchall()]

    print("База production.db успешно инициализирована.")
    print("Созданные таблицы:")
    for table_name in tables:
        print(f"- {table_name}")


if __name__ == "__main__":
    init_db()
