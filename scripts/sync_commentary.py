#!/usr/bin/env python3
"""文字起こしテキストと棋譜を突き合わせて局面同期するスクリプト.

3段階アルゴリズム:
  Stage 1: ルールベースマッチング（指し手名・手数で直接照合）
  Stage 2: AI補完（Gemini API で未マッチセグメントを推定）
  Stage 3: フィルタリング（雑談・CM等を除外）

Gemini API なしでも Stage 1 のみで動作する。

Usage:
    python3 scripts/sync_commentary.py \
      data/transcripts/game01_transcript.json \
      data/parsed/game01_moves.json \
      --output data/synced/game01_synced.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# 将棋用語パターン
# ---------------------------------------------------------------------------
_PIECE_NAMES = (
    "歩", "香", "桂", "銀", "金", "角", "飛", "玉", "王",
    "と", "成香", "成桂", "成銀", "馬", "龍", "竜",
)

_STRATEGY_TERMS = (
    "矢倉", "美濃", "穴熊", "振り飛車", "居飛車", "中飛車",
    "四間飛車", "三間飛車", "向かい飛車", "藤井システム",
    "角換わり", "横歩取り", "相掛かり", "雁木",
)

_SHOGI_TERMS = _PIECE_NAMES + _STRATEGY_TERMS + (
    "王手", "詰み", "詰めろ", "必至", "寄せ",
    "手筋", "好手", "悪手", "疑問手", "妙手",
    "先手", "後手", "形勢", "評価値", "最善手",
    "受け", "攻め", "手番", "持ち駒", "駒得", "駒損",
)

# 指し手パターン (数字+段+駒名)
_MOVE_MENTION_RE = re.compile(
    r"([１-９1-9一二三四五六七八九])([一二三四五六七八九])"
    r"(歩|香|桂|銀|金|角|飛|玉|王|と|成香|成桂|成銀|馬|龍|竜)"
)

# 「同X」パターン
_SAME_MOVE_RE = re.compile(
    r"同\s*(歩|香|桂|銀|金|角|飛|玉|王|と|成香|成桂|成銀|馬|龍|竜)"
)

# 手数直接指定
_PLY_DIRECT_RE = re.compile(r"(\d+)\s*手目")

# 漢数字→int
_KANJI_TO_INT = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_ZEN_TO_HAN = {
    "１": "1", "２": "2", "３": "3", "４": "4", "５": "5",
    "６": "6", "７": "7", "８": "8", "９": "9",
}

# コメンタリータイプ推定キーワード
_TYPE_KEYWORDS = {
    "move_evaluation": ["好手", "悪手", "疑問手", "妙手", "最善", "次善"],
    "position_analysis": ["形勢", "評価値", "優勢", "劣勢", "互角", "有利"],
    "tactical": ["手筋", "王手", "詰み", "詰めろ", "必至", "寄せ"],
    "strategic": ["陣形", "玉の固さ", "バランス", "模様", "厚み"],
    "opening_theory": ["定跡", "研究", "前例", "棋譜"],
}


# ---------------------------------------------------------------------------
# ルールベースマッチング (Stage 1)
# ---------------------------------------------------------------------------

def _normalize_file(ch: str) -> Optional[int]:
    """筋文字をintに変換."""
    if ch in _ZEN_TO_HAN:
        return int(_ZEN_TO_HAN[ch])
    if ch in _KANJI_TO_INT:
        return _KANJI_TO_INT[ch]
    if ch.isdigit():
        return int(ch)
    return None


def _normalize_rank(ch: str) -> Optional[int]:
    """段文字をintに変換."""
    return _KANJI_TO_INT.get(ch)


def _build_move_index(moves: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """棋譜の手からマッチング用インデックスを構築.

    Returns
    -------
    dict
        {"7六歩": [1], "3四歩": [2, 10], ...} のような辞書
        キーは正規化された指し手表記
    """
    index: Dict[str, List[int]] = {}
    for mv in moves:
        ply = mv["ply"]
        move_ja = mv.get("move_ja", "")
        if move_ja:
            # 正規化: 全角数字→半角 (キーとして)
            normalized = move_ja
            for z, h in _ZEN_TO_HAN.items():
                normalized = normalized.replace(z, h)
            index.setdefault(normalized, []).append(ply)
            # 元の表記でもインデックス
            if normalized != move_ja:
                index.setdefault(move_ja, []).append(ply)
    return index


def _match_segment_rule_based(
    text: str,
    move_index: Dict[str, List[int]],
    moves: List[Dict[str, Any]],
    time_context: Optional[Tuple[int, int]] = None,
) -> Optional[Tuple[int, float, str]]:
    """ルールベースで解説テキストを局面にマッチ.

    Returns
    -------
    (ply, confidence, reason) | None
    """
    # 手数直接指定
    ply_match = _PLY_DIRECT_RE.search(text)
    if ply_match:
        ply = int(ply_match.group(1))
        # 範囲チェック
        if any(m["ply"] == ply for m in moves):
            return (ply, 1.0, f"direct_ply_mention:{ply}")

    # 指し手メンション
    move_mentions = _MOVE_MENTION_RE.findall(text)
    if move_mentions:
        best_ply = None
        best_conf = 0.0
        for file_ch, rank_ch, piece in move_mentions:
            f = _normalize_file(file_ch)
            r = _normalize_rank(rank_ch)
            if f is None or r is None:
                continue
            # 正規化キーで検索
            key = f"{f}{rank_ch}{piece}"
            candidates = move_index.get(key, [])
            if not candidates:
                # 全角筋でも試す
                for z, h in _ZEN_TO_HAN.items():
                    if h == str(f):
                        alt_key = f"{z}{rank_ch}{piece}"
                        candidates = move_index.get(alt_key, [])
                        if candidates:
                            break
            if candidates:
                # 時間コンテキストがあれば最も近い手を選択
                if time_context and len(candidates) > 1:
                    ctx_ply = (time_context[0] + time_context[1]) // 2
                    ply = min(candidates, key=lambda p: abs(p - ctx_ply))
                else:
                    ply = candidates[0]
                conf = 1.0 if len(candidates) == 1 else 0.9
                if conf > best_conf:
                    best_ply = ply
                    best_conf = conf
        if best_ply is not None:
            return (best_ply, best_conf, f"move_mention:{best_ply}")

    # 「同X」パターン
    same_match = _SAME_MOVE_RE.search(text)
    if same_match:
        piece = same_match.group(1)
        for mv in moves:
            if mv.get("is_same") and piece in mv.get("move_ja", ""):
                return (mv["ply"], 0.9, f"same_move:{mv['ply']}")

    return None


# ---------------------------------------------------------------------------
# AI補完 (Stage 2)
# ---------------------------------------------------------------------------

def _ai_match_segments(
    unmatched: List[Dict[str, Any]],
    matched_context: List[Dict[str, Any]],
    moves: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Gemini API で未マッチセグメントの局面を推定.

    Parameters
    ----------
    unmatched : list
        未マッチのセグメント
    matched_context : list
        マッチ済みのセグメント (時間順)
    moves : list
        棋譜の手リスト

    Returns
    -------
    list
        AI推定結果を付与したセグメントリスト
    """
    try:
        from backend.api.utils.gemini_client import ensure_configured, get_model_name
        import google.generativeai as genai
    except ImportError:
        return []

    key = ensure_configured()
    if not key:
        return []

    model_name = get_model_name()
    model = genai.GenerativeModel(model_name)

    results = []
    for seg in unmatched:
        # 前後のマッチ済みコンテキストを探す
        before_ctx = None
        after_ctx = None
        for mc in matched_context:
            if mc["timestamp_end"] <= seg["start"]:
                before_ctx = mc
            if mc["timestamp_start"] >= seg["end"] and after_ctx is None:
                after_ctx = mc
                break

        context_str = ""
        ply_range_start = 1
        ply_range_end = len(moves)

        if before_ctx:
            context_str += f"直前の解説: {before_ctx['ply']}手目（{before_ctx.get('move_ja', '')}）\n"
            ply_range_start = max(1, before_ctx["ply"] - 2)
        if after_ctx:
            context_str += f"直後の解説: {after_ctx['ply']}手目（{after_ctx.get('move_ja', '')}）\n"
            ply_range_end = min(len(moves), after_ctx["ply"] + 2)

        # 該当範囲の手順を抽出
        range_moves = [
            f"{m['ply']}. {m.get('move_ja', '')}"
            for m in moves
            if ply_range_start <= m["ply"] <= ply_range_end
        ]

        prompt = (
            "以下の将棋解説テキストが、棋譜のどの局面（何手目）に"
            "対する解説かを判定してください。\n\n"
            f"解説テキスト: \"{seg['text']}\"\n"
            f"前後の文脈: {context_str}"
            f"棋譜の該当範囲: {', '.join(range_moves)}\n\n"
            "回答はJSON形式のみ（余計な説明不要）:\n"
            '{\"ply\": <手数>, \"confidence\": <0.0-1.0>, \"reason\": \"<理由>\"}'
        )

        try:
            response = model.generate_content(prompt)
            resp_text = response.text.strip()
            # JSON部分を抽出
            json_match = re.search(r"\{.*\}", resp_text, re.DOTALL)
            if json_match:
                ai_result = json.loads(json_match.group())
                ply = ai_result.get("ply")
                confidence = ai_result.get("confidence", 0.5)
                reason = ai_result.get("reason", "ai_inference")
                if ply and any(m["ply"] == ply for m in moves):
                    results.append({
                        **seg,
                        "ply": ply,
                        "confidence": min(confidence, 0.85),
                        "match_method": "ai",
                        "ai_reason": reason,
                    })
        except Exception:
            continue

    return results


# ---------------------------------------------------------------------------
# フィルタリング (Stage 3)
# ---------------------------------------------------------------------------

def _has_shogi_terms(text: str) -> bool:
    """テキストに将棋用語が含まれるか."""
    for term in _SHOGI_TERMS:
        if term in text:
            return True
    return False


def _classify_commentary_type(text: str) -> str:
    """解説テキストのタイプを推定."""
    for ctype, keywords in _TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return ctype
    if _MOVE_MENTION_RE.search(text):
        return "move_evaluation"
    return "general"


def _filter_segment(
    text: str,
    has_match: bool,
    neighbor_matched: bool,
) -> Tuple[bool, str]:
    """セグメントが将棋解説として有効かフィルタリング.

    Returns
    -------
    (is_valid, filter_reason)
    """
    # 既にマッチ済みなら有効
    if has_match:
        return True, ""

    # 短すぎるセグメント
    if len(text) < 5:
        return False, "too_short"

    # 将棋用語チェック
    if _has_shogi_terms(text):
        return True, ""

    # 前後にマッチしたセグメントがあればコンテキストで有効
    if neighbor_matched and len(text) >= 10:
        return True, ""

    return False, "no_shogi_terms"


# ---------------------------------------------------------------------------
# メインパイプライン
# ---------------------------------------------------------------------------

def sync_commentary(
    transcript: Dict[str, Any],
    parsed_kifu: Dict[str, Any],
    use_ai: bool = True,
) -> Dict[str, Any]:
    """文字起こしと棋譜を同期.

    Parameters
    ----------
    transcript : dict
        文字起こしJSON (transcribe_commentary.py の出力)
    parsed_kifu : dict
        棋譜パース結果 (kif_parser.py の出力)
    use_ai : bool
        Stage 2 (AI補完) を使用するか

    Returns
    -------
    dict
        同期結果
    """
    segments = transcript.get("segments", [])
    moves = parsed_kifu.get("moves", [])
    move_index = _build_move_index(moves)

    # ply → move_ja マップ
    ply_to_move: Dict[int, str] = {
        m["ply"]: m.get("move_ja", "") for m in moves
    }

    # Stage 1: ルールベースマッチング
    matched: List[Dict[str, Any]] = []
    unmatched_segs: List[Dict[str, Any]] = []
    matched_indices: set = set()

    for seg in segments:
        text = seg.get("text", "")
        result = _match_segment_rule_based(text, move_index, moves)
        if result:
            ply, confidence, reason = result
            matched.append({
                "ply": ply,
                "move_ja": ply_to_move.get(ply, ""),
                "timestamp_start": seg.get("start", 0),
                "timestamp_end": seg.get("end", 0),
                "text": text,
                "match_method": "rule_based",
                "confidence": confidence,
                "is_explanation": True,
                "commentary_type": _classify_commentary_type(text),
            })
            matched_indices.add(seg.get("id", -1))
        else:
            unmatched_segs.append({
                "id": seg.get("id"),
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": text,
            })

    # Stage 2: AI補完
    ai_matched: List[Dict[str, Any]] = []
    still_unmatched: List[Dict[str, Any]] = []

    if use_ai and unmatched_segs:
        ai_results = _ai_match_segments(unmatched_segs, matched, moves)
        ai_matched_ids = {r.get("id") for r in ai_results}

        for r in ai_results:
            ai_matched.append({
                "ply": r["ply"],
                "move_ja": ply_to_move.get(r["ply"], ""),
                "timestamp_start": r["start"],
                "timestamp_end": r["end"],
                "text": r["text"],
                "match_method": "ai",
                "confidence": r["confidence"],
                "is_explanation": True,
                "commentary_type": _classify_commentary_type(r["text"]),
            })

        still_unmatched = [
            s for s in unmatched_segs if s.get("id") not in ai_matched_ids
        ]
    else:
        still_unmatched = unmatched_segs

    # Stage 3: フィルタリング
    all_matched = sorted(
        matched + ai_matched,
        key=lambda x: x.get("timestamp_start", 0),
    )

    # マッチ済みタイムスタンプセット (近傍判定用)
    matched_times = {(m["timestamp_start"], m["timestamp_end"]) for m in all_matched}

    unmatched_filtered: List[Dict[str, Any]] = []
    for seg in still_unmatched:
        start = seg["start"]
        end = seg["end"]
        # 前後にマッチしたセグメントがあるか
        neighbor_matched = any(
            abs(m["timestamp_end"] - start) < 5.0
            or abs(m["timestamp_start"] - end) < 5.0
            for m in all_matched
        )

        is_valid, reason = _filter_segment(
            seg["text"],
            has_match=False,
            neighbor_matched=neighbor_matched,
        )

        if not is_valid:
            unmatched_filtered.append({
                "timestamp_start": start,
                "timestamp_end": end,
                "text": seg["text"],
                "filter_reason": reason,
            })
        else:
            # 将棋用語ありだが局面特定できず → unmatchedに残す
            unmatched_filtered.append({
                "timestamp_start": start,
                "timestamp_end": end,
                "text": seg["text"],
                "filter_reason": "no_ply_match",
            })

    # 統計
    total = len(segments)
    n_rule = len(matched)
    n_ai = len(ai_matched)
    n_matched = n_rule + n_ai
    n_unmatched = len(unmatched_filtered)

    return {
        "source_video": transcript.get("source", ""),
        "source_kifu": "",
        "synced_comments": all_matched,
        "unmatched_segments": unmatched_filtered,
        "stats": {
            "total_segments": total,
            "matched_segments": n_matched,
            "unmatched_segments": n_unmatched,
            "match_rate": round(n_matched / total, 2) if total > 0 else 0.0,
            "rule_based_matches": n_rule,
            "ai_matches": n_ai,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="文字起こしテキストと棋譜を局面同期"
    )
    parser.add_argument(
        "transcript", help="文字起こしJSON (transcribe_commentary.py 出力)"
    )
    parser.add_argument(
        "kifu", help="棋譜パース結果JSON (kif_parser.py 出力)"
    )
    parser.add_argument(
        "--output", "-o",
        help="出力JSONファイル (デフォルト: data/synced/<transcript名>_synced.json)",
    )
    parser.add_argument(
        "--no-ai", action="store_true",
        help="AI補完 (Stage 2) を使用しない",
    )
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    kifu_path = Path(args.kifu)

    if not transcript_path.exists():
        print(f"Error: file not found: {args.transcript}", file=sys.stderr)
        sys.exit(1)
    if not kifu_path.exists():
        print(f"Error: file not found: {args.kifu}", file=sys.stderr)
        sys.exit(1)

    with open(transcript_path, encoding="utf-8") as f:
        transcript = json.load(f)
    with open(kifu_path, encoding="utf-8") as f:
        parsed_kifu = json.load(f)

    result = sync_commentary(
        transcript,
        parsed_kifu,
        use_ai=not args.no_ai,
    )
    result["source_kifu"] = str(kifu_path.name)

    # 出力先決定
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            _PROJECT_ROOT / "data" / "synced"
            / f"{transcript_path.stem}_synced.json"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    stats = result["stats"]
    print(f"Total segments: {stats['total_segments']}")
    print(f"Matched: {stats['matched_segments']} "
          f"(rule: {stats['rule_based_matches']}, ai: {stats['ai_matches']})")
    print(f"Unmatched: {stats['unmatched_segments']}")
    print(f"Match rate: {stats['match_rate']:.0%}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
