import sqlite3
from datetime import datetime
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "production.db"

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()

        cursor.execute("SELECT id FROM locations WHERE name = ? ORDER BY id LIMIT 1", ("Bend Zone",))
        location_row = cursor.fetchone()

        if location_row is None:
            print("Техническая ошибка: location с name='Bend Zone' не найдена. Сначала запустите scripts/create_test_locations.py")
            return

        location_id = location_row[0]
        date_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO transfers (batch_id, date, location_id, comment)
            VALUES (?, ?, ?, ?)
            """,
            (1, date_text, location_id, "Передано после laser"),
        )
        transfer_id = cursor.lastrowid
        connection.commit()

        cursor.execute(
            "SELECT id, batch_id, location_id, comment FROM transfers WHERE id = ?",
            (transfer_id,),
        )
        transfer_row = cursor.fetchone()

    if transfer_row is None:
        print("Техническая ошибка: не удалось прочитать созданную transfer запись.")
        return

    print(f"id transfer: {transfer_row[0]}")
    print(f"batch_id: {transfer_row[1]}")
    print(f"location_id: {transfer_row[2]}")
    print(f"comment: {transfer_row[3]}")


if __name__ == "__main__":
    main()
