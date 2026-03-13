import sqlite3
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.db import get_connection
from app.routers.view_data import collect_batch_details, humanize_stage, quantity_expr

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _batch_stage_rows(connection: sqlite3.Connection, batch_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT s.id, s.batch_item_id, s.stage_name, s.status
        FROM batch_item_stages s
        JOIN batch_items bi ON bi.id = s.batch_item_id
        WHERE bi.batch_id = ?
        ORDER BY s.id
        """,
        (batch_id,),
    ).fetchall()


def _current_stage(stages: list[sqlite3.Row]) -> sqlite3.Row | None:
    for stage in stages:
        status = (stage["status"] or "").lower()
        if status in {"in_progress", "pending"}:
            return stage
    return None


@router.post("/batch/{batch_id}/start-stage")
def start_stage(batch_id: int):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    try:
        stage = _current_stage(_batch_stage_rows(connection, batch_id))
        if stage is None:
            raise HTTPException(status_code=400, detail="No startable stage")
        if (stage["status"] or "").lower() == "pending":
            connection.execute(
                "UPDATE batch_item_stages SET status = 'in_progress' WHERE id = ?",
                (stage["id"],),
            )
        connection.commit()
        return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)
    finally:
        connection.close()


@router.post("/batch/{batch_id}/complete-stage")
def complete_stage(batch_id: int):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    try:
        stages = _batch_stage_rows(connection, batch_id)
        active = next((s for s in stages if (s["status"] or "").lower() == "in_progress"), None)
        if active is None:
            active = _current_stage(stages)
        if active is None:
            raise HTTPException(status_code=400, detail="No completable stage")

        connection.execute("UPDATE batch_item_stages SET status = 'done' WHERE id = ?", (active["id"],))
        connection.commit()
        return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)
    finally:
        connection.close()


@router.post("/batch/{batch_id}/transfer")
def transfer_batch(batch_id: int, location_id: int = Form(...), comment: str = Form(default="")):
    connection = get_connection()
    try:
        location_exists = connection.execute("SELECT 1 FROM locations WHERE id = ?", (location_id,)).fetchone()
        if location_exists is None:
            raise HTTPException(status_code=404, detail="Location not found")

        connection.execute(
            """
            INSERT INTO transfers (batch_id, date, location_id, comment)
            VALUES (?, ?, ?, ?)
            """,
            (batch_id, datetime.now().isoformat(sep=" ", timespec="seconds"), location_id, comment),
        )
        connection.commit()
        return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)
    finally:
        connection.close()


@router.get("/batch/{batch_id}", response_class=HTMLResponse)
def get_batch_page(batch_id: int, request: Request) -> HTMLResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        batch = connection.execute(
            f"""
            SELECT tb.id, tb.batch_number, {quantity_expr(connection)} AS quantity,
                   t.id AS type_id, t.type_name, p.id AS project_id, p.name AS project_name
            FROM type_batches tb
            JOIN types t ON t.id = tb.type_id
            JOIN projects p ON p.id = t.project_id
            WHERE tb.id = ?
            """,
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")

        details = collect_batch_details(connection, [batch_id]).get(batch_id, {})
        raw_stages = details.get("raw_stages", [])
        current_stage_key = details.get("current_stage_key")

        route_stages = []
        for stage in raw_stages:
            stage_status = (stage["status"] or "pending").lower()
            state = "pending"
            if stage_status == "done":
                state = "done"
            elif stage_status == "in_progress" or (
                stage_status == "pending" and (stage["stage_name"] or "").lower() == current_stage_key
            ):
                state = "current"
            route_stages.append(
                {
                    "stage_name": humanize_stage(stage["stage_name"]),
                    "status": stage_status,
                    "state": state,
                }
            )

        locations = connection.execute(
            """
            SELECT id, name
            FROM locations
            WHERE name IN ('Laser Zone', 'Bend Zone', 'Weld Zone', 'Shelf A', 'Finished Zone')
            ORDER BY id
            """
        ).fetchall()
        if not locations:
            locations = connection.execute("SELECT id, name FROM locations ORDER BY id").fetchall()

        transfers = connection.execute(
            """
            SELECT tr.id, tr.date, tr.comment, l.name AS location_name
            FROM transfers tr
            LEFT JOIN locations l ON l.id = tr.location_id
            WHERE tr.batch_id = ?
            ORDER BY tr.id
            """,
            (batch_id,),
        ).fetchall()

        blocks = connection.execute(
            """
            SELECT id, reason, status
            FROM blocks
            WHERE object_type = 'type_batch' AND object_id = ?
            ORDER BY id
            """,
            (batch_id,),
        ).fetchall()

        history: list[dict[str, str | int]] = []
        for stage in raw_stages:
            st = (stage["status"] or "pending").lower()
            if st == "done":
                text = f"{humanize_stage(stage['stage_name'])} завершён"
            elif st == "in_progress":
                text = f"{humanize_stage(stage['stage_name'])} запущен"
            else:
                text = f"{humanize_stage(stage['stage_name'])} ожидает"
            history.append({"order": stage["id"], "text": text, "kind": "stage"})

        for tr in transfers:
            when = tr["date"] or ""
            location_name = tr["location_name"] or "Unknown location"
            suffix = f" ({tr['comment']})" if tr["comment"] else ""
            history.append({"order": 100000 + tr["id"], "text": f"[{when}] Передано в {location_name}{suffix}", "kind": "transfer"})

        for block in blocks:
            if (block["status"] or "").lower() == "active":
                text = f"Блокировка: {block['reason']}"
            else:
                text = "Блокировка снята"
            history.append({"order": 200000 + block["id"], "text": text, "kind": "block"})

        history.sort(key=lambda x: x["order"])

        return templates.TemplateResponse(
            "batch.html",
            {
                "request": request,
                "page_title": f"Batch {batch['batch_number']}",
                "active_page": "board",
                "batch": {**dict(batch), **details},
                "route_stages": route_stages,
                "locations": [dict(row) for row in locations],
                "history": history,
                "breadcrumbs": [
                    {"label": "Projects", "href": "/projects"},
                    {"label": batch["project_name"], "href": f"/projects/{batch['project_id']}"},
                    {"label": batch["type_name"], "href": f"/types/{batch['type_id']}"},
                    {"label": f"Batch {batch['batch_number']}", "href": None},
                ],
            },
        )
    finally:
        connection.close()
