import enum

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, enum.Enum):
    admin = "admin"
    laser = "laser"
    bending = "bending"
    welding = "welding"


class ProjectStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class PartStatus(str, enum.Enum):
    active = "active"
    frozen = "frozen"
    completed = "completed"


class ProductionAction(str, enum.Enum):
    start = "start"
    pause = "pause"
    resume = "resume"
    done = "done"
    scrap = "scrap"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    pin_code = Column(String, nullable=False)
    role = Column(SqlEnum(UserRole), nullable=False)

    material_logs = relationship("MaterialLog", back_populates="user")
    production_logs = relationship("ProductionLog", back_populates="user")


class Stage(Base):
    __tablename__ = "stages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)

    part_routes = relationship("PartRoute", back_populates="stage")
    production_logs = relationship("ProductionLog", back_populates="stage")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    type_name = Column(String, nullable=False, index=True)
    thickness = Column(Float, nullable=False)
    stock_sheets = Column(Float, nullable=False, default=0.0)

    material_logs = relationship("MaterialLog", back_populates="material")


class MaterialLog(Base):
    __tablename__ = "material_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    is_offcut = Column(Boolean, nullable=False, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="material_logs")
    material = relationship("Material", back_populates="material_logs")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    priority_index = Column(Integer, nullable=False, default=10)
    name = Column(String, nullable=False, index=True)
    total_units = Column(Integer, nullable=False)
    blocks_count = Column(Integer, nullable=False)
    status = Column(SqlEnum(ProjectStatus), nullable=False, default=ProjectStatus.active)

    parent = relationship("Project", remote_side=[id], back_populates="children")
    children = relationship("Project", back_populates="parent")
    parts = relationship("Part", back_populates="project")
    nesting_layouts = relationship("NestingLayout", back_populates="project")


class Part(Base):
    __tablename__ = "parts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False, index=True)
    material_type = Column(String, nullable=False)
    thickness = Column(Float, nullable=False)
    qty_per_unit = Column(Integer, nullable=False)
    base_pdf_path = Column(String, nullable=True)
    status = Column(SqlEnum(PartStatus), nullable=False, default=PartStatus.active)

    project = relationship("Project", back_populates="parts")
    routes = relationship("PartRoute", back_populates="part")
    nesting_parts = relationship("NestingPart", back_populates="part")
    production_logs = relationship("ProductionLog", back_populates="part")


class PartRoute(Base):
    __tablename__ = "part_routes"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    stage_id = Column(Integer, ForeignKey("stages.id"), nullable=False)
    order_index = Column(Integer, nullable=False)

    part = relationship("Part", back_populates="routes")
    stage = relationship("Stage", back_populates="part_routes")


class NestingLayout(Base):
    __tablename__ = "nesting_layouts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    filename = Column(String, nullable=False)
    material_type = Column(String, nullable=False)
    thickness = Column(Float, nullable=False)

    project = relationship("Project", back_populates="nesting_layouts")
    nesting_parts = relationship("NestingPart", back_populates="layout")
    production_logs = relationship("ProductionLog", back_populates="nesting_layout")


class NestingPart(Base):
    __tablename__ = "nesting_parts"

    id = Column(Integer, primary_key=True, index=True)
    layout_id = Column(Integer, ForeignKey("nesting_layouts.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    qty_in_layout = Column(Integer, nullable=False)

    layout = relationship("NestingLayout", back_populates="nesting_parts")
    part = relationship("Part", back_populates="nesting_parts")


class ProductionLog(Base):
    __tablename__ = "production_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stage_id = Column(Integer, ForeignKey("stages.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=True)
    nesting_layout_id = Column(Integer, ForeignKey("nesting_layouts.id"), nullable=True)
    block_number = Column(Integer, nullable=False)
    action = Column(SqlEnum(ProductionAction), nullable=False)
    qty_processed = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="production_logs")
    stage = relationship("Stage", back_populates="production_logs")
    part = relationship("Part", back_populates="production_logs")
    nesting_layout = relationship("NestingLayout", back_populates="production_logs")
