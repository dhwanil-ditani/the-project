from fastapi import FastAPI
from core.settings import settings

app = FastAPI(title="FastAPI Project", version="1.0.0")

@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env}
