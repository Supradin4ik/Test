from fastapi import APIRouter, HTTPException

from app.database.db import get_connection

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    connection = None
    try:
        connection = get_connection()
        connection.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "database": "not connected",
                "detail": str(error),
            },
        ) from error
    finally:
        if connection is not None:
            connection.close()
