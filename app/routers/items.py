from pathlib import Path
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database.db import get_connection
from app.routers.view_data import humanize_stage

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

DRAWINGS_DIR = Path(__file__).resolve().parents[2] / "drawings"


@router.get("/items/{item_id}", response_class=HTMLResponse)
def get_item_page(item_id: int, request: Request) -> HTMLResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    try:
        item = connection.execute(
            """
            SELECT i.id, i.type_id, i.part_number, i.name, i.metal, i.thickness, i.qty_per_product, i.total_qty,
                   t.type_name, t.project_id, p.name AS project_name
            FROM items i
            JOIN types t ON t.id = i.type_id
            JOIN projects p ON p.id = t.project_id
            WHERE i.id = ?
            """,
            (item_id,),
        ).fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        route_rows = connection.execute(
            "SELECT stage_name, order_index FROM routes WHERE item_id = ? ORDER BY order_index, id",
            (item_id,),
        ).fetchall()
        route = [humanize_stage(row["stage_name"]) for row in route_rows]

        drawing_path = DRAWINGS_DIR / f"{item['part_number']}.pdf"

        return templates.TemplateResponse(
            "item.html",
            {
                "request": request,
                "page_title": item["part_number"],
                "active_page": "projects",
                "item": dict(item),
                "route": route,
                "drawing_found": drawing_path.exists(),
                "breadcrumbs": [
                    {"label": "Projects", "href": "/projects"},
                    {"label": item["project_name"], "href": f"/projects/{item['project_id']}"},
                    {"label": item["type_name"], "href": f"/types/{item['type_id']}"},
                    {"label": item["part_number"], "href": None},
                ],
            },
        )
    finally:
        connection.close()


@router.get("/drawing/{part_number}")
def open_drawing(part_number: str):
    drawing_path = DRAWINGS_DIR / f"{part_number}.pdf"
    if not drawing_path.exists():
        raise HTTPException(status_code=404, detail="Drawing not found")
    return FileResponse(drawing_path, media_type="application/pdf", filename=f"{part_number}.pdf")
