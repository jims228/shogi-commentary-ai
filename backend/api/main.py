"""
backend/api/main.py
将棋解説AI - FastAPI アプリケーションエントリポイント
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import annotate, analysis, explain, games


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown


app = FastAPI(
    title="将棋解説AI API",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
_default_origins = ["http://localhost:3000", "http://localhost:3001"]
_env_origins = os.getenv("FRONTEND_ORIGINS", "")
_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(annotate.router)
app.include_router(analysis.router)
app.include_router(explain.router, prefix="/api")
app.include_router(games.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "shogi-commentary-ai ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
