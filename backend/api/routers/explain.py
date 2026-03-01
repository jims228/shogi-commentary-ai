"""
backend/api/routers/explain.py
Routes: /api/explain, /api/explain/digest
"""
from __future__ import annotations
import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.auth import Principal, require_user

_LOG = logging.getLogger("uvicorn.error")
from backend.api.services.ai_service import AIService
from backend.api.routers.annotate import _dump_model

router = APIRouter(prefix="/api")


class ExplainCandidate(BaseModel):
    move: str
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None


class PositionCommentRequest(BaseModel):
    ply: int
    sfen: str
    candidates: List[ExplainCandidate] = []
    user_move: Optional[str] = None
    delta_cp: Optional[int] = None


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
async def explain_endpoint(req: PositionCommentRequest, _principal: Principal = Depends(require_user)):
    candidates = [c.model_dump() for c in req.candidates]
    comment = await AIService.generate_position_comment(
        ply=req.ply,
        sfen=req.sfen,
        candidates=candidates,
        user_move=req.user_move,
        delta_cp=req.delta_cp,
    )
    return {"explanation": comment}


@router.post("/explain/digest")
async def digest_endpoint(
    req: GameDigestInput,
    request: Request,
    force_llm: bool = False,
    _principal: Principal = Depends(require_user),
):
    rid = uuid.uuid4().hex[:12]
    ip = request.client.host if request.client else "unknown"
    _LOG.info("[digest] in rid=%s ip=%s path=/api/explain/digest", rid, ip)
    payload = _dump_model(req) or {}
    payload["_request_id"] = rid
    payload["force_llm"] = force_llm
    result = await AIService.generate_game_digest(payload)
    headers = result.pop("_headers", None) or {}
    return JSONResponse(result, headers=headers)
