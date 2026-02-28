"""
backend/api/routers/annotate.py
Routes: /annotate, /digest
Also owns the shared Pydantic models and annotate() function that tests reference.
"""
from __future__ import annotations
import asyncio
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.auth import Principal, require_api_key
from backend.api import engine_state as _es

router = APIRouter()

# ====== Shared Pydantic models (re-exported via main.py for test compat) ======

class PVItem(BaseModel):
    move: str
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    depth: Optional[int] = None
    pv: List[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    bestmove: str
    candidates: List[PVItem] = Field(default_factory=list)


class AnnotateRequest(BaseModel):
    usi: str
    byoyomi_ms: Optional[int] = None


class AnnotateResponse(BaseModel):
    summary: str = ""
    bestmove: Optional[str] = None
    notes: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class AnalyzeIn(BaseModel):
    position: str
    depth: int = 15
    multipv: int = 3


# ====== Engine adapter (wraps batch_engine for sync callers) ======

class _EnginePlaceholder:
    def analyze(self, payload: Any) -> AnalyzeResponse:
        raise RuntimeError("engine.analyze is not configured")


class _EngineAdapter:
    def analyze(self, payload: Any) -> AnalyzeResponse:
        data = _dump_model(payload)
        usi = (data or {}).get("usi") or ""
        ply_raw = (data or {}).get("ply")
        try:
            ply = int(ply_raw) if ply_raw is not None else None
        except Exception:
            ply = None
        moves_all = _extract_moves_from_usi(usi)
        moves_prefix = moves_all[:ply] if ply is not None else moves_all
        pos_str = "startpos moves " + " ".join(moves_prefix) if moves_prefix else "startpos"
        position_cmd = f"position {pos_str}"

        async def _run() -> Dict[str, Any]:
            async with _es.batch_engine.lock:
                await _es.batch_engine.ensure_alive()
                await _es.batch_engine.stop_and_flush()
                return await _es.batch_engine.fast_analyze_one(position_cmd)

        if _es._MAIN_LOOP is None:
            # テスト環境: 新しいevent loopで直接実行
            try:
                return asyncio.run(_run())
            except Exception as e:
                print(f"[EngineAdapter] analyze failed (no loop): {e}")
                return AnalyzeResponse(bestmove="", candidates=[])
        try:
            fut = asyncio.run_coroutine_threadsafe(_run(), _es._MAIN_LOOP)
            res = fut.result(timeout=15.0)
        except Exception as e:
            print(f"[EngineAdapter] analyze failed: {e}")
            return AnalyzeResponse(bestmove="", candidates=[])

        bestmove = (res or {}).get("bestmove") or ""
        multipv = (res or {}).get("multipv") or []
        candidates: List[PVItem] = []
        for item in multipv:
            score_cp: Optional[int] = None
            score_mate: Optional[int] = None
            depth: Optional[int] = None
            pv_list: List[str] = []
            if isinstance(item, dict):
                depth = item.get("depth")
                pv_raw = item.get("pv")
                if isinstance(pv_raw, str):
                    pv_list = [p for p in pv_raw.split() if p]
                elif isinstance(pv_raw, list):
                    pv_list = [p for p in pv_raw if isinstance(p, str) and p]
                score = item.get("score") or {}
                if isinstance(score, dict):
                    if score.get("type") == "cp":
                        score_cp = score.get("cp")
                    elif score.get("type") == "mate":
                        score_mate = score.get("mate")
            move0 = pv_list[0] if pv_list else ""
            candidates.append(
                PVItem(move=move0, score_cp=score_cp, score_mate=score_mate, depth=depth, pv=pv_list)
            )
        return AnalyzeResponse(bestmove=bestmove, candidates=candidates)


# Module-level engine instance; tests monkeypatch via api_main.engine
engine: _EngineAdapter | _EnginePlaceholder = _EngineAdapter()


# ====== Shared utility functions ======

def _extract_moves_from_usi(usi: str) -> List[str]:
    s = (usi or "").strip()
    if not s:
        return []
    if "moves" in s:
        try:
            return s.split("moves", 1)[1].strip().split()
        except Exception:
            return []
    return s.split()


def _tag_from_delta(delta_cp: Optional[int]) -> List[str]:
    if not isinstance(delta_cp, (int, float)):
        return []
    if delta_cp <= -150:
        return ["悪手"]
    return []


def _digest_from_notes(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    key_moments: List[Dict[str, Any]] = []
    for n in notes:
        d = n.get("delta_cp")
        if isinstance(d, (int, float)) and abs(d) >= 150:
            key_moments.append({"ply": n.get("ply"), "move": n.get("move"), "delta_cp": d})
    if not key_moments and notes:
        key_moments.append(
            {"ply": notes[0].get("ply"), "move": notes[0].get("move"), "delta_cp": notes[0].get("delta_cp")}
        )
    return {
        "summary": ["digest"],
        "key_moments": key_moments,
        "stats": {"plies": len(notes)},
    }


def _dump_model(obj: Any) -> Any:
    """Pydantic v2/v1 compatible dump."""
    md = getattr(obj, "model_dump", None)
    if callable(md):
        try:
            dumped = md()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    d = getattr(obj, "dict", None)
    if callable(d):
        try:
            dumped = d()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    return obj


# ====== annotate() function (also imported by annotate_batch.py) ======

def annotate(payload: Any) -> AnnotateResponse:
    """Core annotation logic. Called by route handler and annotate_batch.py."""
    data = _dump_model(payload)
    usi = (data or {}).get("usi") or ""
    options = (data or {}).get("options") or {}
    moves = _extract_moves_from_usi(usi)

    notes: List[Dict[str, Any]] = []
    prev_score: Optional[int] = None
    last_res: Optional[AnalyzeResponse] = None

    for i, mv in enumerate(moves):
        req = {"usi": usi, "ply": i + 1, "move": mv}
        import sys
        _engine = sys.modules.get('backend.api.main') 
        _engine = getattr(_engine, 'engine', None) if _engine else None
        res = (_engine or engine).analyze(req)
        last_res = res

        score_after: Optional[int] = None
        depth: Optional[int] = None
        pv_line: List[str] = []
        if res.candidates:
            cand0 = res.candidates[0]
            score_after = cand0.score_cp
            depth = cand0.depth
            pv_line = cand0.pv or []

        delta_cp: Optional[int] = None
        if isinstance(score_after, int) and isinstance(prev_score, int):
            delta_cp = score_after - prev_score

        note: Dict[str, Any] = {
            "ply": i + 1,
            "move": mv,
            "bestmove": res.bestmove,
            "score_before_cp": prev_score,
            "score_after_cp": score_after,
            "delta_cp": delta_cp,
            "pv": " ".join(pv_line) if pv_line else "",
            "tags": _tag_from_delta(delta_cp),
            "evidence": {
                "tactical": {"is_capture": False, "is_check": "+" in (mv or "")},
                "depth": depth or 0,
            },
        }
        notes.append(note)

        try:
            if pv_line and (note["tags"] or options):
                from backend.ai import pv_reason as pv_reason_mod
                pv_reason = None
                if getattr(pv_reason_mod, "HAS_SHOGI", False):
                    import shogi  # type: ignore
                    b = shogi.Board()
                    for m0 in moves[:i]:
                        try:
                            mv0 = shogi.Move.from_usi(m0)
                            if hasattr(b, "is_legal") and b.is_legal(mv0):
                                b.push(mv0)
                            else:
                                b.push(mv0)
                        except Exception:
                            break
                    pv_reason = pv_reason_mod.build_pv_reason(b, mv, " ".join(pv_line), options)
                else:
                    pos_str = "startpos moves " + " ".join(moves[:i]) if moves[:i] else "startpos"
                    position_cmd = f"position {pos_str}"
                    pv_reason = pv_reason_mod.build_pv_reason_fallback(
                        position_cmd, " ".join(pv_line), options
                    )
                if pv_reason:
                    note.setdefault("evidence", {}).setdefault("pv_reason", pv_reason)
                    note["explain"] = pv_reason.get("summary")
        except Exception:
            pass

        if isinstance(score_after, int):
            prev_score = score_after

    if not notes:
        notes = [{"ply": 1, "move": "", "tags": [], "evidence": {"tactical": {"is_capture": False}}}]

    candidates_dump: List[Dict[str, Any]] = []
    bestmove: Optional[str] = None
    if last_res is not None:
        bestmove = last_res.bestmove
        candidates_dump = [_dump_model(c) for c in last_res.candidates]

    return AnnotateResponse(summary="annotation", bestmove=bestmove, notes=notes, candidates=candidates_dump)


# ====== Routes ======

@router.post("/annotate")
def annotate_endpoint(payload: Dict[str, Any], _principal: Principal = Depends(require_api_key)):
    return annotate(payload)


@router.post("/digest")
def digest_endpoint_compat(payload: Dict[str, Any]):
    usi = (payload or {}).get("usi") or ""
    moves = _extract_moves_from_usi(usi)
    notes: List[Dict[str, Any]] = []
    prev_score: Optional[int] = None
    for i, mv in enumerate(moves):
        req = {"usi": usi, "ply": i + 1, "move": mv}
        import sys
        _engine = sys.modules.get('backend.api.main') 
        _engine = getattr(_engine, 'engine', None) if _engine else None
        res = (_engine or engine).analyze(req)
        score_after: Optional[int] = None
        if res.candidates:
            score_after = res.candidates[0].score_cp
        delta_cp: Optional[int] = None
        if isinstance(score_after, int) and isinstance(prev_score, int):
            delta_cp = score_after - prev_score
        notes.append({"ply": i + 1, "move": mv, "score_after_cp": score_after, "delta_cp": delta_cp})
        if isinstance(score_after, int):
            prev_score = score_after
    return _digest_from_notes(notes)
