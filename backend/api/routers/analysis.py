"""
backend/api/routers/analysis.py
Routes: /api/analysis/*, /api/tsume/*, /api/solve/mate
"""
from __future__ import annotations
import json
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api.auth import Principal, require_api_key, require_user
from backend.api.tsume_data import TSUME_PROBLEMS
from backend.api import engine_state as _es
from backend.api.routers.annotate import AnalyzeIn

router = APIRouter()


class BatchAnalysisRequest(BaseModel):
    position: Optional[str] = None
    usi: Optional[str] = None
    moves: Optional[List[str]] = None
    max_ply: Optional[int] = None
    movetime_ms: Optional[int] = None
    multipv: Optional[int] = None
    time_budget_ms: Optional[int] = None


class TsumePlayRequest(BaseModel):
    sfen: str


class MateRequest(BaseModel):
    sfen: str
    timeout: float = 5.0


@router.get("/api/tsume/list")
def get_tsume_list():
    return [{"id": p["id"], "title": p["title"], "steps": p["steps"]} for p in TSUME_PROBLEMS]


@router.get("/api/tsume/{problem_id}")
def get_tsume_detail(problem_id: int):
    problem = next((p for p in TSUME_PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        return {"error": "Problem not found"}
    return problem


@router.post("/api/tsume/play")
async def tsume_play_endpoint(req: TsumePlayRequest, _principal: Principal = Depends(require_api_key)):
    return await _es.stream_engine.solve_tsume_hand(req.sfen)


@router.post("/api/analysis/batch")
async def batch_endpoint(
    req: BatchAnalysisRequest,
    request: Request,
    request_id: Optional[str] = None,
    _principal: Principal = Depends(require_user),
):
    moves = req.moves or []
    if req.usi and "moves" in req.usi:
        moves = req.usi.split("moves")[1].split()
    rid = request_id or uuid.uuid4().hex[:12]
    ip = request.client.host if request.client else "unknown"

    async def generator():
        print(f"[batch] start rid={rid} ip={ip}")
        try:
            async for line in _es.batch_engine.stream_batch_analyze(moves, req.time_budget_ms):
                if await request.is_disconnected():
                    print(f"[batch] client_disconnect rid={rid}")
                    await _es.batch_engine.cancel_current()
                    break
                yield line
        except Exception as e:
            print(f"[batch] error rid={rid}: {e}")
            yield json.dumps({"error": str(e)}) + "\n"
        finally:
            print(f"[batch] end rid={rid}")

    return StreamingResponse(generator(), media_type="application/x-ndjson")


@router.post("/api/analysis/batch-stream")
async def batch_stream_endpoint(
    req: BatchAnalysisRequest,
    request: Request,
    request_id: Optional[str] = None,
    _principal: Principal = Depends(require_user),
):
    return await batch_endpoint(req, request=request, request_id=request_id)


@router.get("/api/analysis/stream")
async def stream_endpoint(
    position: str,
    request: Request,
    request_id: Optional[str] = None,
    _principal: Principal = Depends(require_user),
):
    rid = request_id or uuid.uuid4().hex[:12]
    ip = request.client.host if request.client else "unknown"

    async def generator():
        print(f"[analysis] stream_start rid={rid} ip={ip}")
        try:
            async for chunk in _es.stream_engine.stream_analyze(
                AnalyzeIn(position=position, depth=15, multipv=3)
            ):
                if await request.is_disconnected():
                    print(f"[analysis] client_disconnect rid={rid}")
                    await _es.stream_engine.cancel_current()
                    break
                yield chunk
        finally:
            print(f"[analysis] stream_end rid={rid}")

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/api/solve/mate")
async def solve_mate_endpoint(req: MateRequest):
    """詰み探索エンドポイント（stub: solve_mate未実装）"""
    return await _es.stream_engine.solve_tsume_hand(req.sfen)
