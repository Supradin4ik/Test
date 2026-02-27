from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import models
from backend.database import engine, get_db
from backend.models import ProductionLog, Project, ProjectStatus
from backend.services.excel_parser import parse_spec_to_db
from backend.services.production import update_part_status


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
    log = await update_part_status(
        part_id=payload.part_id,
        user_id=payload.user_id,
        stage_id=payload.stage_id,
        action=payload.action,
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


@app.patch("/api/projects/{project_id}/freeze")
async def freeze_project(project_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, str | int]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project.status = ProjectStatus.paused
    await db.commit()
    return {"project_id": project_id, "status": project.status.value}
