import os
import time
import logging
import re
import json
import hashlib
from typing import List, Optional, Dict, Any, Tuple, cast

import google.generativeai as genai
from google.api_core import exceptions as gax_exceptions
from backend.api.utils.gemini_client import ensure_configured, get_model_name
from fastapi import HTTPException
from backend.api.utils.shogi_utils import ShogiUtils, StrategyAnalyzer

from backend.api.utils.shogi_explain_core import (
    build_explain_facts,
    render_rule_based_explanation,
)

from backend.api.db.wkbk_db import lookup_by_sfen

from backend.api.utils.ai_explain_json import (
    ExplainJson,
    build_explain_json_from_facts,
    validate_explain_json,
)

_LOG = logging.getLogger("uvicorn.error")

# --- digest cache (in-memory, dev only) ---
_DIGEST_CACHE_TTL_SEC = int(os.getenv("DIGEST_CACHE_TTL_SEC", "600"))
_DIGEST_CACHE: Dict[str, Dict[str, Any]] = {}



USE_EXPLAIN_V2 = os.getenv("USE_EXPLAIN_V2", "0") == "1"
USE_GEMINI_REWRITE = os.getenv("USE_GEMINI_REWRITE", "1") == "1"

# --- 超軽量キャッシュ（同局面で連打しても課金しない） ---
_EXPLAIN_CACHE: Dict[str, Tuple[float, str]] = {}
_EXPLAIN_CACHE_TTL_SEC = int(os.getenv("EXPLAIN_CACHE_TTL_SEC", "600"))

_EXPLAIN_PAYLOAD_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cache_get(key: str) -> Optional[str]:
    v = _EXPLAIN_CACHE.get(key)
    if not v:
        return None
    ts, text = v
    if time.time() - ts > _EXPLAIN_CACHE_TTL_SEC:
        _EXPLAIN_CACHE.pop(key, None)
        return None
    return text


def _cache_set(key: str, text: str) -> None:
    # 雑に増えすぎないように上限
    if len(_EXPLAIN_CACHE) > 500:
        _EXPLAIN_CACHE.clear()
    _EXPLAIN_CACHE[key] = (time.time(), text)

def _payload_cache_get(key: str) -> Optional[Dict[str, Any]]:
    v = _EXPLAIN_PAYLOAD_CACHE.get(key)
    if not v:
        return None
    ts, payload = v
    if time.time() - ts > _EXPLAIN_CACHE_TTL_SEC:
        _EXPLAIN_PAYLOAD_CACHE.pop(key, None)
        return None
    return payload

def _payload_cache_set(key: str, payload: Dict[str, Any]) -> None:
    if len(_EXPLAIN_PAYLOAD_CACHE) > 500:
        _EXPLAIN_PAYLOAD_CACHE.clear()
    _EXPLAIN_PAYLOAD_CACHE[key] = (time.time(), payload)


class AIService:
    @staticmethod
    async def generate_shogi_explanation(data: Dict[str, Any]) -> str:
        """
        既存を壊さず、新方式は feature flag で切り替える
        """
        payload = await AIService.generate_shogi_explanation_payload(data)
        return str(payload.get("explanation") or "")

    @staticmethod
    async def generate_shogi_explanation_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Backward compatible API payload:
          - explanation: string (always present)
          - explanation_json: structured JSON (optional but usually present)
          - verify: { ok, errors } (debug-friendly)
        """
        cache_key = str(
            {
                "v2": USE_EXPLAIN_V2,
                "sfen": data.get("sfen"),
                "ply": data.get("ply"),
                "turn": data.get("turn"),
                "explain_level": data.get("explain_level"),
                "delta_cp": data.get("delta_cp"),
                "bestmove": data.get("bestmove"),
                "pv": data.get("pv"),
                "user_move": data.get("user_move"),
                "cands": [
                    (
                        c.get("move"),
                        c.get("score_cp"),
                        c.get("score_mate"),
                        c.get("pv"),
                    )
                    for c in (data.get("candidates") or [])
                ][:3],
            }
        )
        hit_payload = _payload_cache_get(cache_key)
        if hit_payload:
            return hit_payload

        # v2 OFF なら完全に旧挙動
        if not USE_EXPLAIN_V2:
            text = await AIService._generate_shogi_explanation_legacy(data)
            payload = AIService._build_structured_payload(data, text=text)
            _payload_cache_set(cache_key, payload)
            _cache_set(cache_key, text)
            return payload

        # v2 ON（失敗したら旧へフォールバック）
        try:
            text = await AIService._generate_shogi_explanation_v2(data)
            payload = AIService._build_structured_payload(data, text=text)
            _payload_cache_set(cache_key, payload)
            _cache_set(cache_key, text)
            return payload
        except Exception as e:
            print("[ExplainV2] error -> fallback legacy:", e)
            text = await AIService._generate_shogi_explanation_legacy(data)
            payload = AIService._build_structured_payload(data, text=text)
            _payload_cache_set(cache_key, payload)
            _cache_set(cache_key, text)
            return payload

    @staticmethod
    async def _generate_shogi_explanation_v2(data: Dict[str, Any]) -> str:
        # 1) 事実抽出（嘘をつけない）
        facts = build_explain_facts(data)

        # 2) まずはルールベース文章（LLMなしで成立）
        # NOTE: We intentionally keep v2 explanation deterministic to avoid contradictions.
        # UI can prefer explanation_json (structured). The text remains a stable fallback.
        return render_rule_based_explanation(facts)

    @staticmethod
    def _build_structured_payload(data: Dict[str, Any], text: str) -> Dict[str, Any]:
        """
        Build explanation_json from facts, validate it, and fallback safely.
        """
        facts = build_explain_facts(data)
        explain_json: Optional[ExplainJson] = None
        verify_errors: List[str] = []
        try:
            candidate = build_explain_json_from_facts(facts)
            parsed, errs = validate_explain_json(candidate.model_dump(), facts)
            if parsed is None:
                verify_errors.extend(errs)
            else:
                explain_json = parsed
        except Exception as e:
            verify_errors.append(f"exception: {e}")

        payload: Dict[str, Any] = {"explanation": text}
        if explain_json is not None:
            payload["explanation_json"] = explain_json.model_dump()
        payload["verify"] = {"ok": len(verify_errors) == 0, "errors": verify_errors}

        # --- DB 参照（wkbk / shogi-extend 由来） ---
        sfen = (data.get("sfen") or "").strip()
        try:
            db_result = lookup_by_sfen(sfen)
            db_refs: Dict[str, Any] = {"hit": db_result.hit, "items": []}
            if db_result.hit:
                db_refs["items"] = [
                    {
                        "key": db_result.key,
                        "lineage_key": db_result.lineage_key,
                        "tags": db_result.tags,
                        "difficulty": db_result.difficulty,
                        "category_hint": db_result.category_hint,
                        "goal_summary": db_result.goal_summary,
                        "author": db_result.author,
                        "short_note": db_result.short_note,
                    }
                ]
            payload["db_refs"] = db_refs
        except Exception as e:
            _LOG.debug("[ai_service] db_refs lookup failed (non-fatal): %s", e)
            payload["db_refs"] = {"hit": False, "items": []}

        return payload

    @staticmethod
    async def _generate_shogi_explanation_legacy(data: Dict[str, Any]) -> str:
        """
        既存の生成を丸ごと残す（旧方式）
        """
        if not ensure_configured():
            return "APIキーが設定されていません。環境変数 GEMINI_API_KEY を確認してください。"

        ply = data.get("ply", 0)
        turn = data.get("turn", "b")
        bestmove = data.get("bestmove", "")
        score_cp = data.get("score_cp")
        score_mate = data.get("score_mate")
        history: List[str] = data.get("history", [])
        sfen = data.get("sfen", "")

        strategy = StrategyAnalyzer.analyze_sfen(sfen)
        bestmove_jp = ShogiUtils.format_move_label(bestmove, turn)

        phase = "序盤" if ply < 24 else "終盤" if ply > 100 else "中盤"
        perspective = "先手" if turn == "b" else "後手"

        score_desc = "互角"
        if score_mate:
            score_desc = "詰みあり"
        elif score_cp is not None:
            sc = score_cp
            if abs(sc) > 2000:
                score_desc = "勝勢"
            elif abs(sc) > 800:
                score_desc = "優勢" if sc > 0 else "劣勢"
            elif abs(sc) > 300:
                score_desc = "有利" if sc > 0 else "不利"

        history_str = " -> ".join(history[-5:]) if history else "初手"

        # DB参照（wkbk / shogi-extend 由来）— faithfulness補助情報
        # 注意: db_refs はあくまで補助。エンジン評価値/PV が最優先根拠。
        # 著作権方針: タグ/カテゴリのみ渡す。元テキスト丸写し禁止。
        db_hint_block = ""
        try:
            db_result = lookup_by_sfen(sfen)
            if db_result.hit:
                hint_lines = [f"- パターン種別: {db_result.category_hint} ({db_result.lineage_key})"]
                if db_result.tags:
                    hint_lines.append(f"- タグ: {', '.join(db_result.tags)}")
                if db_result.difficulty is not None:
                    hint_lines.append(f"- 難易度: {db_result.difficulty}/5")
                if db_result.short_note:
                    hint_lines.append(f"- 補足メモ: {db_result.short_note}")
                if db_result.goal_summary:
                    hint_lines.append(f"- 問題の狙い（要約）: {db_result.goal_summary}")
                db_hint_block = "\n\n【参考パターン情報（補助のみ・断言不可）】\n" + "\n".join(hint_lines)
                db_hint_block += "\n※この情報はヒント程度。エンジン評価値/PVが最優先根拠であること。"
        except Exception:
            pass  # DB参照失敗は非致命的

        prompt = f"""
あなたはプロの将棋解説者です。以下の局面を**{perspective}視点**で、初心者にも分かりやすく解説してください。

【局面情報】
- 手数: {ply}手目 ({phase})
- 戦型目安: {strategy}
- 形勢: {score_desc} (評価値: {score_cp if score_cp is not None else 'Mate'})
- AI推奨手: {bestmove_jp} ({bestmove})
- 直近の進行: {history_str}{db_hint_block}

【指示】
1. 局面ダイジェスト
2. この一手の狙い
3. 次の方針
【制約】
- 評価値/PV 以外の事実を断言しない（根拠がない推測は「〜の可能性があります」と書く）
- 参考パターン情報がある場合はヒントとして活用するが、パターン名を断言しない
"""

        model = genai.GenerativeModel(get_model_name())
        res = await model.generate_content_async(prompt)
        return res.text

    @staticmethod
    async def generate_game_digest(data: Dict[str, Any]) -> Dict[str, Any]:
        request_id = data.get("_request_id") or "n/a"
        total_moves = int(data.get("total_moves") or 0)
        eval_history = data.get("eval_history") or []
        winner = data.get("winner")
        force_llm = bool(data.get("force_llm"))
        notes: List[dict] = data.get("notes") or []
        bioshogi: Dict[str, Any] = data.get("bioshogi") or {}
        sente_name: str = data.get("sente_name") or "先手"
        gote_name: str = data.get("gote_name") or "後手"

        cache_key = _digest_cache_key(total_moves, eval_history, winner,
                                      notes=notes, bioshogi=bioshogi,
                                      sente_name=sente_name, gote_name=gote_name)
        hit = _digest_cache_get(cache_key)
        if hit and not force_llm:
            age = int(time.time() - hit["created_at"])
            _LOG.info("[digest] cache_hit rid=%s key=%s age=%ss", request_id, cache_key, age)
            return _build_digest_payload(
                explanation=hit["explanation"],
                source="cache",
                limited=hit.get("limited", False),
                retry_after=None,
            )

        _LOG.info("[digest] cache_miss rid=%s key=%s", request_id, cache_key)

        force_fallback = os.getenv("FORCE_DIGEST_FALLBACK", "0") == "1"
        if force_fallback:
            explanation = _build_fallback_digest(eval_history, total_moves, winner)
            _digest_cache_set(cache_key, explanation, limited=True)
            return _build_digest_payload(explanation, source="fallback", limited=True, retry_after=None)

        if not ensure_configured():
            # Return fallback to keep dev moving.
            explanation = _build_fallback_digest(eval_history, total_moves, winner)
            _digest_cache_set(cache_key, explanation, limited=False)
            return _build_digest_payload(explanation, source="fallback", limited=False, retry_after=None)

        try:
            step = max(1, len(eval_history) // 20)
            eval_summary = [f"{i}手:{v}" for i, v in enumerate(eval_history) if i % step == 0]

            # --- bioshogi block ---
            bio_block = ""
            if bioshogi:
                bio_s = bioshogi.get("sente") or {}
                bio_g = bioshogi.get("gote") or {}
                s_atk = ", ".join(bio_s.get("attack", []) or []) or "不明"
                s_def = ", ".join(bio_s.get("defense", []) or []) or "不明"
                s_tec = ", ".join(bio_s.get("technique", []) or []) or "なし"
                g_atk = ", ".join(bio_g.get("attack", []) or []) or "不明"
                g_def = ", ".join(bio_g.get("defense", []) or []) or "不明"
                g_tec = ", ".join(bio_g.get("technique", []) or []) or "なし"
                bio_block = (
                    f"\n【戦型・囲い情報】\n"
                    f"- {sente_name}（先手）: 戦型={s_atk}, 囲い={s_def}, 手筋={s_tec}\n"
                    f"- {gote_name}（後手）: 戦型={g_atk}, 囲い={g_def}, 手筋={g_tec}\n"
                )

            # --- notable moves block ---
            notes_block = ""
            if notes:
                notable = sorted(
                    [n for n in notes if isinstance(n.get("delta_cp"), (int, float))],
                    key=lambda n: abs(n["delta_cp"]),
                    reverse=True,
                )[:5]
                if notable:
                    lines = [
                        f"  - {n['ply']}手目 {n.get('move', '')} (Δ{n['delta_cp']:+d}cp)"
                        for n in notable
                    ]
                    notes_block = "\n【注目手（評価値変動が大きかった手）】\n" + "\n".join(lines) + "\n"

            prompt = f"""
将棋の対局データを元に、観戦記風の総評レポート（400文字程度）を作成してください。
- 対局者: {sente_name}（先手）vs {gote_name}（後手）
- 総手数: {total_moves}手
- 評価値推移: {', '.join(eval_summary)}
{bio_block}{notes_block}
【構成】
1. 序盤（戦型・囲いに触れる） 2. 中盤 3. 終盤 4. 総括
"""
            model_name = get_model_name()
            prompt_size = len(prompt)
            t0 = time.time()
            _LOG.info("[digest] llm.start rid=%s model=%s prompt_chars=%s", request_id, model_name, prompt_size)
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(prompt)
            elapsed_ms = int((time.time() - t0) * 1000)
            _LOG.info("[digest] llm.ok rid=%s ms=%s", request_id, elapsed_ms)
            explanation = response.text
            _digest_cache_set(cache_key, explanation, limited=False)
            return _build_digest_payload(explanation, source="llm", limited=False, retry_after=None)
        except gax_exceptions.ResourceExhausted as e:
            _log_llm_exception("ResourceExhausted", e, data)
            retry_after = _extract_retry_after_seconds(e)
            explanation = _build_fallback_digest(eval_history, total_moves, winner)
            _digest_cache_set(cache_key, explanation, limited=True)
            return _build_digest_payload(explanation, source="fallback", limited=True, retry_after=retry_after)
        except gax_exceptions.TooManyRequests as e:
            _log_llm_exception("TooManyRequests", e, data)
            retry_after = _extract_retry_after_seconds(e)
            explanation = _build_fallback_digest(eval_history, total_moves, winner)
            _digest_cache_set(cache_key, explanation, limited=True)
            return _build_digest_payload(explanation, source="fallback", limited=True, retry_after=retry_after)
        except gax_exceptions.GoogleAPICallError as e:
            _log_llm_exception("GoogleAPICallError", e, data)
            explanation = _build_fallback_digest(eval_history, total_moves, winner)
            _digest_cache_set(cache_key, explanation, limited=False)
            return _build_digest_payload(explanation, source="fallback", limited=False, retry_after=None)
        except Exception as e:
            _log_llm_exception(type(e).__name__, e, data)
            explanation = _build_fallback_digest(eval_history, total_moves, winner)
            _digest_cache_set(cache_key, explanation, limited=False)
            return _build_digest_payload(explanation, source="fallback", limited=False, retry_after=None)


def _digest_cache_key(
    total_moves: int,
    eval_history: List[int],
    winner: Optional[str],
    notes: Optional[list] = None,
    bioshogi: Optional[dict] = None,
    sente_name: Optional[str] = None,
    gote_name: Optional[str] = None,
) -> str:
    # Use condensed note/bioshogi summary to keep key compact
    bio_s = ((bioshogi or {}).get("sente") or {})
    bio_g = ((bioshogi or {}).get("gote") or {})
    payload = {
        "total_moves": total_moves,
        "eval_history": eval_history,
        "winner": winner,
        "notes_len": len(notes or []),
        "bio_s_atk": (bio_s.get("attack") or [])[:1],
        "bio_g_atk": (bio_g.get("attack") or [])[:1],
        "sente_name": sente_name,
        "gote_name": gote_name,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest_cache_get(key: str) -> Optional[Dict[str, Any]]:
    v = _DIGEST_CACHE.get(key)
    if not v:
        return None
    if time.time() - v["created_at"] > _DIGEST_CACHE_TTL_SEC:
        _DIGEST_CACHE.pop(key, None)
        return None
    return v


def _digest_cache_set(key: str, explanation: str, limited: bool) -> None:
    if len(_DIGEST_CACHE) > 500:
        _DIGEST_CACHE.clear()
    _DIGEST_CACHE[key] = {
        "created_at": time.time(),
        "explanation": explanation,
        "limited": limited,
    }


def _build_digest_payload(explanation: str, source: str, limited: bool, retry_after: Optional[int]) -> Dict[str, Any]:
    headers: Dict[str, str] = {"X-Digest-Source": source}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return {
        "explanation": explanation,
        "meta": {
            "source": source,
            "limited": bool(limited),
            "retry_after": retry_after,
        },
        "_headers": headers,
    }


def _build_fallback_digest(eval_history: List[int], total_moves: int, winner: Optional[str]) -> str:
    if not eval_history:
        return "評価値データがないため簡易レポートを生成できませんでした。"

    n = len(eval_history)
    thirds = max(1, n // 3)
    opening = eval_history[:thirds]
    middle = eval_history[thirds : 2 * thirds]
    endgame = eval_history[2 * thirds :]

    def avg(xs: List[int]) -> float:
        return sum(xs) / max(1, len(xs))

    def trend_label(v: float) -> str:
        if v > 150:
            return "先手優勢"
        if v < -150:
            return "後手優勢"
        return "互角"

    open_avg = avg(opening)
    mid_avg = avg(middle)
    end_avg = avg(endgame)

    # 最大変動点
    diffs = [eval_history[i] - eval_history[i - 1] for i in range(1, n)]
    max_up = max(diffs) if diffs else 0
    max_down = min(diffs) if diffs else 0
    up_idx = diffs.index(max_up) + 1 if diffs else 0
    down_idx = diffs.index(max_down) + 1 if diffs else 0

    avg_abs = sum(abs(d) for d in diffs) / max(1, len(diffs))
    stability = "安定" if avg_abs < 80 else "変動大きめ"

    lines = []
    if winner:
        lines.append(f"勝敗: {winner}")
    lines.append("【全体傾向】")
    lines.append(f"- 序盤: {trend_label(open_avg)}")
    lines.append(f"- 中盤: {trend_label(mid_avg)}")
    lines.append(f"- 終盤: {trend_label(end_avg)}")
    lines.append("【転換点】")
    lines.append(f"- 最大上昇: {up_idx}手目付近 (+{max_up}cp)")
    lines.append(f"- 最大下降: {down_idx}手目付近 ({max_down}cp)")
    lines.append("【安定度】")
    lines.append(f"- 評価値の変動は {stability} でした")
    lines.append("【次の改善】")
    lines.append("- 中盤で大きく動いた局面を中心に指し手の意図を見直しましょう")
    lines.append("- 形勢が揺れた手順の候補手比較を意識すると改善につながります")
    return "\n".join(lines)


def _extract_error_body(err: Exception) -> str:
    # Try to extract response body safely (first 200 chars).
    resp = getattr(err, "response", None)
    if resp is None:
        return ""
    try:
        body = getattr(resp, "text", None)
        if body is None and hasattr(resp, "content"):
            body = resp.content
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8", errors="ignore")
        if isinstance(body, str):
            return body[:200]
    except Exception:
        return ""
    return ""


def _extract_retry_after_seconds(err: Exception) -> Optional[int]:
    # Try to parse retry delay from exception message (e.g. "Please retry in 49.1s")
    msg = str(err)
    m = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", msg, re.IGNORECASE)
    if not m:
        return None
    try:
        return max(1, int(float(m.group(1))))
    except Exception:
        return None


def _log_llm_exception(label: str, err: Exception, data: Dict[str, Any]) -> None:
    rid = data.get("_request_id") or "n/a"
    status_code = getattr(err, "status_code", None) or getattr(err, "code", None)
    body = _extract_error_body(err)
    _LOG.error(
        "[digest] llm.err rid=%s type=%s status=%s msg=%s body=%s",
        rid,
        label,
        status_code,
        err,
        body,
    )
