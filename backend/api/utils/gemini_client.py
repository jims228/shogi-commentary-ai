"""
backend/api/utils/gemini_client.py
------------------------------------
Gemini API の設定・モデル名解決の単一情報源 (Single Source of Truth)。

すべての Gemini 呼び出しはここから `ensure_configured` / `get_model_name`
をインポートして使う。各ファイルが直接 genai.configure() を呼ばない。

設計方針:
- configure は遅延実行 (import 時ではなく呼び出し時)
- APIキーが変わったら自動で再設定 (dev/テストで便利)
- デフォルトモデルは gemini-2.0-flash (gemini-1.5-flash ハードコード禁止)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import google.generativeai as genai

_LOG = logging.getLogger("uvicorn.error")
_CONFIGURED_FOR_KEY: Optional[str] = None


def _api_key() -> Optional[str]:
    k = os.getenv("GEMINI_API_KEY")
    return k.strip() if isinstance(k, str) and k.strip() else None


def ensure_configured() -> Optional[str]:
    """
    google.generativeai を遅延設定して API キーを返す。
    GEMINI_API_KEY が未設定なら None を返す（呼び出し元は早期リターンすること）。
    キーが変わった場合は自動で再設定する。
    """
    global _CONFIGURED_FOR_KEY
    key = _api_key()
    if not key:
        return None
    if _CONFIGURED_FOR_KEY != key:
        genai.configure(api_key=key)
        _CONFIGURED_FOR_KEY = key
        _LOG.info("[gemini_client] configured (key suffix=...%s)", key[-4:])
    return key


def get_model_name(default: str = "gemini-2.0-flash") -> str:
    """
    使用する Gemini モデル名を返す。

    優先順:
      1. GEMINI_EXPLAIN_MODEL 環境変数 (rewrite 専用オーバーライド)
      2. GEMINI_MODEL 環境変数
      3. `default` 引数 (gemini-2.0-flash)
    """
    raw = (os.getenv("GEMINI_EXPLAIN_MODEL") or os.getenv("GEMINI_MODEL") or "").strip()
    return raw or default
