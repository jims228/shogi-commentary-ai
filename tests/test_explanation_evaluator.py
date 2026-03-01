"""Tests for backend.api.services.explanation_evaluator."""
from __future__ import annotations

import json
import os
from unittest import mock

import pytest

from backend.api.services.explanation_evaluator import (
    evaluate_explanation,
    evaluate_training_logs,
    score_context_relevance,
    score_naturalness,
    score_informativeness,
    score_readability,
)


# ===== テスト用解説文 =====
GOOD_EXPLANATION = (
    "中盤の攻め合いの中、▲５五角が相手玉の守りを崩す好手です。"
    "しかし後手も△３三銀で受けに回り、形勢は互角に近い約50点差となっています。"
)

TEMPLATE_EXPLANATION = (
    "この手は攻めの手です。この手は守りの手です。この手は受けの手です。"
    "この手は良い手です。この手は悪い手です。"
)

PHASE_MISMATCH_OPENING = (
    "終盤の寄せが見事で、詰みに向かう手順がきれいです。"
)

PHASE_MISMATCH_ENDGAME = (
    "序盤の駒組みが丁寧で、陣形がしっかりしています。"
)

SHORT_EXPLANATION = "良い手。"

LONG_EXPLANATION = "あ" * 350

NO_TERMS_EXPLANATION = (
    "これはとても良い手だと思います。状況が大きく変わりました。"
    "次の展開が楽しみですね。がんばりましょう。"
)

INFORMATIVE_EXPLANATION = (
    "▲７六歩から居飛車の駒組みが始まり、矢倉の陣形を目指しています。"
    "評価値は約120点で先手がやや有利です。"
)


class TestContextRelevance:
    def test_no_features(self):
        """特徴量なしは中立スコア."""
        score = score_context_relevance("何かの解説", None)
        assert score == 50

    def test_opening_with_opening_words(self):
        """序盤で序盤語 → 高スコア."""
        features = {"phase": "opening", "move_intent": "development"}
        score = score_context_relevance("序盤の駒組みが進んでいます。", features)
        assert score >= 70

    def test_opening_with_endgame_words(self):
        """序盤なのに終盤語 → 低スコア."""
        features = {"phase": "opening", "move_intent": "development"}
        score = score_context_relevance(PHASE_MISMATCH_OPENING, features)
        assert score < 70

    def test_endgame_with_opening_words(self):
        """終盤なのに序盤語 → 低スコア."""
        features = {"phase": "endgame", "move_intent": "attack"}
        score = score_context_relevance(PHASE_MISMATCH_ENDGAME, features)
        assert score < 70

    def test_attack_intent_with_attack_words(self):
        """攻めの意図で攻め語あり → 高スコア."""
        features = {"phase": "midgame", "move_intent": "attack"}
        score = score_context_relevance("相手玉に迫る攻めの手です。", features)
        assert score >= 80

    def test_attack_intent_without_attack_words(self):
        """攻めの意図なのに攻め語なし → 減点."""
        features = {"phase": "midgame", "move_intent": "attack"}
        score = score_context_relevance("静かな局面が続きます。", features)
        assert score < 70

    def test_defense_intent_with_defense_words(self):
        """守りの意図で守り語あり → 高スコア."""
        features = {"phase": "midgame", "move_intent": "defense"}
        score = score_context_relevance("玉を固める守りの手です。", features)
        assert score >= 80

    def test_exchange_intent(self):
        """交換の意図で交換語あり → 加点."""
        features = {"phase": "midgame", "move_intent": "exchange"}
        score = score_context_relevance("銀と角の交換になりました。", features)
        assert score >= 75

    def test_range_0_100(self):
        features = {"phase": "opening", "move_intent": "attack"}
        score = score_context_relevance("終盤寄せ詰み", features)
        assert 0 <= score <= 100


class TestNaturalness:
    def test_good_text(self):
        """多様な文末・適切な長さ → 高スコア."""
        score = score_naturalness(GOOD_EXPLANATION)
        assert score >= 60

    def test_template_repetition(self):
        """同じ構造の繰り返し → 低スコア."""
        score = score_naturalness(TEMPLATE_EXPLANATION)
        assert score < 60

    def test_empty(self):
        assert score_naturalness("") == 0

    def test_single_short_sentence(self):
        """極端に短い一文 → 低スコア."""
        score = score_naturalness("良い手。")
        assert score < 50

    def test_connector_bonus(self):
        """接続詞使用 → 加点."""
        text = "手堅い一手です。しかし後手にも反撃の余地があります。また次の展開にも注目です。"
        score = score_naturalness(text)
        assert score >= 65

    def test_range_0_100(self):
        score = score_naturalness("テスト文です。")
        assert 0 <= score <= 100


class TestInformativeness:
    def test_good_text(self):
        """将棋用語・指し手・数値あり → 高スコア."""
        score = score_informativeness(INFORMATIVE_EXPLANATION)
        assert score >= 65

    def test_no_terms(self):
        """将棋用語なし → 低スコア."""
        score = score_informativeness(NO_TERMS_EXPLANATION)
        assert score < 50

    def test_piece_names_bonus(self):
        """駒名言及 → 加点."""
        score = score_informativeness("金と銀で玉を守ります。角が効いています。")
        assert score >= 50

    def test_move_reference(self):
        """具体的指し手言及 → 加点."""
        score = score_informativeness("▲７六歩が好手です。")
        assert score >= 45  # base(40) + piece(3) + move(5) = 48

    def test_range_0_100(self):
        score = score_informativeness("テスト")
        assert 0 <= score <= 100


class TestReadability:
    def test_good_length(self):
        """理想的な文字数・文数 → 高スコア."""
        score = score_readability(GOOD_EXPLANATION)
        assert score >= 65

    def test_too_short(self):
        """短すぎ → 低スコア."""
        score = score_readability(SHORT_EXPLANATION)
        assert score < 50

    def test_too_long(self):
        """長すぎ → 減点."""
        score = score_readability(LONG_EXPLANATION)
        assert score < 60

    def test_empty(self):
        assert score_readability("") == 0

    def test_unmatched_brackets(self):
        """括弧の対応不一致 → 減点."""
        score_good = score_readability("銀が（上がって）活躍しています。")
        score_bad = score_readability("銀が（上がって活躍しています。")
        assert score_good > score_bad

    def test_incomplete_sentence(self):
        """文末が途切れている → 減点."""
        score_complete = score_readability("好手です。")
        score_incomplete = score_readability("好手で")
        assert score_complete > score_incomplete

    def test_range_0_100(self):
        score = score_readability("テスト。")
        assert 0 <= score <= 100


class TestEvaluateExplanation:
    def test_good_explanation_high_score(self):
        """良い解説は総合スコアが高い."""
        features = {"phase": "midgame", "move_intent": "attack"}
        result = evaluate_explanation(GOOD_EXPLANATION, features)
        assert result["total"] >= 55
        assert "scores" in result
        assert all(k in result["scores"] for k in
                   ["context_relevance", "naturalness", "informativeness", "readability"])

    def test_template_low_naturalness(self):
        """定型文は naturalness が低い."""
        result = evaluate_explanation(TEMPLATE_EXPLANATION)
        assert result["scores"]["naturalness"] < 55

    def test_mismatch_low_context(self):
        """局面と矛盾する解説は context_relevance が低い."""
        features = {"phase": "opening", "move_intent": "development"}
        result = evaluate_explanation(PHASE_MISMATCH_OPENING, features)
        assert result["scores"]["context_relevance"] < 65

    def test_short_low_readability(self):
        """短すぎる解説は readability が低い."""
        result = evaluate_explanation(SHORT_EXPLANATION)
        assert result["scores"]["readability"] < 50

    def test_no_terms_low_informativeness(self):
        """専門用語なしは informativeness が低い."""
        result = evaluate_explanation(NO_TERMS_EXPLANATION)
        assert result["scores"]["informativeness"] < 50

    def test_total_weighted(self):
        """total は重み付き合計."""
        result = evaluate_explanation("テストの解説文です。", None)
        s = result["scores"]
        expected = (s["context_relevance"] * 0.30
                    + s["naturalness"] * 0.25
                    + s["informativeness"] * 0.25
                    + s["readability"] * 0.20)
        assert abs(result["total"] - round(expected, 1)) < 0.2

    def test_no_features_still_works(self):
        """特徴量なしでも全軸評価される."""
        result = evaluate_explanation(GOOD_EXPLANATION)
        assert 0 <= result["total"] <= 100


class TestEvaluateTrainingLogs:
    def _write_logs(self, log_dir: str, records: list) -> None:
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "explanations_2025-01.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _make_record(self, explanation: str, phase: str = "midgame",
                     intent: str = "attack") -> dict:
        return {
            "type": "explanation",
            "input": {
                "sfen": "position startpos",
                "features": {"phase": phase, "move_intent": intent},
            },
            "output": {"explanation": explanation},
        }

    def test_empty_dir(self):
        result = evaluate_training_logs("/nonexistent")
        assert result["total_records"] == 0

    def test_basic_stats(self, tmp_path):
        """基本統計が返る."""
        log_dir = str(tmp_path / "logs")
        records = [
            self._make_record(GOOD_EXPLANATION, "midgame", "attack"),
            self._make_record(INFORMATIVE_EXPLANATION, "opening", "development"),
            self._make_record(NO_TERMS_EXPLANATION, "endgame", "defense"),
        ]
        self._write_logs(log_dir, records)

        result = evaluate_training_logs(log_dir)
        assert result["total_records"] == 3
        assert "avg_total" in result
        assert "avg_scores" in result
        assert "low_quality_count" in result
        assert "by_phase" in result
        assert "by_intent" in result

    def test_phase_breakdown(self, tmp_path):
        """phase別の平均が計算される."""
        log_dir = str(tmp_path / "logs")
        records = [
            self._make_record(GOOD_EXPLANATION, "midgame", "attack"),
            self._make_record(GOOD_EXPLANATION, "opening", "development"),
        ]
        self._write_logs(log_dir, records)

        result = evaluate_training_logs(log_dir)
        assert "midgame" in result["by_phase"]
        assert "opening" in result["by_phase"]

    def test_low_quality_count(self, tmp_path):
        """低品質レコードがカウントされる."""
        log_dir = str(tmp_path / "logs")
        records = [
            self._make_record("短い。", "endgame", "attack"),  # 低品質
            self._make_record(GOOD_EXPLANATION, "midgame", "attack"),
        ]
        self._write_logs(log_dir, records)

        result = evaluate_training_logs(log_dir)
        assert result["total_records"] == 2
        # 短い解説は低品質の可能性が高い
        assert isinstance(result["low_quality_count"], int)
