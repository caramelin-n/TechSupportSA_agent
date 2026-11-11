"""Entrypoint FastAPI — TechSupport S.A."""
from fastapi import FastAPI

app = FastAPI(title="TechSupport S.A. API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
