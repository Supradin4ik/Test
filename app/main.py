from fastapi import FastAPI

from app.routers.health import router as health_router

app = FastAPI()

app.include_router(health_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "MES system API started"}
