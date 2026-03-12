"""Tests for quality comparison tool and batch generation enhancements."""
from __future__ import annotations

import atexit
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.quality_comparison import (
    load_features,
    generate_mock_gemini_commentary,
    compare_single,
    compute_phase_breakdown,
    run_comparison,
)
from scripts.batch_generate_commentary import (
    load_collection_config,
    _is_phase_over_represented,
    _estimate_cost_yen,
    batch_generate,
)
from backend.api.services.template_commentary import generate_template_commentary

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _make_features_file() -> str:
    """Create a self-contained temp JSONL of position features (cleaned up at exit)."""
    phases = ["opening", "midgame", "endgame"]
    records = [
        {
            "game_index": i // 5,
            "ply": (i % 5) * 10,
            "sfen": "position startpos",
            "move": "7g7f",
            "king_safety": 28 + (i % 10),
            "piece_activity": 50 + (i % 20),
            "attack_pressure": i % 30,
            "phase": phases[i % 3],
            "turn": "b" if i % 2 == 0 else "w",
            "move_intent": "development",
            "tension_delta": {
                "d_king_safety": float(i % 10 - 5),
                "d_piece_activity": float(i % 8 - 4),
                "d_attack_pressure": float(i % 6 - 3),
            },
        }
        for i in range(20)
    ]
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    atexit.register(os.unlink, path)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def _make_sample_games_file() -> str:
    """Create a self-contained temp USI game file (cleaned up at exit)."""
    yagura_20 = (
        "position startpos moves "
        "7g7f 8c8d 6g6f 3c3d 6f6e 7a6b "
        "2h6h 5a4b 5i4h 4b3b 3i3h 6b5b "
        "4h3i 5b4b 3h2g 4b3c 7i6h 3a2b "
        "6h5g 2b3a"
    )
    fd, path = tempfile.mkstemp(suffix=".txt")
    atexit.register(os.unlink, path)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for i in range(3):
            f.write(f"# test game {i + 1}\n")
            f.write(yagura_20 + "\n")
    return path


_FEATURES_PATH = _make_features_file()
_SAMPLE_GAMES_FILE = _make_sample_games_file()


# ---------------------------------------------------------------------------
# A/B Comparison
# ---------------------------------------------------------------------------

class TestABComparison:
    """A/B comparison logic tests."""

    def test_load_features_returns_correct_count(self) -> None:
        features = load_features(_FEATURES_PATH, samples=5, seed=42)
        assert len(features) == 5

    def test_load_features_has_required_keys(self) -> None:
        features = load_features(_FEATURES_PATH, samples=3, seed=42)
        for f in features:
            assert "phase" in f
            assert "king_safety" in f

    def test_load_features_reproducible_with_seed(self) -> None:
        f1 = load_features(_FEATURES_PATH, samples=5, seed=42)
        f2 = load_features(_FEATURES_PATH, samples=5, seed=42)
        assert f1 == f2

    def test_load_features_different_seed_different_sample(self) -> None:
        f1 = load_features(_FEATURES_PATH, samples=5, seed=42)
        f2 = load_features(_FEATURES_PATH, samples=5, seed=99)
        assert f1 != f2

    def test_mock_gemini_longer_than_template(self) -> None:
        features = {
            "phase": "midgame",
            "king_safety": 50,
            "attack_pressure": 30,
            "move_intent": "attack",
            "piece_activity": 60,
        }
        template = generate_template_commentary(features, seed=0)
        mock = generate_mock_gemini_commentary(features, seed=0)
        assert len(mock) > len(template)

    def test_compare_single_has_diff(self) -> None:
        features = {
            "phase": "midgame",
            "king_safety": 50,
            "attack_pressure": 30,
            "move_intent": "attack",
            "piece_activity": 60,
        }
        t_text = generate_template_commentary(features, seed=0)
        g_text = generate_mock_gemini_commentary(features, seed=100)
        result = compare_single(features, t_text, g_text)
        assert "quality_diff" in result
        assert "total" in result["quality_diff"]
        assert "template" in result
        assert "gemini" in result

    def test_compare_single_phase_preserved(self) -> None:
        features = {
            "phase": "opening",
            "king_safety": 60,
            "attack_pressure": 5,
            "piece_activity": 40,
        }
        t_text = generate_template_commentary(features, seed=0)
        g_text = generate_mock_gemini_commentary(features, seed=100)
        result = compare_single(features, t_text, g_text)
        assert result["phase"] == "opening"

    def test_phase_breakdown_all_phases(self) -> None:
        results = [
            {
                "phase": "opening",
                "template": {"quality": {"total": 60.0}},
                "gemini": {"quality": {"total": 65.0}},
                "quality_diff": {"total": 5.0},
            },
            {
                "phase": "midgame",
                "template": {"quality": {"total": 55.0}},
                "gemini": {"quality": {"total": 62.0}},
                "quality_diff": {"total": 7.0},
            },
            {
                "phase": "endgame",
                "template": {"quality": {"total": 50.0}},
                "gemini": {"quality": {"total": 58.0}},
                "quality_diff": {"total": 8.0},
            },
        ]
        breakdown = compute_phase_breakdown(results)
        assert "opening" in breakdown
        assert "midgame" in breakdown
        assert "endgame" in breakdown
        assert breakdown["opening"]["template_avg"] == 60.0
        assert breakdown["midgame"]["gemini_avg"] == 62.0

    def test_dry_run_comparison_no_api(self) -> None:
        with patch("scripts.quality_comparison.generate_gemini_commentary") as mock_api:
            results = asyncio.run(run_comparison(
                features_path=_FEATURES_PATH,
                samples=3,
                dry_run=True,
                seed=42,
            ))
            mock_api.assert_not_called()
            assert len(results) == 3


# ---------------------------------------------------------------------------
# Config Loading
# ---------------------------------------------------------------------------

class TestConfigLoading:
    """Config loading and defaults tests."""

    def test_default_config_when_missing(self) -> None:
        config = load_collection_config("/nonexistent/path.json")
        assert config["daily_budget_yen"] == 100
        assert config["rate_limit_per_minute"] == 10
        assert config["max_requests_per_run"] == 200
        assert config["min_quality_score"] == 40
        assert config["max_retries"] == 2
        assert config["model"] is None

    def test_config_loads_from_file(self, tmp_path: Path) -> None:
        config_data = {
            "daily_budget_yen": 200,
            "rate_limit_per_minute": 5,
        }
        config_path = str(tmp_path / "test_config.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_collection_config(config_path)
        assert config["daily_budget_yen"] == 200
        assert config["rate_limit_per_minute"] == 5
        # Defaults for missing keys
        assert config["max_retries"] == 2

    def test_config_partial_override(self, tmp_path: Path) -> None:
        config_data = {"min_quality_score": 50}
        config_path = str(tmp_path / "partial.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_collection_config(config_path)
        assert config["min_quality_score"] == 50
        assert config["daily_budget_yen"] == 100  # default preserved

    def test_phase_targets_default_sum(self) -> None:
        config = load_collection_config("/nonexistent/path.json")
        targets = config["phase_targets"]
        assert abs(sum(targets.values()) - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Phase Balance
# ---------------------------------------------------------------------------

class TestPhaseBalance:
    """Phase balance logic tests."""

    def test_not_over_represented_early(self) -> None:
        assert not _is_phase_over_represented(
            "opening",
            {"opening": 3, "midgame": 2, "endgame": 0},
            {"opening": 0.3, "midgame": 0.4, "endgame": 0.3},
            total_processed=5,
        )

    def test_over_represented_detected(self) -> None:
        assert _is_phase_over_represented(
            "opening",
            {"opening": 15, "midgame": 5, "endgame": 5},
            {"opening": 0.3, "midgame": 0.4, "endgame": 0.3},
            total_processed=25,
        )

    def test_balanced_not_flagged(self) -> None:
        assert not _is_phase_over_represented(
            "midgame",
            {"opening": 3, "midgame": 4, "endgame": 3},
            {"opening": 0.3, "midgame": 0.4, "endgame": 0.3},
            total_processed=10,
        )

    def test_unknown_phase_default(self) -> None:
        result = _is_phase_over_represented(
            "unknown_phase",
            {"unknown_phase": 0},
            {"opening": 0.3, "midgame": 0.4, "endgame": 0.3},
            total_processed=20,
        )
        assert not result  # 0/20 = 0% < 33% * 1.5


# ---------------------------------------------------------------------------
# Quality Retry
# ---------------------------------------------------------------------------

class TestQualityRetry:
    """Quality retry logic tests."""

    def test_batch_generate_with_retry(self) -> None:
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = asyncio.run(batch_generate(
                input_file=input_file,
                output_dir=tmpdir,
                sample_interval=30,
                max_requests=3,
                dry_run=True,
                min_quality_score=100.0,  # Impossible → forces retries
                max_retries=2,
            ))
            assert stats["processed"] > 0
            assert stats["total_retries"] > 0

    def test_high_quality_no_retry(self) -> None:
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = asyncio.run(batch_generate(
                input_file=input_file,
                output_dir=tmpdir,
                sample_interval=30,
                max_requests=2,
                dry_run=True,
                min_quality_score=0.0,  # All pass immediately
                max_retries=5,
            ))
            assert stats["processed"] > 0
            assert stats["total_retries"] == 0


# ---------------------------------------------------------------------------
# Budget Estimation
# ---------------------------------------------------------------------------

class TestBudgetEstimation:
    """Budget estimation tests."""

    def test_zero_requests(self) -> None:
        assert _estimate_cost_yen(0) == 0.0

    def test_positive_cost(self) -> None:
        cost = _estimate_cost_yen(100)
        assert cost > 0

    def test_cost_scales_linearly(self) -> None:
        cost_100 = _estimate_cost_yen(100)
        cost_200 = _estimate_cost_yen(200)
        assert abs(cost_200 - cost_100 * 2) < 0.01

    def test_known_value(self) -> None:
        """1 request: ~¥0.01 based on 500 input + 100 output tokens."""
        cost = _estimate_cost_yen(1)
        assert 0.005 < cost < 0.02
