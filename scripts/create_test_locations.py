import sqlite3
from pathlib import Path


TEST_LOCATIONS = [
    ("Laser Zone", "production"),
    ("Bend Zone", "production"),
    ("Weld Zone", "production"),
    ("Shelf A", "storage"),
    ("Finished Zone", "storage"),
]


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.executemany(
            "INSERT INTO locations (name, zone_type) VALUES (?, ?)",
            TEST_LOCATIONS,
        )
        connection.commit()

        cursor.execute("SELECT id, name, zone_type FROM locations ORDER BY id")
        locations = cursor.fetchall()

    print("Созданные и существующие locations:")
    for row in locations:
        print(row)
    print(f"Количество locations: {len(locations)}")


if __name__ == "__main__":
    main()
