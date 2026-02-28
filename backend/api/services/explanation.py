"""
backend/api/services/explanation.py
解説生成サービス

エンジン評価値・特徴量をもとに LLM（Gemini）で解説文を生成する。
既存プロジェクトの shogi_explain_core.py / ai_explain_json.py から移植予定。
"""
from __future__ import annotations

import os
from typing import Optional

from backend.api.utils.gemini_client import ensure_configured, get_model_name


async def generate_explanation(
    move: str,
    position: str,
    eval_before: Optional[int] = None,
    eval_after: Optional[int] = None,
) -> Optional[str]:
    """
    1手の解説文を生成して返す。
    USE_LLM=0 の場合は None を返す。

    TODO: プロンプト設計・構造化出力の実装
    """
    if os.getenv("USE_LLM", "0") != "1":
        return None

    key = ensure_configured()
    if not key:
        return None

    model_name = get_model_name()
    # TODO: LLM呼び出し実装
    return None
