import html
import sqlite3
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database.db import get_connection
from app.routers.summary import (
    _get_active_batch_blocks,
    _get_quantity_column,
    _resolve_batch_stage_info,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


_STAGE_LABELS = {
    "laser": "Лазер",
    "bend": "Гибка",
    "weld": "Сварка",
}

_STATUS_CARD_STYLES = {
    "pending": "status-pending",
    "in_progress": "status-in-progress",
    "blocked": "status-blocked",
    "done": "status-done",
}

_STATUS_LABELS = {
    "pending": "Pending",
    "in_progress": "In Progress",
    "blocked": "Blocked",
    "done": "Done",
}


def _humanize_stage(stage_name: str | None) -> str:
    if not stage_name:
        return "-"
    normalized = stage_name.strip().lower()
    return _STAGE_LABELS.get(normalized, stage_name)


@router.get("/board", response_class=HTMLResponse)
def get_production_board(request: Request) -> HTMLResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        quantity_column = _get_quantity_column(connection)
        quantity_expr = quantity_column if quantity_column else "NULL"

        batches = connection.execute(
            f"""
            SELECT
                tb.id,
                tb.type_id,
                tb.batch_number,
                {quantity_expr} AS quantity,
                t.type_name,
                p.id AS project_id,
                p.name AS project_name
            FROM type_batches tb
            JOIN types t ON t.id = tb.type_id
            JOIN projects p ON p.id = t.project_id
            ORDER BY p.name, p.id, t.type_name, t.id, tb.batch_number, tb.id
            """
        ).fetchall()

        if not batches:
            return templates.TemplateResponse(
                request,
                "layout.html",
                {
                    "page_title": "Production Board",
                    "content": "<p class='muted-text'>Данные по партиям отсутствуют.</p>",
                },
            )

        batch_items = connection.execute(
            "SELECT id, batch_id FROM batch_items ORDER BY batch_id, id"
        ).fetchall()
        stages = connection.execute(
            """
            SELECT id, batch_item_id, stage_name, status
            FROM batch_item_stages
            ORDER BY batch_item_id, id
            """
        ).fetchall()
        transfers = connection.execute(
            """
            SELECT id, batch_id, location_id, comment
            FROM transfers
            ORDER BY id
            """
        ).fetchall()
        locations = connection.execute(
            """
            SELECT id, name
            FROM locations
            ORDER BY id
            """
        ).fetchall()
        active_blocks_by_batch = _get_active_batch_blocks(connection)

        batch_item_ids_by_batch: dict[int, list[int]] = defaultdict(list)
        for batch_item in batch_items:
            batch_id = batch_item["batch_id"]
            if batch_id is None:
                continue
            batch_item_ids_by_batch[batch_id].append(batch_item["id"])

        stages_by_batch_item: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for stage in stages:
            batch_item_id = stage["batch_item_id"]
            if batch_item_id is None:
                continue
            stages_by_batch_item[batch_item_id].append(stage)

        latest_transfer_by_batch: dict[int, sqlite3.Row] = {}
        for transfer in transfers:
            batch_id = transfer["batch_id"]
            if batch_id is None:
                continue
            latest_transfer_by_batch[batch_id] = transfer

        location_names = {location["id"]: location["name"] for location in locations}

        grouped_rows: dict[
            tuple[int | None, str],
            dict[tuple[int | None, str], list[dict[str, object]]],
        ] = defaultdict(lambda: defaultdict(list))

        for batch in batches:
            batch_id = batch["id"]
            batch_stages: list[sqlite3.Row] = []

            for batch_item_id in batch_item_ids_by_batch.get(batch_id, []):
                batch_stages.extend(stages_by_batch_item.get(batch_item_id, []))

            current_stage, batch_status = _resolve_batch_stage_info(batch_stages)

            active_block = active_blocks_by_batch.get(batch_id)
            blocked = active_block is not None
            block_reason = active_block["reason"] if active_block is not None else "-"

            if blocked:
                batch_status = "blocked"

            latest_transfer = latest_transfer_by_batch.get(batch_id)
            current_location = "-"
            if latest_transfer is not None:
                current_location = location_names.get(latest_transfer["location_id"], "-") or "-"

            project_key = (batch["project_id"], batch["project_name"] or "Без проекта")
            type_key = (batch["type_id"], batch["type_name"] or "Без типа")

            grouped_rows[project_key][type_key].append(
                {
                    "batch_id": batch_id,
                    "batch_number": batch["batch_number"] if batch["batch_number"] is not None else "-",
                    "quantity": batch["quantity"] if batch["quantity"] is not None else "-",
                    "current_stage": _humanize_stage(current_stage),
                    "batch_status": batch_status,
                    "block_reason": block_reason or "-",
                    "current_location": current_location,
                }
            )

        sections: list[str] = []
        for (_, project_name), project_types in grouped_rows.items():
            project_html = [
                "<section class='project-section stack-md'>",
                f"<h2 class='section-title'>{html.escape(str(project_name))}</h2>",
            ]

            for (_, type_name), rows in project_types.items():
                cards: list[str] = []
                for row in rows:
                    batch_status = str(row["batch_status"])
                    status_class = _STATUS_CARD_STYLES.get(batch_status, "")
                    status_label = _STATUS_LABELS.get(batch_status, batch_status)

                    cards.append(
                        "".join(
                            [
                                f"<article class='batch-card {status_class}'>",
                                "<div class='batch-card-head'>",
                                f"<h4>Batch {html.escape(str(row['batch_number']))}</h4>",
                                f"<span class='status-badge {status_class}'>{html.escape(status_label)}</span>",
                                "</div>",
                                "<dl class='batch-meta'>",
                                "<div><dt>Quantity</dt>",
                                f"<dd>{html.escape(str(row['quantity']))}</dd></div>",
                                "<div><dt>Current Stage</dt>",
                                f"<dd>{html.escape(str(row['current_stage']))}</dd></div>",
                                "<div><dt>Location</dt>",
                                f"<dd>{html.escape(str(row['current_location']))}</dd></div>",
                                "<div><dt>Block Reason</dt>",
                                f"<dd class='muted-text'>{html.escape(str(row['block_reason']))}</dd></div>",
                                "</dl>",
                                "</article>",
                            ]
                        )
                    )

                project_html.extend(
                    [
                        "<section class='type-section stack-sm'>",
                        f"<h3 class='type-title'>{html.escape(str(type_name))}</h3>",
                        f"<div class='batch-grid'>{''.join(cards)}</div>",
                        "</section>",
                    ]
                )

            project_html.append("</section>")
            sections.append("\n".join(project_html))

        return templates.TemplateResponse(
            request,
            "layout.html",
            {
                "page_title": "Production Board",
                "content": "".join(sections),
            },
        )
    finally:
        connection.close()
