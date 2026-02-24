import sqlite3
from pathlib import Path

DB_PATH = Path("data.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            project_root_path TEXT,
            standard_root_path TEXT,
            daily_kits INTEGER,
            total_kits INTEGER,
            excel_path TEXT
        );

        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position TEXT,
            dxf_name TEXT,
            part_name TEXT,
            qty_per_kit REAL,
            thickness TEXT,
            material TEXT,
            qty_day REAL,
            pdf_path TEXT,
            pdf_missing INTEGER DEFAULT 0,
            laser_status TEXT DEFAULT 'new',
            bend_status TEXT DEFAULT 'pending',
            weld_status TEXT DEFAULT 'pending',
            qc_status TEXT DEFAULT 'pending',
            zone TEXT DEFAULT ''
        );
        """
    )
    conn.commit()
    conn.close()
