import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database.db import get_connection
from app.routers.view_data import collect_batch_details, quantity_expr
from app.services.planning_service import (
    ensure_types_done_manual_column,
    get_type_planning_data,
    recreate_type_plan,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class TypeCreate(BaseModel):
    project_id: int
    type_name: str
    quantity_plan: int
    stage_size: int


@router.get("/types")
def get_types() -> list[dict[str, int | str]]:
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            SELECT id, project_id, type_name, quantity_plan, stage_size
            FROM types
            """
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "project_id": row[1],
                "type_name": row[2],
                "quantity_plan": row[3],
                "stage_size": row[4],
            }
            for row in rows
        ]
    finally:
        connection.close()


@router.get("/types/{type_id}", response_class=HTMLResponse)
def get_type_page(type_id: int, request: Request, tab: str = "planning") -> HTMLResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        ensure_types_done_manual_column(connection)

        type_row = connection.execute(
            """
            SELECT t.id, t.project_id, t.type_name, t.quantity_plan, t.stage_size, p.name AS project_name
            FROM types t
            JOIN projects p ON p.id = t.project_id
            WHERE t.id = ?
            """,
            (type_id,),
        ).fetchone()
        if type_row is None:
            raise HTTPException(status_code=404, detail="Type not found")

        batches = connection.execute(
            f"""
            SELECT id, batch_number, {quantity_expr(connection)} AS quantity
            FROM type_batches
            WHERE type_id = ?
            ORDER BY batch_number, id
            """,
            (type_id,),
        ).fetchall()
        batch_ids = [row["id"] for row in batches]
        details = collect_batch_details(connection, batch_ids)
        has_plan = bool(batch_ids)


        items = connection.execute(
            """
            SELECT id, part_number, name, metal, thickness, qty_per_product, total_qty
            FROM items
            WHERE type_id = ?
            ORDER BY id
            """,
            (type_id,),
        ).fetchall()

        batch_payload = []
        for row in batches:
            info = details.get(row["id"], {})
            batch_payload.append(
                {
                    "id": row["id"],
                    "batch_number": row["batch_number"],
                    "quantity": row["quantity"],
                    **info,
                }
            )

        planning = get_type_planning_data(connection, type_id)
        active_tab = tab if tab in {"overview", "planning", "batches", "items"} else "planning"

        return templates.TemplateResponse(
            "type.html",
            {
                "request": request,
                "page_title": type_row["type_name"],
                "active_page": "projects",
                "type_item": dict(type_row),
                "batches": batch_payload,
                "has_plan": has_plan,
                "items": [dict(row) for row in items],
                "planning": planning,
                "active_tab": active_tab,
                "breadcrumbs": [
                    {"label": "Projects", "href": "/projects"},
                    {"label": type_row["project_name"], "href": f"/projects/{type_row['project_id']}"},
                    {"label": type_row["type_name"], "href": None},
                ],
            },
        )
    finally:
        connection.close()


@router.post("/types/{type_id}/plan-production")
def plan_type_production(type_id: int) -> RedirectResponse:
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
            quantity_plan=type_row["quantity_plan"] or 0,
            stage_size=type_row["stage_size"] or 0,
        )
        connection.commit()

        return RedirectResponse(url=f"/types/{type_id}?tab=planning", status_code=303)
    finally:
        connection.close()


@router.post("/types")
def create_type(payload: TypeCreate) -> dict[str, int | str]:
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO types (project_id, type_name, quantity_plan, stage_size)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.type_name,
                payload.quantity_plan,
                payload.stage_size,
            ),
        )
        connection.commit()

        return {
            "id": cursor.lastrowid,
            "project_id": payload.project_id,
            "type_name": payload.type_name,
            "quantity_plan": payload.quantity_plan,
            "stage_size": payload.stage_size,
        }
    finally:
        connection.close()


@router.get("/projects/{project_id}/types")
def get_project_types(project_id: int) -> list[dict[str, int | str]]:
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            SELECT id, project_id, type_name, quantity_plan, stage_size
            FROM types
            WHERE project_id = ?
            """,
            (project_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "project_id": row[1],
                "type_name": row[2],
                "quantity_plan": row[3],
                "stage_size": row[4],
            }
            for row in rows
        ]
    finally:
        connection.close()
