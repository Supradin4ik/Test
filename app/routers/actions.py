from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse, RedirectResponse

from app.database.db import get_connection

router = APIRouter()


@router.post("/batch/{batch_id}/block")
def block_batch(batch_id: int, return_to_board: bool = Form(default=False)):
    connection = get_connection()

    try:
        active_block = connection.execute(
            """
            SELECT id
            FROM blocks
            WHERE object_type = 'type_batch' AND object_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (batch_id,),
        ).fetchone()

        if active_block is None:
            connection.execute(
                """
                INSERT INTO blocks (object_type, object_id, reason, comment, status)
                VALUES ('type_batch', ?, 'manual_block', 'Блокировано с борда', 'active')
                """,
                (batch_id,),
            )
            connection.commit()

        if return_to_board:
            return RedirectResponse(url="/board", status_code=303)

        return JSONResponse({"result": "batch blocked", "batch_id": batch_id})
    finally:
        connection.close()


@router.post("/batch/{batch_id}/unblock")
def unblock_batch(batch_id: int, return_to_board: bool = Form(default=False)):
    connection = get_connection()

    try:
        active_block = connection.execute(
            """
            SELECT id
            FROM blocks
            WHERE object_type = 'type_batch' AND object_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (batch_id,),
        ).fetchone()

        if active_block is not None:
            connection.execute(
                "UPDATE blocks SET status = 'resolved' WHERE id = ?",
                (active_block[0],),
            )
            connection.commit()

        if return_to_board:
            return RedirectResponse(url="/board", status_code=303)

        return JSONResponse({"result": "batch unblocked", "batch_id": batch_id})
    finally:
        connection.close()
