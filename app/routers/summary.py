import sqlite3
from collections import defaultdict

from fastapi import APIRouter

from app.database.db import get_connection

router = APIRouter()


@router.get("/summary/production")
def get_production_summary() -> list[dict[str, object]]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        projects = connection.execute(
            """
            SELECT id, name, client, deadline, status
            FROM projects
            ORDER BY id
            """
        ).fetchall()
        types_rows = connection.execute(
            """
            SELECT id, project_id, type_name, quantity_plan, stage_size
            FROM types
            ORDER BY project_id, id
            """
        ).fetchall()
        batches = connection.execute(
            """
            SELECT id, type_id, batch_number, qty_planned
            FROM type_batches
            ORDER BY type_id, id
            """
        ).fetchall()
        batch_items = connection.execute(
            """
            SELECT id, batch_id
            FROM batch_items
            ORDER BY batch_id, id
            """
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

        types_by_project: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for type_row in types_rows:
            types_by_project[type_row["project_id"]].append(type_row)

        batches_by_type: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for batch in batches:
            batches_by_type[batch["type_id"]].append(batch)

        batch_item_ids_by_batch: dict[int, list[int]] = defaultdict(list)
        for batch_item in batch_items:
            batch_item_ids_by_batch[batch_item["batch_id"]].append(batch_item["id"])

        stages_by_batch_item: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for stage in stages:
            stages_by_batch_item[stage["batch_item_id"]].append(stage)

        location_names = {location["id"]: location["name"] for location in locations}

        latest_transfer_by_batch: dict[int, sqlite3.Row] = {}
        for transfer in transfers:
            batch_id = transfer["batch_id"]
            if batch_id is None:
                continue

            current_latest = latest_transfer_by_batch.get(batch_id)
            if current_latest is None or transfer["id"] > current_latest["id"]:
                latest_transfer_by_batch[batch_id] = transfer

        response: list[dict[str, object]] = []
        for project in projects:
            project_types_payload: list[dict[str, object]] = []

            for type_row in types_by_project.get(project["id"], []):
                type_batches_payload: list[dict[str, object]] = []

                for batch in batches_by_type.get(type_row["id"], []):
                    batch_stages: list[dict[str, str | None]] = []
                    for batch_item_id in batch_item_ids_by_batch.get(batch["id"], []):
                        for stage in stages_by_batch_item.get(batch_item_id, []):
                            batch_stages.append(
                                {
                                    "stage_name": stage["stage_name"],
                                    "status": stage["status"],
                                }
                            )

                    last_transfer = latest_transfer_by_batch.get(batch["id"])
                    current_location = None
                    last_transfer_comment = None

                    if last_transfer is not None:
                        current_location = location_names.get(last_transfer["location_id"])
                        last_transfer_comment = last_transfer["comment"]

                    type_batches_payload.append(
                        {
                            "batch_number": batch["batch_number"],
                            "quantity": batch["qty_planned"],
                            "stages": batch_stages,
                            "current_location": current_location,
                            "last_transfer_comment": last_transfer_comment,
                        }
                    )

                project_types_payload.append(
                    {
                        "type": {
                            "id": type_row["id"],
                            "type_name": type_row["type_name"],
                            "quantity_plan": type_row["quantity_plan"],
                            "stage_size": type_row["stage_size"],
                        },
                        "batches": type_batches_payload,
                    }
                )

            response.append(
                {
                    "project": {
                        "id": project["id"],
                        "name": project["name"],
                        "client": project["client"],
                        "deadline": project["deadline"],
                        "status": project["status"],
                    },
                    "types": project_types_payload,
                }
            )

        return response
    finally:
        connection.close()
