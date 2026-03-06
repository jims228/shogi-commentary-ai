import asyncio
import os
import time
import logging
import re
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

import google.generativeai as genai
from google.api_core import exceptions as gax_exceptions
from backend.api.utils.gemini_client import ensure_configured
from backend.api.utils.shogi_utils import ShogiUtils
from backend.api.services.training_logger import training_logger
from backend.api.services.position_features import extract_position_features

_LOG = logging.getLogger("uvicorn.error")

# --- lazy style selector ---
_style_selector = None


def _get_style_selector():
    global _style_selector
    if _style_selector is None:
        from backend.api.services.ml_trainer import CommentaryStyleSelector
        _style_selector = CommentaryStyleSelector()
        _style_selector.load()  # load saved model if available
    return _style_selector


_STYLE_INSTRUCTIONS = {
    "technical": "専門的な視点で、手順や読み筋に言及しつつ解説してください。",
    "encouraging": "親しみやすく前向きなトーンで、指し手の良い点を認めながら解説してください。",
    "neutral": "客観的かつ淡々と、局面の状況を正確に解説してください。",
}

# --- digest cache (in-memory, dev only) ---
_DIGEST_CACHE_TTL_SEC = int(os.getenv("DIGEST_CACHE_TTL_SEC", "600"))
_DIGEST_CACHE: Dict[str, Dict[str, Any]] = {}



_EXPLAIN_CACHE: Dict[str, Tuple[float, str]] = {}
_EXPLAIN_CACHE_TTL_SEC = int(os.getenv("EXPLAIN_CACHE_TTL_SEC", "600"))


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
    if len(_EXPLAIN_CACHE) > 500:
        _EXPLAIN_CACHE.clear()
    _EXPLAIN_CACHE[key] = (time.time(), text)


def _detect_turn(sfen: str) -> str:
    """position コマンド文字列から手番を判定する.

    "position startpos moves ..." 形式の場合、moves の数の偶奇で判定。
    "position sfen ... b/w ... moves ..." 形式の場合、ベースSFEN中の手番 + moves数で判定。
    """
    parts = sfen.split()

    if "startpos" in parts:
        # startpos = sente(b) to move, each move flips turn
        if "moves" in parts:
            n_moves = len(parts) - parts.index("moves") - 1
        else:
            n_moves = 0
        return "b" if n_moves % 2 == 0 else "w"

    # "position sfen <board> <turn> <hands> <ply> moves ..."
    if "sfen" in parts:
        si = parts.index("sfen")
        # turn token is 2 positions after "sfen" (board turn hands ply)
        base_turn = "b"
        if si + 2 < len(parts) and parts[si + 2] in ("b", "w"):
            base_turn = parts[si + 2]
        if "moves" in parts:
            n_moves = len(parts) - parts.index("moves") - 1
        else:
            n_moves = 0
        # Each move flips the turn from base
        if n_moves % 2 == 0:
            return base_turn
        return "w" if base_turn == "b" else "b"

    return "b"


def _describe_safety(value: int) -> str:
    """king_safety (0-100) を人間が読める説明に変換."""
    if value >= 80:
        return "堅い囲いで安定"
    if value >= 55:
        return "ある程度守られている"
    if value >= 30:
        return "やや不安定"
    return "玉が危険な状態"


def _describe_pressure(value: int) -> str:
    """attack_pressure (0-100) を人間が読める説明に変換."""
    if value >= 70:
        return "強い攻撃態勢"
    if value >= 40:
        return "攻めの形ができつつある"
    if value >= 15:
        return "まだ様子見"
    return "攻めの形なし"


_PHASE_JP = {"opening": "序盤", "midgame": "中盤", "endgame": "終盤"}

_INTENT_JP = {
    "attack": "攻め（相手玉や駒を狙う手）",
    "defense": "守り（自玉を固める手）",
    "development": "駒組み（陣形を整える手）",
    "exchange": "駒交換（互いに取り合う手）",
    "sacrifice": "犠牲（駒損を承知で踏み込む手）",
}


def build_digest_features_block(features_list: List[Dict[str, Any]]) -> str:
    """棋譜全体の特徴量サマリーをダイジェストプロンプト用に構築."""
    if not features_list:
        return ""
    n = len(features_list)

    # フェーズ推移を検出
    phases = [f.get("phase", "midgame") for f in features_list]
    phase_transitions: List[str] = []
    for label in ("opening", "midgame", "endgame"):
        indices = [i for i, p in enumerate(phases) if p == label]
        if indices:
            jp = _PHASE_JP.get(label, label)
            phase_transitions.append(f"{jp}({indices[0]+1}〜{indices[-1]+1}手目)")

    # 攻守の平均推移 (序盤/中盤/終盤)
    thirds = max(1, n // 3)
    segments = [
        ("序盤", features_list[:thirds]),
        ("中盤", features_list[thirds:2 * thirds]),
        ("終盤", features_list[2 * thirds:]),
    ]

    def _avg(lst: List[Dict[str, Any]], key: str) -> int:
        vals = [f.get(key, 0) for f in lst]
        return int(sum(vals) / max(1, len(vals)))

    lines = ["\n【局面特徴量サマリー】"]
    if phase_transitions:
        lines.append(f"局面推移: {' → '.join(phase_transitions)}")

    for seg_name, seg_data in segments:
        if not seg_data:
            continue
        ks = _avg(seg_data, "king_safety")
        ap = _avg(seg_data, "attack_pressure")
        lines.append(
            f"{seg_name}: 玉の安全度={ks}/100({_describe_safety(ks)}), "
            f"攻めの圧力={ap}/100({_describe_pressure(ap)})"
        )

    # 攻守切り替わりポイント: attack_pressure が大きく変化した箇所
    pressure_vals = [f.get("attack_pressure", 0) for f in features_list]
    max_jump = 0
    jump_idx = 0
    for i in range(1, len(pressure_vals)):
        d = abs(pressure_vals[i] - pressure_vals[i - 1])
        if d > max_jump:
            max_jump = d
            jump_idx = i
    if max_jump >= 15:
        lines.append(f"攻守の切り替わり: {jump_idx + 1}手目付近（圧力変化 {max_jump}pt）")

    lines.append("上記を踏まえ、対局全体の流れを自然な文章で説明してください。")
    return "\n".join(lines)


def build_features_block(features: Dict[str, Any]) -> str:
    """特徴量辞書からプロンプト用の日本語ブロックを構築."""
    phase = _PHASE_JP.get(features.get("phase", ""), "不明")
    ks = features.get("king_safety", 0)
    ap = features.get("attack_pressure", 0)
    intent = features.get("move_intent")
    intent_jp = _INTENT_JP.get(intent, "") if intent else ""

    # 相手側の情報があれば (after に入っている)
    after = features.get("after") or {}
    opp_ks = after.get("king_safety")
    opp_ap = after.get("attack_pressure")

    lines = [
        "\n【局面の状況】",
        f"局面: {phase}",
        f"手番側の玉の安全度: {ks}/100（{_describe_safety(ks)}）",
    ]
    if opp_ks is not None:
        lines.append(f"相手側の玉の安全度: {opp_ks}/100（{_describe_safety(opp_ks)}）")
    lines.append(f"手番側の攻めの圧力: {ap}/100（{_describe_pressure(ap)}）")
    if opp_ap is not None:
        lines.append(f"相手側の攻めの圧力: {opp_ap}/100（{_describe_pressure(opp_ap)}）")
    if intent_jp:
        lines.append(f"この手の意図: {intent_jp}")
    lines.append("")
    lines.append("上記を踏まえ、「なぜこの手が指されたか」を局面の状況と結びつけて説明してください。")

    return "\n".join(lines)


async def _log_explanation(**kwargs: Any) -> None:
    """Fire-and-forget: log explanation to training logger."""
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "explanation",
            "input": {
                "sfen": kwargs.get("sfen"),
                "ply": kwargs.get("ply"),
                "candidates": kwargs.get("candidates"),
                "user_move": kwargs.get("user_move"),
                "delta_cp": kwargs.get("delta_cp"),
                "features": kwargs.get("features"),
            },
            "output": {
                "explanation": kwargs.get("explanation", ""),
                "model": kwargs.get("model_name", ""),
                "tokens": kwargs.get("tokens"),
                "style": kwargs.get("style"),
            },
        }
        # plan は features とは別フィールドに保持 (既存の学習スクリプトを壊さない)
        plan = kwargs.get("plan")
        if plan is not None:
            record["metadata"] = {"plan": plan}
        await training_logger.log_explanation(record)
    except Exception as e:
        _LOG.debug("[training_logger] explanation log failed: %s", e)


async def _log_digest(**kwargs: Any) -> None:
    """Fire-and-forget: log digest to training logger."""
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "digest",
            "input": {
                "total_moves": kwargs.get("total_moves"),
                "eval_history_len": kwargs.get("eval_history_len"),
                "notes_count": kwargs.get("notes_count"),
                "digest_features_count": kwargs.get("digest_features_count"),
            },
            "output": {
                "explanation": kwargs.get("explanation", ""),
                "model": kwargs.get("model_name", ""),
                "tokens": kwargs.get("tokens"),
                "source": kwargs.get("source", ""),
            },
        }
        await training_logger.log_digest(record)
    except Exception as e:
        _LOG.debug("[training_logger] digest log failed: %s", e)


class AIService:
    @staticmethod
    async def generate_position_comment(
        ply: int,
        sfen: str,
        candidates: List[Dict[str, Any]],
        user_move: Optional[str],
        delta_cp: Optional[int],
        features: Optional[Dict[str, Any]] = None,
        style: Optional[str] = None,
    ) -> str:
        """現在局面の将棋仙人コメントを生成する (レガシー)"""
        if not ensure_configured():
            return "APIキーが設定されていません。環境変数 GEMINI_API_KEY を確認してください。"

        # 形勢判定
        best_cp = None
        best_move_usi = ""
        if candidates:
            top = candidates[0]
            best_move_usi = top.get("move", "")
            if top.get("score_mate") is not None:
                best_cp = 30000 if top["score_mate"] >= 0 else -30000
            elif top.get("score_cp") is not None:
                best_cp = top["score_cp"]

        if best_cp is None:
            situation = "不明"
        elif abs(best_cp) > 2000:
            situation = "先手勝勢" if best_cp > 0 else "後手勝勢"
        elif abs(best_cp) > 800:
            situation = "先手優勢" if best_cp > 0 else "後手優勢"
        elif abs(best_cp) > 300:
            situation = "先手有利" if best_cp > 0 else "後手有利"
        else:
            situation = "互角"

        # 指し手の評価
        good_or_bad = "普通"
        if delta_cp is not None:
            if delta_cp <= -150:
                good_or_bad = "悪手"
            elif delta_cp <= -50:
                good_or_bad = "疑問手"
            elif delta_cp >= 150:
                good_or_bad = "好手"

        # 日本語ラベル
        turn = _detect_turn(sfen)
        best_move_jp = ShogiUtils.format_move_label(best_move_usi, turn) if best_move_usi else "なし"
        user_move_jp = ShogiUtils.format_move_label(user_move, turn) if user_move else "なし"

        # 特徴量ブロック
        features_block = build_features_block(features) if features else ""

        # スタイル選択
        if style is None and features:
            style = _get_style_selector().predict(features)
        style = style or "neutral"
        style_instruction = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["neutral"])

        prompt = f"""あなたは将棋の局面解説AIです。
以下の局面について、80文字以内で解説してください。

手数: {ply}手目
指された手: {user_move_jp}（この手の評価: {good_or_bad}）
AI推奨手: {best_move_jp}
形勢: {situation}
{features_block}
トーン: {style_instruction}
ルール:
- 80文字以内で完結すること
- 地の文のみ。箇条書き・見出し・記号禁止
- です/ます調
- 文章を途中で切らないこと"""

        # 短文生成には 2.5-flash-lite を固定（2.5-flash の thinking モードが tokens を消費するため）
        model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            generation_config=genai.types.GenerationConfig(max_output_tokens=300),
        )
        res = await model.generate_content_async(prompt)
        tokens_info = None
        try:
            if hasattr(res, 'usage_metadata') and res.usage_metadata:
                meta = res.usage_metadata
                tokens_info = {"prompt": meta.prompt_token_count, "completion": meta.candidates_token_count}
                _LOG.info(
                    "[TokenUsage] %s - input: %d, output: %d, total: %d",
                    "generate_position_comment",
                    meta.prompt_token_count,
                    meta.candidates_token_count,
                    meta.total_token_count,
                )
            else:
                _LOG.warning("[TokenUsage] %s - usage_metadata not available", "generate_position_comment")
        except Exception:
            _LOG.warning("[TokenUsage] %s - failed to read usage_metadata", "generate_position_comment")

        # Fire-and-forget training log
        asyncio.ensure_future(_log_explanation(
            sfen=sfen, ply=ply, candidates=candidates,
            user_move=user_move, delta_cp=delta_cp, features=features,
            explanation=res.text, model_name="gemini-2.5-flash-lite",
            tokens=tokens_info, style=style,
        ))

        return res.text

    @staticmethod
    async def generate_planned_comment(
        ply: int,
        sfen: str,
        candidates: List[Dict[str, Any]],
        user_move: Optional[str],
        delta_cp: Optional[int],
        style: Optional[str] = None,
        prev_moves: Optional[List[str]] = None,
        prev_features: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """構造化プラン経由で高品質な局面解説を生成する.

        Returns
        -------
        dict
            explanation: str - 生成されたテキスト
            style: str - 使用スタイル
            plan: dict - 構造化プラン (検証用)
        """
        from backend.api.services.explanation_planner import ExplanationPlanner

        # 1. 構造化プランを生成
        planner = ExplanationPlanner()
        plan = planner.build_plan(
            sfen=sfen,
            move=user_move,
            ply=ply,
            candidates=candidates,
            delta_cp=delta_cp,
            user_move=user_move,
            prev_moves=prev_moves,
            prev_features=prev_features,
        )

        # 2. LLMが使えない場合はプランからテンプレート生成
        if not ensure_configured():
            explanation = _build_planned_fallback(plan)
            return {
                "explanation": explanation,
                "style": style or "neutral",
                "plan": plan.to_dict(),
                "is_fallback": True,
            }

        # 3. スタイル選択
        if style is None:
            try:
                # プラン内の特徴量から推定
                features = extract_position_features(sfen=sfen, move=user_move, ply=ply)
                style = _get_style_selector().predict(features)
            except Exception:
                style = "neutral"
        style = style or "neutral"
        style_instruction = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["neutral"])

        # 4. 日本語ラベル
        turn = _detect_turn(sfen)
        user_move_jp = ShogiUtils.format_move_label(user_move, turn) if user_move else "なし"
        best_move_usi = candidates[0].get("move", "") if candidates else ""
        best_move_jp = ShogiUtils.format_move_label(best_move_usi, turn) if best_move_usi else "なし"

        # 5. 構造化プランをプロンプトに組み込む
        plan_block = plan.to_prompt_block()

        prompt = f"""あなたは将棋の局面解説AIです。
以下の構造化された局面情報に基づいて、80文字以内で解説してください。

手数: {ply}手目
指された手: {user_move_jp}
AI推奨手: {best_move_jp}

{plan_block}

トーン: {style_instruction}

ルール:
- 80文字以内で完結すること
- 上記の【注目ポイント】や【この手の理由】を中心に解説すること
- 【直前の流れ】があれば、対局の文脈を意識した解説にすること
- 地の文のみ。箇条書き・見出し・記号禁止
- です/ます調
- 文章を途中で切らないこと"""

        # 6. LLM呼び出し
        model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            generation_config=genai.types.GenerationConfig(max_output_tokens=300),
        )
        try:
            res = await model.generate_content_async(prompt)
        except Exception as e:
            _LOG.warning("[planned_comment] LLM call failed: %s", e)
            explanation = _build_planned_fallback(plan)
            return {
                "explanation": explanation,
                "style": style,
                "plan": plan.to_dict(),
                "is_fallback": True,
            }

        tokens_info = None
        try:
            if hasattr(res, 'usage_metadata') and res.usage_metadata:
                meta = res.usage_metadata
                tokens_info = {"prompt": meta.prompt_token_count, "completion": meta.candidates_token_count}
                _LOG.info(
                    "[TokenUsage] %s - input: %d, output: %d, total: %d",
                    "generate_planned_comment",
                    meta.prompt_token_count,
                    meta.candidates_token_count,
                    meta.total_token_count,
                )
        except Exception:
            pass

        # 7. 後処理: 改行・記号除去、80文字制限、空文字ガード
        raw_text = getattr(res, "text", None) or ""
        text = _sanitize_explanation(raw_text, plan)
        # fallback 判定: sanitize で fallback テキストに差し替えた場合
        used_fallback = (len(raw_text.strip()) < 5)

        # 8. Fire-and-forget training log
        # features は数値特徴量のまま維持、plan は別フィールド
        try:
            log_features = extract_position_features(sfen=sfen, move=user_move, ply=ply)
        except Exception:
            log_features = None
        asyncio.ensure_future(_log_explanation(
            sfen=sfen, ply=ply, candidates=candidates,
            user_move=user_move, delta_cp=delta_cp,
            features=log_features,
            explanation=text, model_name="gemini-2.5-flash-lite",
            tokens=tokens_info, style=style,
            plan=plan.to_dict(),
        ))

        return {
            "explanation": text,
            "style": style,
            "plan": plan.to_dict(),
            "is_fallback": used_fallback,
        }

    @staticmethod
    def build_plan(
        sfen: str,
        move: Optional[str] = None,
        ply: int = 0,
        candidates: Optional[List[Dict[str, Any]]] = None,
        delta_cp: Optional[int] = None,
        user_move: Optional[str] = None,
        prev_moves: Optional[List[str]] = None,
        prev_features: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """構造化プランのみを生成 (LLM不要、検証・デバッグ用)."""
        from backend.api.services.explanation_planner import ExplanationPlanner
        planner = ExplanationPlanner()
        plan = planner.build_plan(
            sfen=sfen, move=move, ply=ply,
            candidates=candidates, delta_cp=delta_cp,
            user_move=user_move, prev_moves=prev_moves,
            prev_features=prev_features,
        )
        return plan.to_dict()

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
        initial_turn: str = data.get("initial_turn") or "b"  # 'b'=先手先行, 'w'=後手先行
        digest_features: List[Dict[str, Any]] = data.get("digest_features") or []

        _LOG.info(
            "[digest] input rid=%s total_moves=%s notes_count=%s bioshogi=%s initial_turn=%s",
            request_id, total_moves, len(notes),
            "yes" if bioshogi else "no",
            initial_turn,
        )

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
            # delta_cp は手番プレイヤー視点: 負=悪手, 正=好手
            # initial_turn='b': 奇数ply=先手(▲), 偶数ply=後手(△)
            # initial_turn='w': 奇数ply=後手(△), 偶数ply=先手(▲)
            notes_block = ""
            if notes:
                def _is_sente_ply(ply: int) -> bool:
                    return (ply % 2 != 0) if initial_turn == "b" else (ply % 2 == 0)

                valid_notes = [n for n in notes if isinstance(n.get("delta_cp"), (int, float))]
                notable = sorted(valid_notes, key=lambda n: abs(n["delta_cp"]), reverse=True)[:5]
                if notable:
                    lines = []
                    for n in notable:
                        ply = n["ply"]
                        d = int(n["delta_cp"])
                        is_sente = _is_sente_ply(ply)
                        turn = "b" if is_sente else "w"
                        move_jp = ShogiUtils.format_move_label(n.get("move", ""), turn)
                        qualifier = "好手" if d >= 150 else ("悪手" if d <= -150 else "普通")
                        lines.append(f"  - {ply}手目 {move_jp} (Δ{d:+d}cp / {qualifier})")
                    notes_block = "\n【注目手（評価値変動が大きかった手）】\n" + "\n".join(lines) + "\n"

            # --- digest features block ---
            digest_feat_block = build_digest_features_block(digest_features)

            prompt = f"""以下の3点を含む200文字以内の文章を出力せよ。
1. 先手と後手の戦型
2. 最大の転換点（何手目の何の手）
3. 勝者と勝因

{sente_name}（先手）vs {gote_name}（後手）、{total_moves}手
評価値推移: {', '.join(eval_summary)}
{bio_block}{notes_block}{digest_feat_block}
例: 石田流 vs 棒金の一局。42手目△7三(82)が悪手となり形勢逆転。先手が中盤以降の優勢を維持し73手で勝利した。

見出し・箇条書き・挨拶文・装飾すべて禁止。地の文のみ。
【厳守】200文字以内。文章を途中で切らず最後まで完結させること。"""
            # 短文生成には 2.5-flash-lite を固定（2.5-flash の thinking モードが tokens を消費するため）
            digest_model = "gemini-2.5-flash-lite"
            prompt_size = len(prompt)
            t0 = time.time()
            _LOG.info("[digest] llm.start rid=%s model=%s prompt_chars=%s", request_id, digest_model, prompt_size)
            model = genai.GenerativeModel(
                digest_model,
                generation_config=genai.types.GenerationConfig(max_output_tokens=1500),
            )
            response = await model.generate_content_async(prompt)
            elapsed_ms = int((time.time() - t0) * 1000)
            _LOG.info("[digest] llm.ok rid=%s ms=%s", request_id, elapsed_ms)
            digest_tokens = None
            try:
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    meta = response.usage_metadata
                    digest_tokens = {"prompt": meta.prompt_token_count, "completion": meta.candidates_token_count}
                    _LOG.info(
                        "[TokenUsage] %s - input: %d, output: %d, total: %d",
                        "generate_game_digest",
                        meta.prompt_token_count,
                        meta.candidates_token_count,
                        meta.total_token_count,
                    )
                else:
                    _LOG.warning("[TokenUsage] %s - usage_metadata not available", "generate_game_digest")
            except Exception:
                _LOG.warning("[TokenUsage] %s - failed to read usage_metadata", "generate_game_digest")
            explanation = response.text

            # Fire-and-forget training log
            asyncio.ensure_future(_log_digest(
                total_moves=total_moves, eval_history_len=len(eval_history),
                notes_count=len(notes), digest_features_count=len(digest_features),
                explanation=explanation, model_name=digest_model,
                tokens=digest_tokens, source="llm",
            ))

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


_HEADING_RE = re.compile(r"【[^】]*】")
_BULLET_RE = re.compile(r"^[\s]*[-・*•▪]\s*", re.MULTILINE)
_HASH_RE = re.compile(r"^#+\s*", re.MULTILINE)


def _sanitize_explanation(raw: str, plan) -> str:
    """LLM出力を後処理して安全な解説テキストにする.

    - 改行・箇条書き・見出し記号を除去
    - 80文字以内に収める
    - 空文字や不正出力時は fallback を返す
    """
    text = raw.strip()

    # 【見出し】除去
    text = _HEADING_RE.sub("", text)
    # 箇条書き記号除去 (改行がまだ残っている段階で適用)
    text = _BULLET_RE.sub("", text)
    # Markdown見出し除去
    text = _HASH_RE.sub("", text)
    # 改行 → スペースに統合
    text = text.replace("\n", " ").replace("\r", "")
    # 連続スペースを単一に
    text = re.sub(r"\s{2,}", " ", text).strip()

    # 空文字・極端に短い場合は fallback
    if len(text) < 5:
        return _build_planned_fallback(plan)

    # 80文字制限
    if len(text) > 80:
        # 最後の句点位置で切る
        cut = text[:80]
        last_period = max(cut.rfind("。"), cut.rfind("です"), cut.rfind("ます"))
        if last_period > 20:
            text = text[: last_period + 1]
            # "です" / "ます" で切った場合に句点を補う
            if not text.endswith("。"):
                text += "。"
        else:
            text = text[:77] + "..."

    return text


def _build_planned_fallback(plan) -> str:
    """LLM不使用時・エラー時にプランから自然な解説を生成."""
    # surface_reason を軸に自然文を構成
    if plan.surface_reason:
        base = plan.surface_reason
        # 句点で終わっていなければ追加
        if not base.endswith("。"):
            base += "。"
        # topic_keyword を前置して厚みを出す
        if plan.topic_keyword and plan.topic_keyword not in base:
            text = f"{plan.topic_keyword}。{base}"
        else:
            text = base
    elif plan.topic_keyword:
        text = f"{plan.topic_keyword}です。"
    else:
        text = "局面を進める一手です。"

    # 80文字制限
    if len(text) > 80:
        text = text[:77] + "..."

    return text


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
