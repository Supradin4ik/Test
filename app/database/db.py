import sqlite3
from pathlib import Path


def get_connection() -> sqlite3.Connection:
    db_path = Path(__file__).resolve().parents[2] / "production.db"
    return sqlite3.connect(db_path)
