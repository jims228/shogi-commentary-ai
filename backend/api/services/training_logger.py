"""ML training data collection pipeline.

解説生成の入出力ペアをJSONLファイルに記録する。
将来のfine-tuningや評価用データセット構築のため。
"""
from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOG = logging.getLogger("uvicorn.error")

_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "training_logs"
)
_LOG_DIR = os.path.normpath(os.getenv("TRAINING_LOG_DIR", _DEFAULT_LOG_DIR))


def _is_enabled() -> bool:
    return os.getenv("TRAINING_LOG_ENABLED", "1") != "0"


def _ensure_dir() -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)


def _log_path(prefix: str) -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return os.path.join(_LOG_DIR, f"{prefix}_{month}.jsonl")


class TrainingLogger:
    """解説生成の入出力ペアをJSONLファイルに記録する."""

    async def log_explanation(self, record: Dict[str, Any]) -> None:
        """1手解説の入出力を記録.

        record = {
            "timestamp": ISO8601,
            "type": "explanation",
            "input": {
                "sfen": str,
                "ply": int,
                "candidates": [...],
                "user_move": str | None,
                "delta_cp": int | None,
                "features": { king_safety, piece_activity, ... } | None,
            },
            "output": {
                "explanation": str,
                "model": str,
                "tokens": { "prompt": int, "completion": int } | None,
            },
        }
        """
        if not _is_enabled():
            return
        self._append(_log_path("explanations"), record)

    async def log_digest(self, record: Dict[str, Any]) -> None:
        """棋譜ダイジェストの入出力を記録."""
        if not _is_enabled():
            return
        self._append(_log_path("digests"), record)

    def get_stats(self) -> Dict[str, Any]:
        """蓄積データの統計を返す."""
        stats: Dict[str, Any] = {"log_dir": _LOG_DIR, "files": []}
        if not os.path.isdir(_LOG_DIR):
            return stats
        for name in sorted(os.listdir(_LOG_DIR)):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(_LOG_DIR, name)
            try:
                size = os.path.getsize(path)
                with open(path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f)
                stats["files"].append({"name": name, "records": lines, "size_bytes": size})
            except Exception:
                stats["files"].append({"name": name, "records": -1, "size_bytes": -1})
        return stats

    @staticmethod
    def _append(path: str, record: Dict[str, Any]) -> None:
        try:
            _ensure_dir()
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            _LOG.warning("[training_logger] failed to write record: %s", e)


# Module-level singleton
training_logger = TrainingLogger()


# ---------------------------------------------------------------------------
# Export utility
# ---------------------------------------------------------------------------
def export_training_dataset(
    log_dir: Optional[str] = None,
    output_path: str = "training_dataset.jsonl",
    min_explanation_length: int = 20,
    val_ratio: float = 0.2,
    seed: int = 42,
) -> Dict[str, Any]:
    """JSONLログからMLトレーニング用のデータセットを生成.

    Parameters
    ----------
    log_dir : str, optional
        ログディレクトリ（デフォルトは TRAINING_LOG_DIR）
    output_path : str
        出力ファイルパス（.jsonl）。val用は末尾 _val.jsonl に自動分割。
    min_explanation_length : int
        この文字数未満の解説はフィルタ
    val_ratio : float
        val 分割比率
    seed : int
        シャッフル用乱数シード

    Returns
    -------
    dict
        {"total": int, "train": int, "val": int, "filtered": int,
         "train_path": str, "val_path": str}
    """
    src = log_dir or _LOG_DIR
    records: List[Dict[str, Any]] = []
    filtered = 0

    if not os.path.isdir(src):
        return {"total": 0, "train": 0, "val": 0, "filtered": 0,
                "train_path": "", "val_path": ""}

    for name in sorted(os.listdir(src)):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(src, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    explanation = (obj.get("output") or {}).get("explanation", "")
                    if len(explanation) < min_explanation_length:
                        filtered += 1
                        continue
                    # features + explanation のペアに整形
                    features = (obj.get("input") or {}).get("features")
                    entry = {
                        "features": features,
                        "explanation": explanation,
                        "type": obj.get("type", "unknown"),
                        "ply": (obj.get("input") or {}).get("ply"),
                        "sfen": (obj.get("input") or {}).get("sfen"),
                        "model": (obj.get("output") or {}).get("model"),
                    }
                    records.append(entry)
        except Exception:
            continue

    if not records:
        return {"total": 0, "train": 0, "val": 0, "filtered": filtered,
                "train_path": "", "val_path": ""}

    rng = random.Random(seed)
    rng.shuffle(records)

    split = max(1, int(len(records) * (1 - val_ratio)))
    train_records = records[:split]
    val_records = records[split:]

    base, ext = os.path.splitext(output_path)
    train_path = output_path
    val_path = f"{base}_val{ext}"

    def _write(path: str, data: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    _write(train_path, train_records)
    _write(val_path, val_records)

    return {
        "total": len(records),
        "train": len(train_records),
        "val": len(val_records),
        "filtered": filtered,
        "train_path": train_path,
        "val_path": val_path,
    }
