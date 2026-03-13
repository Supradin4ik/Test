import sqlite3
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.database.db import get_connection

router = APIRouter()


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


@router.post("/batch/{batch_id}/complete-stage")
def complete_batch_stage(batch_id: int, return_to_board: bool = Form(default=False)):
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        pending_stage = connection.execute(
            """
            SELECT s.id, s.batch_item_id, bi.qty_required
            FROM batch_item_stages s
            JOIN batch_items bi ON bi.id = s.batch_item_id
            WHERE bi.batch_id = ? AND LOWER(COALESCE(s.status, '')) = 'pending'
            ORDER BY s.batch_item_id, s.id
            LIMIT 1
            """,
            (batch_id,),
        ).fetchone()

        if pending_stage is None:
            raise HTTPException(status_code=404, detail="No pending stage found for batch")

        stage_columns = _table_columns(connection, "batch_item_stages")
        set_clauses = ["status = 'done'"]
        params: list[object] = []

        if "qty_done" in stage_columns:
            if "qty_required" in stage_columns:
                set_clauses.append("qty_done = qty_required")
            else:
                set_clauses.append("qty_done = ?")
                params.append(pending_stage["qty_required"] or 0)

        if "qty_in_progress" in stage_columns:
            set_clauses.append("qty_in_progress = 0")

        params.append(pending_stage["id"])

        connection.execute(
            f"""
            UPDATE batch_item_stages
            SET {', '.join(set_clauses)}
            WHERE id = ?
            """,
            params,
        )
        connection.commit()

        if return_to_board:
            return RedirectResponse(url="/board", status_code=303)

        return JSONResponse({"result": "stage completed", "batch_id": batch_id})
    finally:
        connection.close()


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


@router.post("/batch/{batch_id}/transfer")
def transfer_batch(
    batch_id: int,
    location_id: int = Form(...),
    comment: str = Form(default=""),
    return_to_board: bool = Form(default=False),
):
    connection = get_connection()

    try:
        location_exists = connection.execute(
            "SELECT 1 FROM locations WHERE id = ?",
            (location_id,),
        ).fetchone()
        if location_exists is None:
            raise HTTPException(status_code=404, detail="Location not found")

        connection.execute(
            """
            INSERT INTO transfers (batch_id, date, location_id, comment)
            VALUES (?, ?, ?, ?)
            """,
            (
                batch_id,
                datetime.now().isoformat(sep=" ", timespec="seconds"),
                location_id,
                comment,
            ),
        )
        connection.commit()

        if return_to_board:
            return RedirectResponse(url="/board", status_code=303)

        return JSONResponse({"result": "batch transferred", "batch_id": batch_id})
    finally:
        connection.close()
