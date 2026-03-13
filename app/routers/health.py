from fastapi import APIRouter

from app.database.db import get_connection

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    connection = get_connection()
    try:
        connection.execute("SELECT 1")
    finally:
        connection.close()

    return {"status": "ok", "database": "connected"}
