"""Tests for diverse prompts, diversify script, and merge utility."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.schemas.annotation import DEPTH_LEVELS, FOCUS_LABELS
from backend.api.services.ml_trainer import STYLES
from backend.api.services.diverse_prompts import (
    DIVERSITY_TARGETS,
    build_diverse_prompt,
    compute_target_match,
)
from scripts.diversify_commentary import (
    _generate_diverse_template,
    _sample_balanced,
)
from scripts.merge_annotations import merge_annotations


def _make_features(**overrides):
    """テスト用の局面特徴量を生成."""
    base = {
        "king_safety": 50,
        "piece_activity": 50,
        "attack_pressure": 0,
        "phase": "midgame",
        "turn": "b",
        "ply": 30,
        "move_intent": "development",
        "tension_delta": {
            "d_king_safety": 0.0,
            "d_piece_activity": 0.0,
            "d_attack_pressure": 0.0,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# build_diverse_prompt tests
# ---------------------------------------------------------------------------
class TestBuildDiversePrompt(unittest.TestCase):
    """build_diverse_prompt のテスト."""

    def test_contains_style_instruction_technical(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "technical", ["king_safety"], "strategic"
        )
        self.assertIn("論理的", prompt)

    def test_contains_style_instruction_dramatic(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "dramatic", ["king_safety"], "strategic"
        )
        self.assertIn("ドラマチック", prompt)

    def test_contains_style_instruction_encouraging(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "encouraging", ["king_safety"], "strategic"
        )
        self.assertIn("初心者", prompt)

    def test_contains_style_instruction_neutral(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "neutral", ["king_safety"], "strategic"
        )
        self.assertIn("客観的", prompt)

    def test_contains_focus_description(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "neutral", ["king_safety", "attack_pressure"], "strategic"
        )
        self.assertIn("玉の安全性", prompt)
        self.assertIn("攻めの圧力", prompt)

    def test_contains_depth_surface(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "neutral", ["positional"], "surface"
        )
        self.assertIn("30文字以内", prompt)

    def test_contains_depth_deep(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "neutral", ["positional"], "deep"
        )
        self.assertIn("80文字以上", prompt)
        self.assertIn("条件分岐", prompt)

    def test_contains_features_info(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(king_safety=70, attack_pressure=40),
            "neutral", ["positional"], "strategic"
        )
        self.assertIn("70/100", prompt)
        self.assertIn("40/100", prompt)

    def test_empty_focus_defaults_positional(self) -> None:
        prompt = build_diverse_prompt(
            _make_features(), "neutral", [], "strategic"
        )
        # Should still include some focus description
        self.assertIn("注目して解説", prompt)


# ---------------------------------------------------------------------------
# DIVERSITY_TARGETS validation
# ---------------------------------------------------------------------------
class TestDiversityTargets(unittest.TestCase):
    """DIVERSITY_TARGETS の検証."""

    def test_all_styles_valid(self) -> None:
        for target in DIVERSITY_TARGETS:
            self.assertIn(target["style"], STYLES,
                          f"Invalid style: {target['style']}")

    def test_all_focus_valid(self) -> None:
        for target in DIVERSITY_TARGETS:
            for f in target["focus"]:
                self.assertIn(f, FOCUS_LABELS,
                              f"Invalid focus: {f}")

    def test_all_depths_valid(self) -> None:
        for target in DIVERSITY_TARGETS:
            self.assertIn(target["depth"], DEPTH_LEVELS,
                          f"Invalid depth: {target['depth']}")

    def test_covers_all_styles(self) -> None:
        styles_covered = {t["style"] for t in DIVERSITY_TARGETS}
        for s in STYLES:
            self.assertIn(s, styles_covered)

    def test_covers_all_depths(self) -> None:
        depths_covered = {t["depth"] for t in DIVERSITY_TARGETS}
        for d in DEPTH_LEVELS:
            self.assertIn(d, depths_covered)


# ---------------------------------------------------------------------------
# compute_target_match tests
# ---------------------------------------------------------------------------
class TestTargetMatch(unittest.TestCase):
    """compute_target_match のテスト."""

    def test_perfect_match(self) -> None:
        target = {"style": "dramatic", "focus": ["king_safety"], "depth": "deep"}
        annotation = {"style": "dramatic", "focus": ["king_safety"], "depth": "deep"}
        match = compute_target_match(target, annotation)
        self.assertTrue(match["style_match"])
        self.assertEqual(match["focus_recall"], 1.0)
        self.assertTrue(match["depth_match"])

    def test_no_match(self) -> None:
        target = {"style": "dramatic", "focus": ["king_safety"], "depth": "deep"}
        annotation = {"style": "neutral", "focus": ["positional"], "depth": "surface"}
        match = compute_target_match(target, annotation)
        self.assertFalse(match["style_match"])
        self.assertEqual(match["focus_recall"], 0.0)
        self.assertFalse(match["depth_match"])

    def test_partial_focus_recall(self) -> None:
        target = {"style": "neutral", "focus": ["king_safety", "attack_pressure"], "depth": "strategic"}
        annotation = {"style": "neutral", "focus": ["king_safety", "positional"], "depth": "strategic"}
        match = compute_target_match(target, annotation)
        self.assertEqual(match["focus_recall"], 0.5)

    def test_empty_target_focus(self) -> None:
        target = {"style": "neutral", "focus": [], "depth": "strategic"}
        annotation = {"style": "neutral", "focus": ["positional"], "depth": "strategic"}
        match = compute_target_match(target, annotation)
        self.assertEqual(match["focus_recall"], 1.0)


# ---------------------------------------------------------------------------
# Dry-run template generation
# ---------------------------------------------------------------------------
class TestDiverseTemplate(unittest.TestCase):
    """dry-run テンプレート生成のテスト."""

    def test_surface_short(self) -> None:
        target = {"style": "neutral", "focus": ["king_safety"], "depth": "surface"}
        text = _generate_diverse_template(_make_features(), target, seed=42)
        self.assertLess(len(text), 60)

    def test_deep_long(self) -> None:
        target = {"style": "technical", "focus": ["king_safety"], "depth": "deep"}
        text = _generate_diverse_template(_make_features(), target, seed=42)
        self.assertGreater(len(text), 50)

    def test_focus_keywords_injected(self) -> None:
        target = {"style": "neutral", "focus": ["attack_pressure"], "depth": "strategic"}
        text = _generate_diverse_template(_make_features(), target, seed=42)
        # Should contain attack-related keyword
        self.assertTrue(
            any(w in text for w in ["攻め", "圧力", "仕掛け", "迫る"]),
            f"No attack keyword in: {text}"
        )

    def test_endgame_focus_keywords(self) -> None:
        target = {"style": "neutral", "focus": ["endgame_technique"], "depth": "strategic"}
        text = _generate_diverse_template(_make_features(), target, seed=42)
        self.assertTrue(
            any(w in text for w in ["終盤", "寄せ", "詰み", "受け"]),
            f"No endgame keyword in: {text}"
        )


# ---------------------------------------------------------------------------
# Sample balancing
# ---------------------------------------------------------------------------
class TestSampleBalancing(unittest.TestCase):
    """_sample_balanced のテスト."""

    def test_balanced_phases(self) -> None:
        records = []
        for i in range(60):
            phase = ["opening", "midgame", "endgame"][i % 3]
            records.append({"phase": phase, "ply": i * 5})
        sampled = _sample_balanced(records, max_samples=30)
        phases = [r["phase"] for r in sampled]
        self.assertGreaterEqual(phases.count("opening"), 5)
        self.assertGreaterEqual(phases.count("midgame"), 5)
        self.assertGreaterEqual(phases.count("endgame"), 5)

    def test_respects_max_samples(self) -> None:
        records = [{"phase": "midgame", "ply": i} for i in range(100)]
        sampled = _sample_balanced(records, max_samples=10)
        self.assertLessEqual(len(sampled), 10)


# ---------------------------------------------------------------------------
# Merge annotations
# ---------------------------------------------------------------------------
class TestMergeAnnotations(unittest.TestCase):
    """merge_annotations のテスト."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def _write_jsonl(self, name: str, records: list) -> Path:
        path = Path(self._tmpdir) / name
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return path

    def test_merge_two_files(self) -> None:
        records_a = [
            {"sfen": "pos1", "ply": 0, "source": "a", "original_text": "text1",
             "annotation": {"focus": ["king_safety"], "importance": 0.5,
                            "depth": "strategic", "style": "neutral"}},
        ]
        records_b = [
            {"sfen": "pos2", "ply": 10, "source": "b", "original_text": "text2",
             "annotation": {"focus": ["attack_pressure"], "importance": 0.7,
                            "depth": "deep", "style": "dramatic"}},
        ]
        self._write_jsonl("file_a.jsonl", records_a)
        self._write_jsonl("file_b.jsonl", records_b)

        out = Path(self._tmpdir) / "merged.jsonl"
        result = merge_annotations(
            input_dir=Path(self._tmpdir), output_path=out, dry_run=False
        )
        self.assertEqual(result["merged"], 2)
        self.assertEqual(result["duplicates"], 0)
        self.assertTrue(out.exists())

    def test_dedup_removes_duplicates(self) -> None:
        record = {
            "sfen": "pos1", "ply": 0, "source": "a", "original_text": "same text here",
            "annotation": {"focus": ["king_safety"], "importance": 0.5,
                           "depth": "strategic", "style": "neutral"},
        }
        self._write_jsonl("file_a.jsonl", [record])
        self._write_jsonl("file_b.jsonl", [record])

        out = Path(self._tmpdir) / "merged.jsonl"
        result = merge_annotations(
            input_dir=Path(self._tmpdir), output_path=out, dry_run=False
        )
        self.assertEqual(result["merged"], 1)
        self.assertEqual(result["duplicates"], 1)

    def test_dry_run_no_file(self) -> None:
        records = [
            {"sfen": "pos1", "ply": 0, "source": "a", "original_text": "text",
             "annotation": {"focus": ["king_safety"], "importance": 0.5,
                            "depth": "strategic", "style": "neutral"}},
        ]
        self._write_jsonl("file_a.jsonl", records)

        out = Path(self._tmpdir) / "merged.jsonl"
        result = merge_annotations(
            input_dir=Path(self._tmpdir), output_path=out, dry_run=True
        )
        self.assertEqual(result["merged"], 1)
        self.assertFalse(out.exists())

    def test_empty_dir(self) -> None:
        out = Path(self._tmpdir) / "merged.jsonl"
        result = merge_annotations(
            input_dir=Path(self._tmpdir), output_path=out
        )
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["merged"], 0)


if __name__ == "__main__":
    unittest.main()
