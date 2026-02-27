from io import BytesIO

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Part, PartRoute, Project, Stage


COLUMN_SYNONYMS = {
    "Наименование": ["Наименование"],
    "Материал": ["Материал", "мат", "мат.", "Material"],
    "Толщина": ["Толщина", "толщ", "толщ.", "Thickness", "S"],
    "Количество": ["Количество", "кол-во", "кол", "Qty", "Кол."],
}


def _normalize_column_name(value: str) -> str:
    return str(value).strip().lower()


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    normalized_to_actual = {_normalize_column_name(column): column for column in df.columns}

    resolved = {}
    missing = []
    for canonical_name, synonyms in COLUMN_SYNONYMS.items():
        matched_column = None
        for synonym in synonyms:
            normalized = _normalize_column_name(synonym)
            if normalized in normalized_to_actual:
                matched_column = normalized_to_actual[normalized]
                break

        if matched_column is None:
            missing.append(canonical_name)
            continue

        resolved[canonical_name] = matched_column

    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    return resolved


async def _get_or_create_stage(db: AsyncSession, stage_name: str) -> Stage:
    stage = await db.scalar(select(Stage).where(Stage.name == stage_name))
    if stage is not None:
        return stage

    stage = Stage(name=stage_name)
    db.add(stage)
    await db.flush()
    return stage


async def parse_spec_to_db(file_bytes, project_name: str, db: AsyncSession) -> dict[str, int]:
    df = pd.read_excel(BytesIO(file_bytes))
    columns = _resolve_columns(df)

    name_column = columns["Наименование"]
    material_column = columns["Материал"]
    thickness_column = columns["Толщина"]
    quantity_column = columns["Количество"]

    numeric_thickness = pd.to_numeric(df[thickness_column], errors="coerce")
    parts_df = df.assign(_numeric_thickness=numeric_thickness)

    fasteners = ("Болт", "Гайка", "Шайба")
    parts_df = parts_df[
        ~parts_df[name_column].astype(str).str.contains("|".join(fasteners), case=False, na=False)
        & parts_df["_numeric_thickness"].notna()
    ]

    project = Project(name=project_name, total_units=1, blocks_count=1)
    db.add(project)
    await db.flush()

    laser_stage = await _get_or_create_stage(db, "Лазер")
    bending_stage = await _get_or_create_stage(db, "Гибка")

    parts_added = 0
    for _, row in parts_df.iterrows():
        part = Part(
            project_id=project.id,
            name=str(row[name_column]).strip(),
            material_type=str(row[material_column]).strip(),
            thickness=float(row["_numeric_thickness"]),
            qty_per_unit=int(row[quantity_column]),
        )
        db.add(part)
        await db.flush()

        material_name = str(row[material_column]).strip().lower()
        if "мет" in material_name or "steel" in material_name or "metal" in material_name:
            db.add_all(
                [
                    PartRoute(part_id=part.id, stage_id=laser_stage.id, order_index=1),
                    PartRoute(part_id=part.id, stage_id=bending_stage.id, order_index=2),
                ]
            )
        parts_added += 1

    await db.commit()
    return {"project_id": project.id, "parts_added": parts_added}
