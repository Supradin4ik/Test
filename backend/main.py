from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import models
from backend.database import engine, get_db
from backend.models import (
    Part,
    PartRoute,
    PartStatus,
    ProductionAction,
    ProductionLog,
    Project,
    ProjectStatus,
    Stage,
)
from backend.services.excel_parser import parse_spec_to_db
from backend.services.production import log_production_action


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)


class ProductionActionRequest(BaseModel):
    part_id: int
    user_id: int
    stage_id: int
    action: str
    qty: int


class ProductionLogResponse(BaseModel):
    id: int
    user_id: int
    stage_id: int
    part_id: int | None
    action: str
    qty_processed: int
    timestamp: datetime


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/projects/upload-spec/")
async def upload_spec(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    file_bytes = await file.read()
    result = await parse_spec_to_db(file_bytes=file_bytes, project_name=project_name, db=db)
    return result


@app.get("/api/parts/{part_id}/history", response_model=list[ProductionLogResponse])
async def get_part_history(part_id: int, db: AsyncSession = Depends(get_db)) -> list[ProductionLogResponse]:
    logs = (
        await db.scalars(
            select(ProductionLog)
            .where(ProductionLog.part_id == part_id)
            .order_by(ProductionLog.timestamp.asc(), ProductionLog.id.asc())
        )
    ).all()

    return [
        ProductionLogResponse(
            id=log.id,
            user_id=log.user_id,
            stage_id=log.stage_id,
            part_id=log.part_id,
            action=log.action.value,
            qty_processed=log.qty_processed,
            timestamp=log.timestamp,
        )
        for log in logs
    ]


@app.post("/api/parts/log-action", response_model=ProductionLogResponse)
async def log_part_action(
    payload: ProductionActionRequest,
    db: AsyncSession = Depends(get_db),
) -> ProductionLogResponse:
    log = await log_production_action(
        part_id=payload.part_id,
        user_id=payload.user_id,
        stage_id=payload.stage_id,
        action_type=payload.action,
        qty=payload.qty,
        db=db,
    )

    return ProductionLogResponse(
        id=log.id,
        user_id=log.user_id,
        stage_id=log.stage_id,
        part_id=log.part_id,
        action=log.action.value,
        qty_processed=log.qty_processed,
        timestamp=log.timestamp,
    )


@app.get("/api/projects/{project_id}/stats")
async def get_project_stats(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    total_parts = await db.scalar(select(func.count(Part.id)).where(Part.project_id == project_id))
    completed_parts = await db.scalar(
        select(func.count(Part.id)).where(Part.project_id == project_id, Part.status == PartStatus.completed)
    )

    total_parts_count = int(total_parts or 0)
    completed_parts_count = int(completed_parts or 0)
    overall_progress = 0.0
    if total_parts_count > 0:
        overall_progress = round((completed_parts_count / total_parts_count) * 100, 2)

    stage_progress: dict[str, float] = {"Лазер": 0.0, "Гибка": 0.0}
    for stage_name in ["Лазер", "Гибка"]:
        stage_id = await db.scalar(select(Stage.id).where(Stage.name == stage_name))
        if stage_id is None:
            continue

        total_stage_parts = await db.scalar(
            select(func.count(distinct(PartRoute.part_id)))
            .join(Part, Part.id == PartRoute.part_id)
            .where(Part.project_id == project_id, PartRoute.stage_id == stage_id)
        )

        completed_stage_parts = await db.scalar(
            select(func.count(distinct(ProductionLog.part_id)))
            .join(Part, Part.id == ProductionLog.part_id)
            .where(
                Part.project_id == project_id,
                ProductionLog.stage_id == stage_id,
                ProductionLog.action == ProductionAction.done,
            )
        )

        total_stage_parts_count = int(total_stage_parts or 0)
        completed_stage_parts_count = int(completed_stage_parts or 0)
        if total_stage_parts_count > 0:
            stage_progress[stage_name] = round(
                (completed_stage_parts_count / total_stage_parts_count) * 100,
                2,
            )

    scrap_rows = (
        await db.execute(
            select(Part.id, Part.name, func.coalesce(func.sum(ProductionLog.qty_processed), 0).label("scrap_qty"))
            .join(ProductionLog, ProductionLog.part_id == Part.id)
            .where(
                Part.project_id == project_id,
                ProductionLog.action == ProductionAction.scrap,
            )
            .group_by(Part.id, Part.name)
            .order_by(Part.id.asc())
        )
    ).all()

    problematic_parts = [
        {"part_id": row.id, "part_name": row.name, "scrap_qty": int(row.scrap_qty)} for row in scrap_rows
    ]

    return {
        "project_id": project_id,
        "overall_progress_percent": overall_progress,
        "completed_parts": completed_parts_count,
        "total_parts": total_parts_count,
        "stage_progress_percent": stage_progress,
        "problematic_parts": problematic_parts,
    }


@app.patch("/api/projects/{project_id}/status")
async def toggle_project_status(project_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str | int]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.status == ProjectStatus.paused:
        project.status = ProjectStatus.active
    else:
        project.status = ProjectStatus.paused

    await db.commit()
    return {"project_id": project_id, "status": project.status.value}
