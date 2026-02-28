"""
将棋AI注釈システムのAI層（根拠の言語化）

このモジュールは以下の機能を提供します:
- エンジン出力からの特徴抽出
- ルールベースの日本語テンプレート生成
- LLMによる自然な言い換え
- 統合推論機能
"""

from .reasoning import build_reasoning

__all__ = ["build_reasoning"]