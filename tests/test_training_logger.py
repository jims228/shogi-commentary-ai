"""Tests for backend.api.services.training_logger."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest import mock

import pytest

from backend.api.services.training_logger import (
    TrainingLogger,
    export_training_dataset,
)


def _run(coro):
    """Convenience wrapper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def tmp_log_dir(tmp_path):
    """テスト用の一時ログディレクトリ."""
    log_dir = str(tmp_path / "training_logs")
    with mock.patch("backend.api.services.training_logger._LOG_DIR", log_dir):
        yield log_dir


def _make_explanation_record(explanation: str = "テスト解説", ply: int = 10) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "explanation",
        "input": {
            "sfen": "position startpos moves 7g7f",
            "ply": ply,
            "candidates": [{"move": "7g7f", "score_cp": 50}],
            "user_move": "7g7f",
            "delta_cp": -10,
            "features": {"king_safety": 70, "phase": "opening"},
        },
        "output": {
            "explanation": explanation,
            "model": "gemini-2.5-flash-lite",
            "tokens": {"prompt": 100, "completion": 30},
        },
    }


def _make_digest_record(explanation: str = "ダイジェストテスト") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "digest",
        "input": {
            "total_moves": 80,
            "eval_history_len": 80,
            "notes_count": 5,
            "digest_features_count": 10,
        },
        "output": {
            "explanation": explanation,
            "model": "gemini-2.5-flash-lite",
            "tokens": {"prompt": 500, "completion": 200},
            "source": "llm",
        },
    }


class TestTrainingLogger:
    def test_log_explanation_creates_file(self, tmp_log_dir):
        """ログファイルが作成され、レコードが書き込まれる."""
        logger = TrainingLogger()
        record = _make_explanation_record()
        _run(logger.log_explanation(record))

        files = os.listdir(tmp_log_dir)
        assert len(files) == 1
        assert files[0].startswith("explanations_")
        assert files[0].endswith(".jsonl")

        with open(os.path.join(tmp_log_dir, files[0]), "r") as f:
            line = f.readline()
        obj = json.loads(line)
        assert obj["type"] == "explanation"
        assert obj["output"]["explanation"] == "テスト解説"

    def test_log_digest_creates_file(self, tmp_log_dir):
        """ダイジェストログが正しく書き込まれる."""
        logger = TrainingLogger()
        record = _make_digest_record()
        _run(logger.log_digest(record))

        files = os.listdir(tmp_log_dir)
        assert len(files) == 1
        assert files[0].startswith("digests_")

    def test_multiple_records_appended(self, tmp_log_dir):
        """複数レコードが追記される."""
        logger = TrainingLogger()
        _run(logger.log_explanation(_make_explanation_record("解説1")))
        _run(logger.log_explanation(_make_explanation_record("解説2")))
        _run(logger.log_explanation(_make_explanation_record("解説3")))

        files = os.listdir(tmp_log_dir)
        assert len(files) == 1

        with open(os.path.join(tmp_log_dir, files[0]), "r") as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_month_rotation(self, tmp_log_dir):
        """月が異なればファイルが分かれる."""
        logger = TrainingLogger()

        record = _make_explanation_record()
        _run(logger.log_explanation(record))

        # 別の月のファイル名を直接作成してテスト
        other_path = os.path.join(tmp_log_dir, "explanations_2024-01.jsonl")
        with open(other_path, "w") as f:
            f.write(json.dumps(record) + "\n")

        files = sorted(os.listdir(tmp_log_dir))
        assert len(files) == 2
        assert "2024-01" in files[0]

    def test_disabled_no_file(self, tmp_log_dir):
        """TRAINING_LOG_ENABLED=0 のときはファイルが作られない."""
        logger = TrainingLogger()
        with mock.patch.dict(os.environ, {"TRAINING_LOG_ENABLED": "0"}):
            _run(logger.log_explanation(_make_explanation_record()))

        assert not os.path.exists(tmp_log_dir) or len(os.listdir(tmp_log_dir)) == 0

    def test_get_stats_empty(self, tmp_log_dir):
        """ディレクトリが存在しない場合の統計."""
        logger = TrainingLogger()
        stats = logger.get_stats()
        assert stats["files"] == []

    def test_get_stats_with_data(self, tmp_log_dir):
        """データがある場合の統計."""
        logger = TrainingLogger()
        _run(logger.log_explanation(_make_explanation_record()))
        _run(logger.log_explanation(_make_explanation_record()))

        stats = logger.get_stats()
        assert len(stats["files"]) == 1
        assert stats["files"][0]["records"] == 2
        assert stats["files"][0]["size_bytes"] > 0


class TestExportTrainingDataset:
    def _setup_logs(self, log_dir: str, count: int = 10) -> None:
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "explanations_2025-01.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for i in range(count):
                record = _make_explanation_record(f"解説テスト文章番号{i}です。これは十分な長さがあります。", ply=i + 1)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_basic_export(self, tmp_path):
        """基本的なエクスポートが動作する."""
        log_dir = str(tmp_path / "logs")
        self._setup_logs(log_dir, count=10)

        output = str(tmp_path / "output.jsonl")
        result = export_training_dataset(log_dir=log_dir, output_path=output)

        assert result["total"] == 10
        assert result["train"] + result["val"] == 10
        assert result["filtered"] == 0
        assert os.path.exists(result["train_path"])
        assert os.path.exists(result["val_path"])

    def test_filter_short_explanations(self, tmp_path):
        """短い解説はフィルタされる."""
        log_dir = str(tmp_path / "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "explanations_2025-01.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            # 短い
            f.write(json.dumps(_make_explanation_record("短い"), ensure_ascii=False) + "\n")
            # 長い
            f.write(json.dumps(
                _make_explanation_record("これは十分な長さの解説テスト文章です。フィルタされないはず。"),
                ensure_ascii=False
            ) + "\n")

        output = str(tmp_path / "output.jsonl")
        result = export_training_dataset(log_dir=log_dir, output_path=output, min_explanation_length=20)

        assert result["total"] == 1
        assert result["filtered"] == 1

    def test_train_val_split(self, tmp_path):
        """80/20 分割が正しい."""
        log_dir = str(tmp_path / "logs")
        self._setup_logs(log_dir, count=100)

        output = str(tmp_path / "output.jsonl")
        result = export_training_dataset(log_dir=log_dir, output_path=output, val_ratio=0.2)

        assert result["train"] == 80
        assert result["val"] == 20

    def test_empty_dir(self, tmp_path):
        """空ディレクトリでもクラッシュしない."""
        log_dir = str(tmp_path / "empty_logs")
        result = export_training_dataset(log_dir=log_dir)
        assert result["total"] == 0

    def test_nonexistent_dir(self, tmp_path):
        """存在しないディレクトリでもクラッシュしない."""
        result = export_training_dataset(log_dir="/nonexistent/path")
        assert result["total"] == 0

    def test_output_format(self, tmp_path):
        """出力ファイルの各行が有効なJSONで必要なキーを持つ."""
        log_dir = str(tmp_path / "logs")
        self._setup_logs(log_dir, count=5)

        output = str(tmp_path / "output.jsonl")
        export_training_dataset(log_dir=log_dir, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                assert "features" in obj
                assert "explanation" in obj
                assert "type" in obj
                assert obj["type"] == "explanation"

    def test_deterministic_split(self, tmp_path):
        """同じシードで同じ分割になる."""
        log_dir = str(tmp_path / "logs")
        self._setup_logs(log_dir, count=20)

        out1 = str(tmp_path / "out1.jsonl")
        out2 = str(tmp_path / "out2.jsonl")

        r1 = export_training_dataset(log_dir=log_dir, output_path=out1, seed=42)
        r2 = export_training_dataset(log_dir=log_dir, output_path=out2, seed=42)

        assert r1["train"] == r2["train"]
        assert r1["val"] == r2["val"]

        with open(out1) as f1, open(out2) as f2:
            assert f1.read() == f2.read()
