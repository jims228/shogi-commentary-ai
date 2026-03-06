"""tests/test_compare_legacy_vs_planner.py

compare_legacy_vs_planner.py の単体テスト.
LLMなし (USE_LLM=0) で動作確認する.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.compare_legacy_vs_planner import (
    _load_positions,
    compare_single,
    run_comparison,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
OPENING_POS = {
    "name": "平手初期局面",
    "sfen": "position startpos",
    "ply": 0,
}

MIDGAME_POS = {
    "name": "矢倉囲い完成",
    "sfen": "position sfen ln1g1g1nl/1ks1r4/1pppp1p1p/p4s2P/9/P1P1PS1p1/1P1PP1P2/1BK1G2R1/LNSG3NL b - 32",
    "ply": 32,
    "user_move": "7g7f",
    "delta_cp": -50,
}

ENDGAME_POS = {
    "name": "終盤の寄せ合い",
    "sfen": "position sfen 4k4/9/4G4/9/9/9/9/9/4K4 b G2r2b4s4n4l18p 120",
    "ply": 120,
}

POS_WITH_PREV_MOVES = {
    "name": "前手あり",
    "sfen": "position startpos",
    "ply": 5,
    "prev_moves": ["7g7f", "3c3d", "2g2f"],
}


# ---------------------------------------------------------------------------
# _load_positions
# ---------------------------------------------------------------------------
class TestLoadPositions:
    def test_load_benchmark(self):
        path = Path(__file__).resolve().parent.parent / "data" / "benchmark_positions.json"
        if not path.exists():
            pytest.skip("benchmark_positions.json not found")
        positions = _load_positions(str(path))
        assert len(positions) >= 1
        assert "sfen" in positions[0]

    def test_load_custom(self, tmp_path):
        data = [{"name": "test", "sfen": "position startpos", "ply": 0}]
        p = tmp_path / "test.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        loaded = _load_positions(str(p))
        assert len(loaded) == 1
        assert loaded[0]["name"] == "test"


# ---------------------------------------------------------------------------
# compare_single (LLMなし)
# ---------------------------------------------------------------------------
class TestCompareSingle:
    def test_opening_position(self):
        result = asyncio.run(compare_single(OPENING_POS, use_llm=False))
        assert "legacy_explanation" in result
        assert "planner_explanation" in result
        assert "legacy_eval" in result
        assert "planner_eval" in result
        assert result["legacy_char_count"] == len(result["legacy_explanation"])
        assert result["planner_char_count"] == len(result["planner_explanation"])
        assert result["is_fallback"] is True  # LLMなし → fallback

    def test_midgame_position(self):
        result = asyncio.run(compare_single(MIDGAME_POS, use_llm=False))
        assert result["ply"] == 32
        assert result["user_move"] == "7g7f"
        assert not result["legacy_error"]
        assert not result["planner_error"]

    def test_endgame_position(self):
        result = asyncio.run(compare_single(ENDGAME_POS, use_llm=False))
        assert result["ply"] == 120
        assert len(result["planner_explanation"]) > 0

    def test_with_prev_moves(self):
        result = asyncio.run(compare_single(POS_WITH_PREV_MOVES, use_llm=False))
        assert result["prev_moves"] == ["7g7f", "3c3d", "2g2f"]
        assert len(result["planner_explanation"]) > 0

    def test_planner_plan_present(self):
        result = asyncio.run(compare_single(OPENING_POS, use_llm=False))
        assert result["planner_plan"] is not None
        assert "flow" in result["planner_plan"]
        assert "topic_keyword" in result["planner_plan"]

    def test_eval_scores_structure(self):
        result = asyncio.run(compare_single(OPENING_POS, use_llm=False))
        for key in ("legacy_eval", "planner_eval"):
            ev = result[key]
            assert "scores" in ev
            assert "total" in ev
            for axis in ("context_relevance", "naturalness", "informativeness", "readability"):
                assert axis in ev["scores"]
                assert 0 <= ev["scores"][axis] <= 100

    def test_output_fields(self):
        """ユーザーが要求した12+フィールドが全て含まれる."""
        result = asyncio.run(compare_single(MIDGAME_POS, use_llm=False))
        required = [
            "sfen", "ply", "prev_moves", "candidates", "user_move", "delta_cp",
            "legacy_explanation", "planner_explanation", "planner_plan", "style",
            "legacy_char_count", "planner_char_count", "is_fallback",
            "legacy_error", "planner_error",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_planner_explanation_within_80_chars(self):
        result = asyncio.run(compare_single(MIDGAME_POS, use_llm=False))
        assert len(result["planner_explanation"]) <= 80


# ---------------------------------------------------------------------------
# run_comparison (LLMなし)
# ---------------------------------------------------------------------------
class TestRunComparison:
    def test_summary_structure(self):
        positions = [OPENING_POS, MIDGAME_POS, ENDGAME_POS]
        report = asyncio.run(run_comparison(positions, use_llm=False))
        assert "timestamp" in report
        assert "summary" in report
        assert "positions" in report
        s = report["summary"]
        assert s["total_positions"] == 3
        assert s["use_llm"] is False
        assert "legacy_avg_score" in s
        assert "planner_avg_score" in s
        assert "planner_wins" in s
        assert "legacy_wins" in s
        assert "ties" in s
        assert "fallback_count" in s
        assert "error_count" in s
        assert "note" in s

    def test_wins_add_up(self):
        positions = [OPENING_POS, MIDGAME_POS]
        report = asyncio.run(run_comparison(positions, use_llm=False))
        s = report["summary"]
        total = s["planner_wins"] + s["legacy_wins"] + s["ties"]
        assert total == s["total_positions"]

    def test_benchmark_positions(self):
        path = Path(__file__).resolve().parent.parent / "data" / "benchmark_positions.json"
        if not path.exists():
            pytest.skip("benchmark_positions.json not found")
        positions = _load_positions(str(path))
        report = asyncio.run(run_comparison(positions, use_llm=False))
        assert report["summary"]["total_positions"] == len(positions)
        # 全局面でエラーなし
        for r in report["positions"]:
            assert not r["legacy_error"], f"Legacy error on {r['name']}"
            assert not r["planner_error"], f"Planner error on {r['name']}"

    def test_style_param(self):
        report = asyncio.run(run_comparison([OPENING_POS], use_llm=False, style="technical"))
        assert report["summary"]["style"] == "technical"
        assert report["positions"][0]["style"] == "technical"


# ---------------------------------------------------------------------------
# 出力ファイル形式
# ---------------------------------------------------------------------------
class TestOutputFormat:
    def test_json_serializable(self):
        report = asyncio.run(run_comparison([OPENING_POS], use_llm=False))
        # JSON serialize/deserialize round-trip
        serialized = json.dumps(report, ensure_ascii=False, indent=2)
        loaded = json.loads(serialized)
        assert loaded["summary"]["total_positions"] == 1
