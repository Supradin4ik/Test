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


async def update_part_status(
    part_id: int,
    user_id: int,
    stage_id: int,
    action: str,
    qty: int,
    db: AsyncSession,
) -> ProductionLog:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")

    project_status = await db.scalar(select(Project.status).where(Project.id == part.project_id))
    if project_status in {ProjectStatus.paused, "frozen"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project is frozen. Production actions are not allowed.",
        )

    try:
        production_action = ProductionAction(action)
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

    if production_action == ProductionAction.done:
        processed_total = await db.scalar(
            select(func.coalesce(func.sum(ProductionLog.qty_processed), 0)).where(
                ProductionLog.part_id == part_id,
                ProductionLog.stage_id == stage_id,
                ProductionLog.action == ProductionAction.done,
            )
        )

        if int(processed_total or 0) >= part.qty_per_unit:
            current_route = await db.scalar(
                select(PartRoute)
                .where(PartRoute.part_id == part_id, PartRoute.stage_id == stage_id)
                .order_by(PartRoute.order_index.asc())
            )
            if current_route is not None:
                next_route = await db.scalar(
                    select(PartRoute)
                    .where(
                        PartRoute.part_id == part_id,
                        PartRoute.order_index > current_route.order_index,
                    )
                    .order_by(PartRoute.order_index.asc())
                )
                if next_route is None:
                    part.status = PartStatus.completed
            else:
                part.status = PartStatus.completed

    await db.commit()
    await db.refresh(log)
    return log
