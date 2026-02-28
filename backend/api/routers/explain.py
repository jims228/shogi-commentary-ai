"""
backend/api/routers/explain.py
Routes: /api/explain, /api/explain/digest
"""
from __future__ import annotations
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.auth import Principal, require_user
from backend.api.services.ai_service import AIService
from backend.api.routers.annotate import _dump_model

router = APIRouter(prefix="/api")


class ExplainCandidate(BaseModel):
    move: str
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    pv: str = ""


class ExplainRequest(BaseModel):
    sfen: str
    ply: int
    bestmove: str
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    pv: str
    turn: str
    history: List[str] = []
    user_move: Optional[str] = None
    explain_level: str = "beginner"
    delta_cp: Optional[int] = None
    candidates: List[ExplainCandidate] = []


class GameDigestInput(BaseModel):
    total_moves: int
    eval_history: List[int]
    winner: Optional[str] = None
    notes: Optional[List[dict]] = None
    bioshogi: Optional[dict] = None
    sente_name: Optional[str] = None
    gote_name: Optional[str] = None
    initial_turn: Optional[str] = None  # 'b'=先手先行, 'w'=後手先行


@router.post("/explain")
async def explain_endpoint(req: ExplainRequest, _principal: Principal = Depends(require_user)):
    return await AIService.generate_shogi_explanation_payload(_dump_model(req))


@router.post("/explain/digest")
async def digest_endpoint(
    req: GameDigestInput,
    request: Request,
    force_llm: bool = False,
    _principal: Principal = Depends(require_user),
):
    rid = uuid.uuid4().hex[:12]
    ip = request.client.host if request.client else "unknown"
    print(f"[digest] in rid={rid} ip={ip} path=/api/explain/digest")
    payload = _dump_model(req) or {}
    payload["_request_id"] = rid
    payload["force_llm"] = force_llm
    result = await AIService.generate_game_digest(payload)
    headers = result.pop("_headers", None) or {}
    return JSONResponse(result, headers=headers)
