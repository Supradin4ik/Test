from fastapi import FastAPI

from app.routers.health import router as health_router
from app.routers.projects import router as projects_router
from app.routers.types import router as types_router
from app.routers.summary import router as summary_router
from app.routers.board import router as board_router
from app.routers.actions import router as actions_router

app = FastAPI()

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(types_router)
app.include_router(summary_router)
app.include_router(board_router)
app.include_router(actions_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "MES system API started"}
