from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError


class DetectionItem(BaseModel):
    id: str
    nameJa: str
    confidence: float = 0.0
    reasons: List[str] = Field(default_factory=list)


class PvGuideItem(BaseModel):
    move: str
    note: str = ""


class ExplainJson(BaseModel):
    headline: str
    why: List[str] = Field(default_factory=list)
    pvGuide: List[PvGuideItem] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    # Optional structured detections (rule-based)
    style: Optional[DetectionItem] = None
    opening: Optional[DetectionItem] = None
    castle: Optional[DetectionItem] = None


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def build_explain_json_from_facts(f: Dict[str, Any]) -> ExplainJson:
    """
    Deterministic (non-LLM) structured explanation builder.
    The goal is consistency: never contradict bestmove/PV/eval.
    """
    bestmove = (f.get("bestmove") or "").strip()
    bestmove_jp = (f.get("bestmove_jp") or "").strip()
    target_move = (f.get("target_move") or "").strip()
    target_move_jp = (f.get("target_move_jp") or "").strip()

    # Prefer "target" if it exists (e.g. user_move), but never label it as best if it differs.
    move_for_headline = target_move_jp or bestmove_jp or target_move or bestmove or "（手なし）"

    score_turn = f.get("score_turn") or {}
    mate = score_turn.get("mate")
    cp = score_turn.get("cp")
    score_words = (f.get("score_words") or "").strip()
    phase = (f.get("phase") or "").strip()

    flags = f.get("flags") or {}
    is_check = bool(flags.get("is_check"))
    is_capture = bool(flags.get("is_capture"))
    is_promotion = bool(flags.get("is_promotion"))
    is_drop = bool(flags.get("is_drop"))
    line_opened = bool(flags.get("line_opened"))

    why: List[str] = []
    if phase or score_words:
        why.append("局面の状況: " + " / ".join([p for p in [phase, f"形勢: {score_words}" if score_words else ""] if p]))

    # Only add reasons that are directly derivable from facts/flags.
    if is_check:
        why.append("王手で相手玉の選択肢を減らす。")
    if is_capture:
        ck = flags.get("captured_kind_hand") or flags.get("captured_kind")
        why.append(f"{ck}を取って駒得を狙う。" if ck else "駒取りで得を狙う。")
    if is_promotion:
        why.append("成りで駒の力を上げる。")
    if is_drop:
        why.append("持ち駒を使って局面を動かす。")
    if line_opened:
        why.append("大駒の利きが通りやすくなる。")
    if not any([is_check, is_capture, is_promotion, is_drop, line_opened]):
        why.append("形を整えて次の攻防に備える。")

    # PV guide (prefix only)
    pv_moves: List[str] = list(f.get("pv_moves") or [])
    pv_jp: List[str] = list(f.get("pv_jp") or [])
    pvGuide: List[PvGuideItem] = []
    for i, mv in enumerate(pv_moves[:6]):
        note = pv_jp[i] if i < len(pv_jp) else ""
        pvGuide.append(PvGuideItem(move=mv, note=note))

    risks: List[str] = []
    # Avoid numeric claims. Avoid saying "mate" unless mate-eval exists.
    if is_check:
        risks.append("受け方（逃げる/取る/合駒）の成立を確認。")
    if is_capture:
        risks.append("取り返されないか、直後の反撃を確認。")
    if not risks:
        risks.append("相手の王手・駒取りを先にチェック。")

    # Confidence: higher if PV exists and is consistent; otherwise lower.
    conf = 0.55
    if bestmove and pv_moves and pv_moves[0] == bestmove:
        conf += 0.25
    if isinstance(mate, int) and mate != 0:
        conf += 0.1
    if isinstance(cp, int):
        conf += 0.05
    conf = _clamp01(conf)

    headline = f"推奨: {bestmove} / {move_for_headline}".strip() if bestmove else f"{move_for_headline}"
    # Do NOT say "詰み" unless eval is mate.
    if isinstance(mate, int) and mate != 0:
        headline = headline + "（詰み筋）"

    return ExplainJson(
        headline=headline,
        why=why[:5],
        pvGuide=pvGuide,
        risks=risks[:3],
        confidence=conf,
        style=(f.get("opening_facts") or {}).get("style"),
        opening=(f.get("opening_facts") or {}).get("opening"),
        castle=(f.get("castle_facts") or {}).get("castle"),
    )


def validate_explain_json(obj: Any, facts: Dict[str, Any]) -> Tuple[Optional[ExplainJson], List[str]]:
    """
    Validate JSON output + enforce minimal consistency rules.
    Returns (parsed, errors). If errors, caller should fallback.
    """
    errors: List[str] = []
    try:
        parsed = ExplainJson.model_validate(obj)
    except ValidationError as e:
        return None, [f"schema: {e}"]

    bestmove = (facts.get("bestmove") or "").strip()
    pv_moves: List[str] = list(facts.get("pv_moves") or [])
    mate = (facts.get("score_turn") or {}).get("mate")

    # pvGuide prefix check
    if parsed.pvGuide:
        if bestmove and parsed.pvGuide[0].move != bestmove:
            errors.append("pvGuide[0] != bestmove")
        for i, item in enumerate(parsed.pvGuide):
            if i < len(pv_moves) and item.move != pv_moves[i]:
                errors.append(f"pvGuide[{i}] != pv[{i}]")

    # "詰み" claims require mate eval
    text_blob = "\n".join([parsed.headline] + parsed.why + parsed.risks + [x.note for x in parsed.pvGuide])
    if "詰み" in text_blob:
        if not (isinstance(mate, int) and mate != 0):
            errors.append("mentions mate but eval is not mate")

    # No numeric claims like "駒得◯点" etc. (best-effort)
    if any(ch.isdigit() for ch in text_blob):
        # Allow USI coords like 7g7f (digits are OK). Detect "点" style.
        if "点" in text_blob or "cp" in text_blob or "ＣＰ" in text_blob:
            errors.append("contains numeric claim")

    # Detection sanity: if id != unknown, reasons must exist.
    for k in ("style", "opening", "castle"):
        item = getattr(parsed, k, None)
        if item is None:
            continue
        if (item.id or "") != "unknown" and not (item.reasons and len(item.reasons) > 0):
            errors.append(f"{k}.reasons empty")

    parsed.confidence = _clamp01(float(parsed.confidence))
    return (parsed if not errors else None), errors


