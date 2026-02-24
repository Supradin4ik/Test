from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root() -> dict[str, bool]:
    return {"ok": True}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "up"}
