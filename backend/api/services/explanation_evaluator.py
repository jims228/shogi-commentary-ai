"""ルールベースの解説品質評価器.

Gemini API不使用。pure Python で解説テキストの品質を定量評価する。
将来的にMLベースの評価器に置き換え可能なインターフェースを提供。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 定数: 将棋用語・パターン
# ---------------------------------------------------------------------------
_PIECE_NAMES = {"歩", "香", "桂", "銀", "金", "角", "飛", "玉", "王",
                "と", "成香", "成桂", "成銀", "馬", "龍", "竜"}

_STRATEGY_TERMS = {
    "居飛車", "振り飛車", "中飛車", "四間飛車", "三間飛車", "向かい飛車",
    "矢倉", "美濃", "穴熊", "雁木", "角換わり", "相掛かり", "横歩取り",
    "石田流", "藤井システム", "棒銀", "棒金", "右四間", "急戦", "持久戦",
}

_ATTACK_WORDS = {"攻め", "攻撃", "狙い", "迫る", "寄せ", "王手", "詰み",
                 "突破", "仕掛け", "殺到", "踏み込"}

_DEFENSE_WORDS = {"守り", "守る", "受け", "固める", "囲い", "備え", "耐え",
                  "しのぐ", "受ける", "防ぐ", "安定"}

_OPENING_WORDS = {"序盤", "駒組み", "陣形", "構え", "布陣", "展開"}
_ENDGAME_WORDS = {"終盤", "寄せ", "詰み", "入玉", "必至", "詰めろ", "秒読み"}

_CONNECTORS = {"しかし", "一方", "また", "そして", "ただし", "そのため",
               "なぜなら", "つまり", "さらに", "ところが", "むしろ"}

_MOVE_PATTERN = re.compile(r"[▲△☗☖][１-９1-9一二三四五六七八九]")
_NUMBER_PATTERN = re.compile(r"\d+[点手目cp]")


# ---------------------------------------------------------------------------
# 文分割ヘルパー
# ---------------------------------------------------------------------------
def _split_sentences(text: str) -> List[str]:
    """句点・改行で文を分割."""
    parts = re.split(r"[。\n]", text)
    return [s.strip() for s in parts if s.strip()]


# ---------------------------------------------------------------------------
# 1. context_relevance: 文脈反映度 (0-100, weight=0.30)
# ---------------------------------------------------------------------------
def score_context_relevance(
    text: str,
    features: Optional[Dict[str, Any]] = None,
) -> int:
    """解説が局面の状況を正しく反映しているか."""
    if not features:
        return 50  # 特徴量なしは中立

    score = 70  # 基準点

    phase = features.get("phase", "")
    intent = features.get("move_intent", "")

    # --- phase 整合性 ---
    if phase == "opening":
        # 序盤なのに終盤語があれば減点
        for w in _ENDGAME_WORDS:
            if w in text:
                score -= 10
                break
        # 序盤語があれば加点
        for w in _OPENING_WORDS:
            if w in text:
                score += 10
                break

    elif phase == "endgame":
        # 終盤なのに序盤語があれば減点
        for w in _OPENING_WORDS:
            if w in text:
                score -= 10
                break
        for w in _ENDGAME_WORDS:
            if w in text:
                score += 10
                break

    elif phase == "midgame":
        # 中盤は許容範囲が広い → 軽い加点のみ
        if "中盤" in text:
            score += 5

    # --- intent 整合性 ---
    if intent == "attack":
        has_attack = any(w in text for w in _ATTACK_WORDS)
        if has_attack:
            score += 15
        else:
            score -= 10

    elif intent == "defense":
        has_defense = any(w in text for w in _DEFENSE_WORDS)
        if has_defense:
            score += 15
        else:
            score -= 10

    elif intent == "exchange":
        if "交換" in text or "取" in text:
            score += 10

    elif intent == "sacrifice":
        if "犠牲" in text or "捨て" in text or "タダ" in text:
            score += 10

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# 2. naturalness: 自然さ (0-100, weight=0.25)
# ---------------------------------------------------------------------------
def score_naturalness(text: str) -> int:
    """文の多様性・構造の自然さを評価."""
    sentences = _split_sentences(text)
    if not sentences:
        return 0

    score = 60  # 基準点

    # --- 文末の多様性 ---
    endings = []
    for s in sentences:
        if s.endswith("です"):
            endings.append("です")
        elif s.endswith("ます"):
            endings.append("ます")
        elif s.endswith("した"):
            endings.append("した")
        elif s.endswith("でしょう"):
            endings.append("でしょう")
        elif s.endswith("ません"):
            endings.append("ません")
        else:
            endings.append("other")

    if len(endings) >= 2:
        unique_ratio = len(set(endings)) / len(endings)
        if unique_ratio >= 0.5:
            score += 10
        elif unique_ratio < 0.3:
            score -= 15  # 同じ文末が多すぎ

    # --- 平均文長チェック ---
    avg_len = sum(len(s) for s in sentences) / len(sentences)
    if 30 <= avg_len <= 80:
        score += 10  # 理想範囲
    elif avg_len < 10:
        score -= 20  # 短すぎ
    elif avg_len > 120:
        score -= 15  # 長すぎ

    # --- 同構造の繰り返し検出 ---
    if len(sentences) >= 2:
        repeated = 0
        for i in range(1, len(sentences)):
            # 先頭5文字が同じなら同構造とみなす
            if len(sentences[i]) >= 5 and len(sentences[i - 1]) >= 5:
                if sentences[i][:5] == sentences[i - 1][:5]:
                    repeated += 1
        if repeated >= 2:
            score -= 15

    # --- 接続詞の使用 → 加点 ---
    connector_count = sum(1 for c in _CONNECTORS if c in text)
    score += min(10, connector_count * 5)

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# 3. informativeness: 情報量 (0-100, weight=0.25)
# ---------------------------------------------------------------------------
def score_informativeness(text: str) -> int:
    """将棋用語・具体情報の密度を評価."""
    score = 40  # 基準点

    # --- 駒名の使用 ---
    piece_count = sum(1 for p in _PIECE_NAMES if p in text)
    score += min(15, piece_count * 3)

    # --- 戦型・囲い名の使用 ---
    strategy_count = sum(1 for s in _STRATEGY_TERMS if s in text)
    score += min(15, strategy_count * 5)

    # --- 具体的な指し手への言及 ---
    move_matches = _MOVE_PATTERN.findall(text)
    score += min(15, len(move_matches) * 5)

    # --- 数値情報の引用 ---
    number_matches = _NUMBER_PATTERN.findall(text)
    score += min(10, len(number_matches) * 5)

    # --- 専門用語の羅列だけで文としての体をなしていない場合は減点 ---
    total_terms = piece_count + strategy_count + len(move_matches)
    sentences = _split_sentences(text)
    if sentences and total_terms > len(sentences) * 3:
        score -= 10  # 用語詰め込みすぎ

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# 4. readability: 読みやすさ (0-100, weight=0.20)
# ---------------------------------------------------------------------------
def score_readability(text: str) -> int:
    """文数・文字数・括弧対応などの形式的品質を評価."""
    if not text.strip():
        return 0

    score = 60  # 基準点
    total_len = len(text)
    sentences = _split_sentences(text)
    n_sentences = len(sentences)

    # --- 総文字数 ---
    if 50 <= total_len <= 200:
        score += 15  # 理想範囲
    elif total_len < 20:
        score -= 25  # 短すぎ
    elif total_len > 300:
        score -= 10  # 長め

    # --- 文数 ---
    if 2 <= n_sentences <= 5:
        score += 10
    elif n_sentences == 1:
        score -= 5
    elif n_sentences > 8:
        score -= 10

    # --- 括弧の対応 ---
    for open_b, close_b in [("（", "）"), ("(", ")"), ("「", "」"), ("【", "】")]:
        if text.count(open_b) != text.count(close_b):
            score -= 10
            break

    # --- 不完全な文の検出（末尾が中途半端） ---
    stripped = text.rstrip()
    if stripped and stripped[-1] not in "。！？!?）)」】":
        score -= 10  # 文が途切れている可能性

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# 総合評価
# ---------------------------------------------------------------------------
_WEIGHTS = {
    "context_relevance": 0.30,
    "naturalness": 0.25,
    "informativeness": 0.25,
    "readability": 0.20,
}


def evaluate_explanation(
    text: str,
    features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """解説テキストの品質を総合評価する.

    Returns
    -------
    dict
        scores: {context_relevance, naturalness, informativeness, readability}
        total: 重み付き総合スコア (0-100)
    """
    scores = {
        "context_relevance": score_context_relevance(text, features),
        "naturalness": score_naturalness(text),
        "informativeness": score_informativeness(text),
        "readability": score_readability(text),
    }
    total = sum(scores[k] * _WEIGHTS[k] for k in _WEIGHTS)
    return {
        "scores": scores,
        "total": round(total, 1),
    }


# ---------------------------------------------------------------------------
# バッチ評価ユーティリティ
# ---------------------------------------------------------------------------
def evaluate_training_logs(log_dir: str) -> Dict[str, Any]:
    """training_logs の全レコードを評価し、統計を返す.

    Returns
    -------
    dict
        total_records, avg_total, avg_scores (per axis),
        low_quality_count (total < 40),
        by_phase, by_intent (phase/intent 別の平均)
    """
    if not os.path.isdir(log_dir):
        return {"total_records": 0}

    records: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(log_dir)):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(log_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    explanation = (obj.get("output") or {}).get("explanation", "")
                    features = (obj.get("input") or {}).get("features")
                    if explanation:
                        records.append({"explanation": explanation, "features": features})
        except Exception:
            continue

    if not records:
        return {"total_records": 0}

    all_evals: List[Dict[str, Any]] = []
    by_phase: Dict[str, List[float]] = {}
    by_intent: Dict[str, List[float]] = {}

    for r in records:
        ev = evaluate_explanation(r["explanation"], r["features"])
        all_evals.append(ev)

        phase = (r["features"] or {}).get("phase", "unknown")
        intent = (r["features"] or {}).get("move_intent", "unknown")

        by_phase.setdefault(phase, []).append(ev["total"])
        by_intent.setdefault(intent, []).append(ev["total"])

    totals = [e["total"] for e in all_evals]
    avg_total = round(sum(totals) / len(totals), 1)
    low_quality = sum(1 for t in totals if t < 40)

    avg_scores = {}
    for axis in _WEIGHTS:
        vals = [e["scores"][axis] for e in all_evals]
        avg_scores[axis] = round(sum(vals) / len(vals), 1)

    phase_avg = {k: round(sum(v) / len(v), 1) for k, v in by_phase.items()}
    intent_avg = {k: round(sum(v) / len(v), 1) for k, v in by_intent.items()}

    return {
        "total_records": len(records),
        "avg_total": avg_total,
        "avg_scores": avg_scores,
        "low_quality_count": low_quality,
        "by_phase": phase_avg,
        "by_intent": intent_avg,
    }
