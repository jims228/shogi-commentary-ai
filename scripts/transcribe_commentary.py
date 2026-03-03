#!/usr/bin/env python3
"""将棋解説動画の音声を Whisper で文字起こしするスクリプト.

OpenAI Whisper を使用して音声ファイルをタイムスタンプ付きJSONに変換する。
Whisper がインストールされていない場合は明確なエラーメッセージを表示。

Usage:
    python3 scripts/transcribe_commentary.py audio.wav \
      --output data/transcripts/game01_transcript.json \
      --model large-v3 \
      --language ja
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def _check_whisper() -> bool:
    """Whisper がインストールされているか確認."""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe_audio(
    audio_path: str,
    model_name: str = "base",
    language: str = "ja",
    word_timestamps: bool = True,
) -> Dict[str, Any]:
    """音声ファイルを Whisper で文字起こし.

    Parameters
    ----------
    audio_path : str
        音声ファイルパス
    model_name : str
        Whisper モデル名 (tiny/base/small/medium/large-v3)
    language : str
        言語コード
    word_timestamps : bool
        単語レベルのタイムスタンプを取得するか

    Returns
    -------
    dict
        文字起こし結果
    """
    if not _check_whisper():
        print(
            "Error: openai-whisper がインストールされていません。\n"
            "  pip install openai-whisper\n"
            "詳細: https://github.com/openai/whisper",
            file=sys.stderr,
        )
        sys.exit(1)

    import whisper

    audio_file = Path(audio_path)
    if not audio_file.exists():
        print(f"Error: audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)

    print(f"Transcribing: {audio_path}")
    t0 = time.time()
    result = model.transcribe(
        str(audio_file),
        language=language,
        word_timestamps=word_timestamps,
        verbose=False,
    )
    elapsed = time.time() - t0
    print(f"Transcription done in {elapsed:.1f}s")

    segments = _format_segments(result.get("segments", []))

    return {
        "source": str(audio_file.name),
        "model": model_name,
        "language": language,
        "segments": segments,
    }


def _format_segments(raw_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Whisper セグメントを整形.

    短すぎるセグメントを結合し、自然な文単位にまとめる。
    """
    segments: List[Dict[str, Any]] = []

    for i, seg in enumerate(raw_segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        entry = {
            "id": len(segments),
            "start": round(seg.get("start", 0.0), 2),
            "end": round(seg.get("end", 0.0), 2),
            "text": text,
        }

        # 短すぎるセグメント（2文字以下）は前のセグメントに結合
        if len(text) <= 2 and segments:
            prev = segments[-1]
            prev["end"] = entry["end"]
            prev["text"] = prev["text"] + text
            continue

        segments.append(entry)

    return segments


def load_transcript(path: str) -> Dict[str, Any]:
    """既存の文字起こしJSONを読み込み.

    Whisper なしでも手動で作成した transcript JSON を利用可能にする。

    Parameters
    ----------
    path : str
        JSON ファイルパス

    Returns
    -------
    dict
        文字起こしデータ
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    # 最低限のバリデーション
    if "segments" not in data:
        raise ValueError("Invalid transcript JSON: missing 'segments' field")
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Whisper で将棋解説音声を文字起こし"
    )
    parser.add_argument("audio", help="入力音声ファイル (wav/mp3/m4a等)")
    parser.add_argument(
        "--output", "-o",
        help="出力JSONファイル (デフォルト: data/transcripts/<input名>_transcript.json)",
    )
    parser.add_argument(
        "--model", default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper モデル (default: base)",
    )
    parser.add_argument(
        "--language", default="ja",
        help="言語コード (default: ja)",
    )
    args = parser.parse_args()

    result = transcribe_audio(
        args.audio,
        model_name=args.model,
        language=args.language,
    )

    # 出力先決定
    if args.output:
        output_path = Path(args.output)
    else:
        audio_stem = Path(args.audio).stem
        output_path = (
            _PROJECT_ROOT / "data" / "transcripts"
            / f"{audio_stem}_transcript.json"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Segments: {len(result['segments'])}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
