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
from backend.api.services.game_metrics import calculate_skill_score, calculate_tension_timeline
from backend.api.services.position_features import extract_position_features
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
    moves: Optional[List[str]] = None   # USI手順リスト（特徴量抽出用、省略可）


def _extract_digest_features(moves: List[str], max_samples: int = 20) -> List[dict]:
    """手順リストから等間隔でサンプリングして局面特徴量を抽出."""
    n = len(moves)
    if n == 0:
        return []
    step = max(1, n // max_samples)
    sample_indices = list(range(0, n, step))[:max_samples]

    features_list: List[dict] = []
    prev_features = None
    for idx in sample_indices:
        sfen = "position startpos moves " + " ".join(moves[: idx + 1])
        move = moves[idx]
        f = extract_position_features(
            sfen=sfen,
            move=move,
            ply=idx + 1,
            prev_features=prev_features,
        )
        prev_features = f
        features_list.append(f)
    return features_list


@router.post("/explain")
async def explain_endpoint(req: PositionCommentRequest, _principal: Principal = Depends(require_user)):
    candidates = [c.model_dump() for c in req.candidates]

    # 局面特徴量を抽出
    features = None
    try:
        features = extract_position_features(
            sfen=req.sfen,
            move=req.user_move,
            ply=req.ply,
        )
    except Exception:
        _LOG.warning("[explain] position_features extraction failed, continuing without features")

    comment = await AIService.generate_position_comment(
        ply=req.ply,
        sfen=req.sfen,
        candidates=candidates,
        user_move=req.user_move,
        delta_cp=req.delta_cp,
        features=features,
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

    # 手順が渡されていれば局面特徴量をサンプリング抽出
    if req.moves:
        try:
            digest_features = _extract_digest_features(req.moves)
            payload["digest_features"] = digest_features
        except Exception:
            _LOG.warning("[digest] digest_features extraction failed, continuing without features")

    result = await AIService.generate_game_digest(payload)
    result["skill_score"] = calculate_skill_score(req.notes, req.total_moves)
    result["tension"] = calculate_tension_timeline(req.eval_history)
    headers = result.pop("_headers", None) or {}
    return JSONResponse(result, headers=headers)
