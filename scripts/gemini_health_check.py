#!/usr/bin/env python3
"""Gemini API 接続テスト・ヘルスチェック.

Usage:
    python scripts/gemini_health_check.py
    python scripts/gemini_health_check.py --prompt "将棋の飛車の特徴は？"
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

import google.generativeai as genai  # noqa: E402
from google.api_core import exceptions as gax_exceptions  # noqa: E402

from backend.api.utils.gemini_client import ensure_configured, get_model_name  # noqa: E402

# Cost constants (Gemini Flash family pricing, approximate)
_INPUT_COST_PER_1M = 0.075  # USD per 1M input tokens
_OUTPUT_COST_PER_1M = 0.30  # USD per 1M output tokens
_USD_TO_JPY = 150.0


def check_connectivity(prompt: str = "こんにちは") -> Dict[str, Any]:
    """Gemini APIへの接続テストを実行.

    Returns
    -------
    dict
        status, model_name, latency_ms, prompt_tokens,
        completion_tokens, estimated_cost_jpy, response_preview, error
    """
    result: Dict[str, Any] = {
        "status": "UNKNOWN",
        "model_name": "",
        "latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_jpy": 0.0,
        "response_preview": "",
        "error": None,
    }

    key = ensure_configured()
    if not key:
        result["status"] = "NO_KEY"
        result["error"] = "GEMINI_API_KEY is not set or empty"
        return result

    model_name = get_model_name()
    result["model_name"] = model_name

    try:
        model = genai.GenerativeModel(
            model_name,
            generation_config=genai.types.GenerationConfig(max_output_tokens=200),
        )

        start = time.monotonic()
        res = model.generate_content(prompt)
        elapsed = time.monotonic() - start

        result["latency_ms"] = round(elapsed * 1000)

        if hasattr(res, "usage_metadata") and res.usage_metadata:
            meta = res.usage_metadata
            result["prompt_tokens"] = meta.prompt_token_count or 0
            result["completion_tokens"] = meta.candidates_token_count or 0

        input_cost = (result["prompt_tokens"] / 1_000_000) * _INPUT_COST_PER_1M
        output_cost = (result["completion_tokens"] / 1_000_000) * _OUTPUT_COST_PER_1M
        result["estimated_cost_jpy"] = round((input_cost + output_cost) * _USD_TO_JPY, 4)

        text = (res.text or "").strip()
        result["response_preview"] = text[:80] + ("..." if len(text) > 80 else "")
        result["status"] = "OK"

    except (gax_exceptions.ResourceExhausted, gax_exceptions.TooManyRequests) as e:
        result["status"] = "RATE_LIMITED"
        result["error"] = str(e)[:200]

    except gax_exceptions.GoogleAPICallError as e:
        result["status"] = "API_ERROR"
        result["error"] = str(e)[:200]

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)[:200]

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini API 接続テスト")
    parser.add_argument("--prompt", default="こんにちは", help="テスト用プロンプト")
    args = parser.parse_args()

    result = check_connectivity(args.prompt)

    print()
    print("=" * 40)
    print("  Gemini Health Check")
    print("=" * 40)
    print(f"  Status:            {result['status']}")
    print(f"  Model:             {result['model_name'] or '(not resolved)'}")
    print(f"  Latency:           {result['latency_ms']} ms")
    print(f"  Prompt tokens:     {result['prompt_tokens']}")
    print(f"  Completion tokens: {result['completion_tokens']}")
    print(f"  Estimated cost:    ¥{result['estimated_cost_jpy']}")
    if result["response_preview"]:
        print(f"  Response preview:  {result['response_preview']}")
    if result["error"]:
        print(f"  Error:             {result['error']}")
    print("=" * 40)
    print()

    sys.exit(0 if result["status"] == "OK" else 1)


if __name__ == "__main__":
    main()
