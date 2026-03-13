from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers.health import router as health_router
from app.routers.projects import router as projects_router
from app.routers.types import router as types_router
from app.routers.summary import router as summary_router
from app.routers.board import router as board_router
from app.routers.actions import router as actions_router
from app.routers.batches import router as batches_router
from app.routers.items import router as items_router
from app.routers.spec_import import router as spec_import_router
from app.routers.planning import router as planning_router

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(types_router)
app.include_router(summary_router)
app.include_router(board_router)
app.include_router(actions_router)
app.include_router(batches_router)
app.include_router(items_router)
app.include_router(spec_import_router)
app.include_router(planning_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "MES system API started"}
