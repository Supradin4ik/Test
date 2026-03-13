import sqlite3

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse

from app.database.db import get_connection
from app.services.planning_service import ensure_types_done_manual_column, recreate_type_plan

router = APIRouter()


@router.post("/types/{type_id}/planning/update")
def update_planning_parameters(
    type_id: int,
    quantity_plan: int = Form(...),
    stage_size: int = Form(...),
    done_manual: int = Form(0),
) -> RedirectResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        ensure_types_done_manual_column(connection)

        exists = connection.execute("SELECT id FROM types WHERE id = ?", (type_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Type not found")

        connection.execute(
            """
            UPDATE types
            SET quantity_plan = ?, stage_size = ?, done_manual = ?
            WHERE id = ?
            """,
            (max(quantity_plan, 0), max(stage_size, 0), max(done_manual, 0), type_id),
        )
        connection.commit()
        return RedirectResponse(url=f"/types/{type_id}?tab=planning", status_code=303)
    finally:
        connection.close()


@router.post("/types/{type_id}/planning/replan")
def replan_type_production(type_id: int) -> RedirectResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        ensure_types_done_manual_column(connection)

        type_row = connection.execute(
            "SELECT id, quantity_plan, stage_size FROM types WHERE id = ?",
            (type_id,),
        ).fetchone()
        if type_row is None:
            raise HTTPException(status_code=404, detail="Type not found")

        recreate_type_plan(
            connection,
            type_id=type_id,
            quantity_plan=max(type_row["quantity_plan"] or 0, 0),
            stage_size=max(type_row["stage_size"] or 0, 0),
        )
        connection.commit()
        return RedirectResponse(url=f"/types/{type_id}?tab=planning", status_code=303)
    finally:
        connection.close()
