from fastapi import APIRouter
from pydantic import BaseModel

from app.database.db import get_connection

router = APIRouter()


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
