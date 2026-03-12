"""tests for scripts/batch_generate_commentary.py."""
from __future__ import annotations

import atexit
import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch

# プロジェクトルートをパスに追加
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.batch_generate_commentary import (
    batch_generate,
    _load_progress,
    _save_progress,
)


# ---------------------------------------------------------------------------
# Self-contained game data — three copies of a 20-move valid game sequence.
# sample_interval=10 → 3 positions/game, sample_interval=15 → 2 positions/game,
# sample_interval=30 → 1 position/game.  Three games give enough total
# positions that max_requests caps of 3 and 5 are reliably hit.
# ---------------------------------------------------------------------------
_YAGURA_20 = (
    "position startpos moves "
    "7g7f 8c8d 6g6f 3c3d 6f6e 7a6b "
    "2h6h 5a4b 5i4h 4b3b 3i3h 6b5b "
    "4h3i 5b4b 3h2g 4b3c 7i6h 3a2b "
    "6h5g 2b3a"
)


def _make_sample_games_file() -> str:
    """Create a temporary USI game file for testing (cleaned up at exit)."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    atexit.register(os.unlink, path)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for i in range(3):
            f.write(f"# test game {i + 1}\n")
            f.write(_YAGURA_20 + "\n")
    return path


_SAMPLE_GAMES_FILE = _make_sample_games_file()


class TestDryRun(unittest.TestCase):
    """--dry-run モードのテスト."""

    def test_dry_run_produces_output(self) -> None:
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = asyncio.run(batch_generate(
                input_file=input_file,
                output_dir=tmpdir,
                sample_interval=10,
                max_requests=5,
                dry_run=True,
            ))
            self.assertEqual(stats["processed"], 5)
            self.assertGreater(stats["avg_quality"], 0)

            # JSONL出力を確認
            output_path = os.path.join(tmpdir, "batch_commentary.jsonl")
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(records), 5)
            for r in records:
                self.assertIn("commentary", r)
                self.assertIn("quality", r)
                self.assertEqual(r["source"], "template")

    def test_dry_run_no_api_calls(self) -> None:
        """dry-run ではGemini APIが呼ばれないことを確認."""
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.batch_generate_commentary._generate_api_commentary") as mock_api:
                asyncio.run(batch_generate(
                    input_file=input_file,
                    output_dir=tmpdir,
                    sample_interval=15,
                    max_requests=3,
                    dry_run=True,
                ))
                mock_api.assert_not_called()

    def test_quality_scores_present(self) -> None:
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            asyncio.run(batch_generate(
                input_file=input_file,
                output_dir=tmpdir,
                sample_interval=30,
                max_requests=3,
                dry_run=True,
            ))
            output_path = os.path.join(tmpdir, "batch_commentary.jsonl")
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line.strip())
                    quality = record["quality"]
                    self.assertIn("scores", quality)
                    self.assertIn("total", quality)
                    self.assertGreater(quality["total"], 0)


class TestResume(unittest.TestCase):
    """resume 機能のテスト."""

    def test_progress_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 0, 0)
            _save_progress(tmpdir, 0, 5)
            _save_progress(tmpdir, 1, 0)

            done = _load_progress(tmpdir)
            self.assertIn((0, 0), done)
            self.assertIn((0, 5), done)
            self.assertIn((1, 0), done)
            self.assertNotIn((2, 0), done)

    def test_skip_already_processed(self) -> None:
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            # 初回実行
            stats1 = asyncio.run(batch_generate(
                input_file=input_file,
                output_dir=tmpdir,
                sample_interval=15,
                max_requests=5,
                dry_run=True,
            ))
            self.assertEqual(stats1["processed"], 5)
            self.assertEqual(stats1["skipped"], 0)

            # 2回目: 前回の分はスキップされる
            stats2 = asyncio.run(batch_generate(
                input_file=input_file,
                output_dir=tmpdir,
                sample_interval=15,
                max_requests=10,
                dry_run=True,
            ))
            self.assertGreater(stats2["skipped"], 0)

    def test_empty_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            done = _load_progress(tmpdir)
            self.assertEqual(len(done), 0)


class TestRateLimiting(unittest.TestCase):
    """rate limiting のテスト."""

    def test_dry_run_no_sleep(self) -> None:
        """dry-run ではsleepしない."""
        input_file = _SAMPLE_GAMES_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("time.sleep") as mock_sleep:
                asyncio.run(batch_generate(
                    input_file=input_file,
                    output_dir=tmpdir,
                    sample_interval=15,
                    max_requests=3,
                    rate_limit=5,
                    dry_run=True,
                ))
                mock_sleep.assert_not_called()


class TestInputErrors(unittest.TestCase):
    """入力エラーのテスト."""

    def test_missing_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = asyncio.run(batch_generate(
                input_file="/nonexistent/file.txt",
                output_dir=tmpdir,
                dry_run=True,
            ))
            self.assertEqual(stats["processed"], 0)


if __name__ == "__main__":
    unittest.main()
