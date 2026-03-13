import html
import sqlite3
from collections import defaultdict

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.database.db import get_connection
from app.routers.summary import (
    _get_active_batch_blocks,
    _get_quantity_column,
    _resolve_batch_stage_info,
)

router = APIRouter()


_STAGE_LABELS = {
    "laser": "Лазер",
    "bend": "Гибка",
    "weld": "Сварка",
}

_STATUS_ROW_STYLES = {
    "pending": "status-pending",
    "in_progress": "status-in-progress",
    "blocked": "status-blocked",
    "done": "status-done",
}


def _humanize_stage(stage_name: str | None) -> str:
    if not stage_name:
        return "-"
    normalized = stage_name.strip().lower()
    return _STAGE_LABELS.get(normalized, stage_name)


@router.get("/board", response_class=HTMLResponse)
def get_production_board() -> HTMLResponse:
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
            return HTMLResponse(
                content=(
                    "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
                    "<title>Production Board</title></head><body>"
                    "<h1>Production Board</h1><p>Данные по партиям отсутствуют.</p>"
                    "</body></html>"
                )
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

        location_select_options = "".join(
            (
                f"<option value='{location['id']}'>{html.escape(str(location['name']))}</option>"
                for location in locations
            )
        )

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
            last_transfer_comment = "-"
            if latest_transfer is not None:
                current_location = location_names.get(latest_transfer["location_id"], "-") or "-"
                last_transfer_comment = latest_transfer["comment"] or "-"

            project_key = (batch["project_id"], batch["project_name"] or "Без проекта")
            type_key = (batch["type_id"], batch["type_name"] or "Без типа")

            grouped_rows[project_key][type_key].append(
                {
                    "batch_id": batch_id,
                    "batch_number": batch["batch_number"] if batch["batch_number"] is not None else "-",
                    "quantity": batch["quantity"] if batch["quantity"] is not None else "-",
                    "current_stage": _humanize_stage(current_stage),
                    "batch_status": batch_status,
                    "blocked": "Да" if blocked else "Нет",
                    "block_reason": block_reason or "-",
                    "current_location": current_location,
                    "last_transfer_comment": last_transfer_comment,
                }
            )

        sections: list[str] = []
        for (_, project_name), project_types in grouped_rows.items():
            project_html = [
                "<section class='project-block'>",
                f"<h2>PROJECT: {html.escape(str(project_name))}</h2>",
            ]

            for (_, type_name), rows in project_types.items():
                body_rows = []
                for row in rows:
                    status_class = _STATUS_ROW_STYLES.get(str(row["batch_status"]), "")
                    row_class = " ".join([status_class, "batch-row-blocked" if str(row["blocked"]) == "Да" else ""]).strip()

                    action_forms: list[str] = []
                    if str(row["batch_status"]) == "in_progress":
                        action_forms.append(
                            "".join(
                                [
                                    f"<form method='post' action='/batch/{row['batch_id']}/complete-stage' class='inline-form'>",
                                    "<input type='hidden' name='return_to_board' value='true' />",
                                    "<button type='submit'>Завершить этап</button>",
                                    "</form>",
                                ]
                            )
                        )

                    if str(row["batch_status"]) == "blocked":
                        action_forms.append(
                            "".join(
                                [
                                    f"<form method='post' action='/batch/{row['batch_id']}/unblock' class='inline-form'>",
                                    "<input type='hidden' name='return_to_board' value='true' />",
                                    "<button type='submit'>Снять блокировку</button>",
                                    "</form>",
                                ]
                            )
                        )
                    else:
                        action_forms.append(
                            "".join(
                                [
                                    f"<form method='post' action='/batch/{row['batch_id']}/block' class='inline-form'>",
                                    "<input type='hidden' name='return_to_board' value='true' />",
                                    "<button type='submit'>Заблокировать</button>",
                                    "</form>",
                                ]
                            )
                        )

                    action_forms.append(
                        "".join(
                            [
                                f"<form method='post' action='/batch/{row['batch_id']}/transfer' class='transfer-form'>",
                                "<input type='hidden' name='return_to_board' value='true' />",
                                f"<select name='location_id' required>{location_select_options}</select>",
                                "<input type='text' name='comment' placeholder='Комментарий' />",
                                "<button type='submit'>Передать</button>",
                                "</form>",
                            ]
                        )
                    )

                    body_rows.append(
                        "".join(
                            [
                                f"<tr class='{row_class}'>",
                                f"<td>{html.escape(str(row['batch_number']))}</td>",
                                f"<td>{html.escape(str(row['quantity']))}</td>",
                                f"<td>{html.escape(str(row['current_stage']))}</td>",
                                f"<td>{html.escape(str(row['batch_status']))}</td>",
                                f"<td>{html.escape(str(row['blocked']))}</td>",
                                f"<td>{html.escape(str(row['block_reason']))}</td>",
                                f"<td>{html.escape(str(row['current_location']))}</td>",
                                f"<td>{html.escape(str(row['last_transfer_comment']))}</td>",
                                f"<td class='actions-cell'>{''.join(action_forms)}</td>",
                                "</tr>",
                            ]
                        )
                    )

                project_html.extend(
                    [
                        "<div class='type-block'>",
                        f"<h3>TYPE: {html.escape(str(type_name))}</h3>",
                        "<table>",
                        "<thead><tr><th>Batch</th><th>Quantity</th><th>Current Stage</th>"
                        "<th>Status</th><th>Blocked</th><th>Block Reason</th>"
                        "<th>Current Location</th><th>Last Transfer Comment</th><th>Управление</th></tr></thead>",
                        f"<tbody>{''.join(body_rows)}</tbody>",
                        "</table>",
                        "</div>",
                    ]
                )

            project_html.append("</section>")
            sections.append("\n".join(project_html))

        page = f"""
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Production Board</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 20px; color: #222; }}
      h1 {{ margin-bottom: 18px; }}
      .project-block {{ margin-bottom: 28px; }}
      .type-block {{ margin: 10px 0 18px 20px; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
      th, td {{ border: 1px solid #cfcfcf; padding: 8px; text-align: left; vertical-align: top; }}
      thead th {{ background: #f7f7f7; }}
      .status-pending {{ background-color: #f2f2f2; }}
      .status-in-progress {{ background-color: #fff8cc; }}
      .status-blocked {{ background-color: #ffe0e0; }}
      .status-done {{ background-color: #e2f5e2; }}
      .batch-row-blocked {{ font-weight: 600; border-left: 4px solid #d11a2a; }}
      .actions-cell {{ min-width: 320px; }}
      .inline-form {{ display: inline-block; margin-right: 6px; margin-bottom: 6px; }}
      .transfer-form {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }}
      button {{ cursor: pointer; }}
    </style>
  </head>
  <body>
    <h1>Production Board</h1>
    {''.join(sections)}
  </body>
</html>
""".strip()

        return HTMLResponse(content=page)
    finally:
        connection.close()
