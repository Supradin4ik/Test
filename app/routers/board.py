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


@router.get("/board", response_class=HTMLResponse)
def get_production_board() -> HTMLResponse:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        quantity_column = _get_quantity_column(connection)
        quantity_expr = quantity_column if quantity_column else "NULL"

        batches = connection.execute(
            f"""
            SELECT id, batch_number, {quantity_expr} AS quantity
            FROM type_batches
            ORDER BY batch_number, id
            """
        ).fetchall()

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

        rows: list[dict[str, object]] = []
        for batch in batches:
            batch_id = batch["id"]
            batch_stages: list[sqlite3.Row] = []

            for batch_item_id in batch_item_ids_by_batch.get(batch_id, []):
                batch_stages.extend(stages_by_batch_item.get(batch_item_id, []))

            current_stage, batch_status = _resolve_batch_stage_info(batch_stages)

            active_block = active_blocks_by_batch.get(batch_id)
            blocked = active_block is not None
            block_reason = active_block["reason"] if active_block is not None else None

            if blocked:
                batch_status = "blocked"

            rows.append(
                {
                    "batch_number": batch["batch_number"],
                    "quantity": batch["quantity"],
                    "current_stage": current_stage,
                    "batch_status": batch_status,
                    "blocked": "yes" if blocked else "no",
                    "block_reason": block_reason or "-",
                }
            )

        body_rows = "\n".join(
            "".join(
                [
                    "<tr>",
                    f"<td>{html.escape(str(row['batch_number']))}</td>",
                    f"<td>{html.escape(str(row['quantity']))}</td>",
                    f"<td>{html.escape(str(row['current_stage']))}</td>",
                    f"<td>{html.escape(str(row['batch_status']))}</td>",
                    f"<td>{html.escape(str(row['blocked']))}</td>",
                    f"<td>{html.escape(str(row['block_reason']))}</td>",
                    "</tr>",
                ]
            )
            for row in rows
        )

        page = f"""
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Production Board</title>
  </head>
  <body>
    <h1>Production Board</h1>
    <table border=\"1\" cellspacing=\"0\" cellpadding=\"6\">
      <thead>
        <tr>
          <th>Batch</th>
          <th>Quantity</th>
          <th>Current Stage</th>
          <th>Status</th>
          <th>Blocked</th>
          <th>Block Reason</th>
        </tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </body>
</html>
""".strip()

        return HTMLResponse(content=page)
    finally:
        connection.close()
