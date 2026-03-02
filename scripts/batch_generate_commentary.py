#!/usr/bin/env python3
"""棋譜リストからバッチで解説を生成し、品質評価とともに記録する.

Gemini API を使うか、--dry-run でテンプレート解説を使うか選べる。

Usage:
    python scripts/batch_generate_commentary.py --dry-run
    python scripts/batch_generate_commentary.py --dry-run --max-requests 10
    python scripts/batch_generate_commentary.py --rate-limit 5 --max-requests 50
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.position_features import extract_position_features
from backend.api.services.template_commentary import generate_template_commentary
from backend.api.services.explanation_evaluator import evaluate_explanation
from backend.api.services.training_logger import training_logger
from scripts.batch_extract_features import _parse_game_line


def _progress_path(output_dir: str) -> str:
    return os.path.join(output_dir, "batch_commentary_progress.jsonl")


def _load_progress(output_dir: str) -> set:
    """完了済み (game_index, ply) のセットを読み込む."""
    path = _progress_path(output_dir)
    done = set()
    if not os.path.exists(path):
        return done
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                done.add((obj["game_index"], obj["ply"]))
    except Exception:
        pass
    return done


def _save_progress(output_dir: str, game_index: int, ply: int) -> None:
    """完了した (game_index, ply) を追記."""
    path = _progress_path(output_dir)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"game_index": game_index, "ply": ply}) + "\n")


async def _generate_api_commentary(
    sfen: str,
    ply: int,
    features: Dict[str, Any],
    style: Optional[str] = None,
) -> str:
    """Gemini API 経由で解説を生成."""
    from backend.api.services.ai_service import AIService
    return await AIService.generate_position_comment(
        ply=ply,
        sfen=sfen,
        candidates=[],
        user_move=None,
        delta_cp=None,
        features=features,
        style=style,
    )


async def batch_generate(
    input_file: str,
    output_dir: str,
    sample_interval: int = 5,
    rate_limit: int = 10,
    max_requests: int = 100,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """棋譜ファイルからバッチで解説を生成する.

    Parameters
    ----------
    input_file : str
        1行1棋譜のUSIリスト (.txt)
    output_dir : str
        出力ディレクトリ (JSONL + progress)
    sample_interval : int
        N手ごとにサンプリング
    rate_limit : int
        API呼び出し間隔（リクエスト/分）
    max_requests : int
        最大リクエスト数
    dry_run : bool
        True の場合テンプレート解説を使用

    Returns
    -------
    dict
        統計情報
    """
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: input file not found: {input_file}", file=sys.stderr)
        return {"processed": 0, "skipped": 0, "avg_quality": 0.0, "elapsed_sec": 0.0}

    lines = [
        l.strip()
        for l in input_path.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]

    os.makedirs(output_dir, exist_ok=True)
    done = _load_progress(output_dir)

    output_path = os.path.join(output_dir, "batch_commentary.jsonl")
    sleep_interval = 60.0 / max(1, rate_limit) if not dry_run else 0.0

    total_processed = 0
    total_skipped = 0
    total_quality = 0.0
    start_time = time.time()

    with open(output_path, "a", encoding="utf-8") as out:
        for game_idx, line in enumerate(lines):
            base_position, moves = _parse_game_line(line)
            if not base_position:
                continue

            prev_features: Optional[Dict[str, Any]] = None

            for ply in range(0, len(moves) + 1, sample_interval):
                if total_processed >= max_requests:
                    break

                if (game_idx, ply) in done:
                    total_skipped += 1
                    continue

                # 局面構築
                applied_moves = moves[:ply]
                if applied_moves:
                    sfen = base_position + " moves " + " ".join(applied_moves)
                else:
                    sfen = base_position

                current_move = moves[ply] if ply < len(moves) else None

                try:
                    features = extract_position_features(
                        sfen,
                        move=current_move,
                        ply=ply,
                        prev_features=prev_features,
                    )
                except Exception as e:
                    print(
                        f"  Warning: game {game_idx + 1}, ply {ply}: {e}",
                        file=sys.stderr,
                    )
                    continue

                # 解説生成
                if dry_run:
                    commentary = generate_template_commentary(features, seed=game_idx * 1000 + ply)
                else:
                    if sleep_interval > 0 and total_processed > 0:
                        time.sleep(sleep_interval)
                    try:
                        commentary = await _generate_api_commentary(sfen, ply, features)
                    except Exception as e:
                        print(
                            f"  API error: game {game_idx + 1}, ply {ply}: {e}",
                            file=sys.stderr,
                        )
                        continue

                # 品質評価
                quality = evaluate_explanation(commentary, features)

                # レコード書き出し
                record = {
                    "game_index": game_idx,
                    "ply": ply,
                    "sfen": sfen,
                    "move": current_move,
                    "commentary": commentary,
                    "quality": quality,
                    "style": features.get("phase", "neutral"),
                    "source": "template" if dry_run else "api",
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")

                # Training logger (async)
                try:
                    await training_logger.log_explanation({
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "type": "explanation",
                        "input": {
                            "sfen": sfen,
                            "ply": ply,
                            "features": features,
                        },
                        "output": {
                            "explanation": commentary,
                            "model": "template" if dry_run else "gemini-2.5-flash-lite",
                        },
                    })
                except Exception:
                    pass

                _save_progress(output_dir, game_idx, ply)
                total_processed += 1
                total_quality += quality["total"]
                prev_features = features

            if total_processed >= max_requests:
                break

            # 進捗表示
            elapsed = time.time() - start_time
            print(
                f"\r  [{game_idx + 1}/{len(lines)}] "
                f"{total_processed} processed, {total_skipped} skipped "
                f"({elapsed:.1f}s)",
                end="",
                flush=True,
            )

    elapsed = time.time() - start_time
    print()

    avg_quality = round(total_quality / max(1, total_processed), 1)
    stats = {
        "processed": total_processed,
        "skipped": total_skipped,
        "avg_quality": avg_quality,
        "elapsed_sec": round(elapsed, 2),
    }
    print(
        f"Done: {stats['processed']} processed, "
        f"{stats['skipped']} skipped, "
        f"avg quality: {stats['avg_quality']}, "
        f"{stats['elapsed_sec']}s"
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="棋譜からバッチで解説を生成し品質評価する"
    )
    parser.add_argument(
        "--input",
        default=str(_PROJECT_ROOT / "data" / "sample_games.txt"),
        help="入力ファイル (default: data/sample_games.txt)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_PROJECT_ROOT / "data" / "batch_commentary"),
        help="出力ディレクトリ (default: data/batch_commentary)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="サンプリング間隔 (手数, default: 5)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="API呼び出し回数/分 (default: 10)",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=100,
        help="最大リクエスト数 (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="テンプレート解説を使用（API不使用）",
    )
    args = parser.parse_args()

    asyncio.run(batch_generate(
        input_file=args.input,
        output_dir=args.output_dir,
        sample_interval=args.interval,
        rate_limit=args.rate_limit,
        max_requests=args.max_requests,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
