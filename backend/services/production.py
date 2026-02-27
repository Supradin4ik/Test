from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Part,
    PartRoute,
    PartStatus,
    ProductionAction,
    ProductionLog,
    Project,
    ProjectStatus,
)


async def log_production_action(
    part_id: int,
    user_id: int,
    stage_id: int,
    action_type: str,
    qty: int,
    db: AsyncSession,
) -> ProductionLog:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")

    project_status = await db.scalar(select(Project.status).where(Project.id == part.project_id))
    if project_status == ProjectStatus.paused:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project is paused. Production actions are not allowed.",
        )

    try:
        production_action = ProductionAction(action_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported action") from exc

    if qty <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity must be positive")

    log = ProductionLog(
        user_id=user_id,
        part_id=part_id,
        stage_id=stage_id,
        action=production_action,
        qty_processed=qty,
        block_number=1,
    )
    db.add(log)
    await db.flush()

    last_route_stage_id = await db.scalar(
        select(PartRoute.stage_id)
        .where(PartRoute.part_id == part_id)
        .order_by(PartRoute.order_index.desc())
        .limit(1)
    )

    if last_route_stage_id is not None:
        completed_on_last_stage = await db.scalar(
            select(func.coalesce(func.sum(ProductionLog.qty_processed), 0)).where(
                ProductionLog.part_id == part_id,
                ProductionLog.stage_id == last_route_stage_id,
                ProductionLog.action == ProductionAction.done,
            )
        )
        if int(completed_on_last_stage or 0) >= part.qty_per_unit:
            part.status = PartStatus.completed
        else:
            part.status = PartStatus.active

    await db.commit()
    await db.refresh(log)
    return log


async def update_part_status(
    part_id: int,
    user_id: int,
    stage_id: int,
    action: str,
    qty: int,
    db: AsyncSession,
) -> ProductionLog:
    return await log_production_action(
        part_id=part_id,
        user_id=user_id,
        stage_id=stage_id,
        action_type=action,
        qty=qty,
        db=db,
    )
