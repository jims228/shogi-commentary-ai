"""特徴量からルールベースのテンプレート解説を生成する.

Gemini APIの代替として、学習データのベースライン品質を確保する。
将来MLモデルに置き換え予定。
"""
from __future__ import annotations

import random
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# フェーズ別テンプレート
# ---------------------------------------------------------------------------
_OPENING_TEMPLATES = [
    "序盤の駒組みが進んでいます。{safety_desc}。{intent_desc}",
    "まだ序盤の段階で、両者ともに陣形を整えています。{safety_desc}。{intent_desc}",
    "駒組みの途中で、{intent_desc}。{safety_desc}。",
]

_MIDGAME_TEMPLATES = [
    "中盤に入り、{pressure_desc}。{intent_desc}。{safety_desc}。",
    "中盤の戦いが始まっています。{intent_desc}。{pressure_desc}。",
    "仕掛けのタイミングを伺う局面です。{safety_desc}。{intent_desc}。",
]

_ENDGAME_TEMPLATES = [
    "終盤に突入しました。{pressure_desc}。{intent_desc}。{safety_desc}。",
    "寄せ合いの終盤戦です。{intent_desc}。{pressure_desc}。",
    "終盤の追い込みです。{safety_desc}。{pressure_desc}。{intent_desc}。",
]

# ---------------------------------------------------------------------------
# 意図別テンプレート
# ---------------------------------------------------------------------------
_INTENT_DESCRIPTIONS = {
    "attack": [
        "攻めの手を繰り出しています",
        "積極的に攻撃を仕掛けています",
        "相手の陣形を崩しにかかっています",
    ],
    "defense": [
        "守りを固めています",
        "受けの手で陣形を補強しています",
        "自玉の安全を確保する一手です",
    ],
    "exchange": [
        "駒の交換が行われました",
        "駒の交換を通じて局面を動かしています",
        "互いの駒を取り合う展開です",
    ],
    "sacrifice": [
        "駒を犠牲にして攻め込んでいます",
        "捨て駒の筋で勝負に出ています",
        "大胆な駒の犠牲で勝機を探っています",
    ],
    "development": [
        "駒の展開を進めています",
        "効率良く駒を活用しています",
        "駒の配置を改善しています",
    ],
    None: [
        "局面を進めています",
        "次の構想を練る一手です",
    ],
}

# ---------------------------------------------------------------------------
# 数値記述
# ---------------------------------------------------------------------------

def _describe_safety_text(value: int) -> str:
    """king_safety の値を人間可読な日本語に変換."""
    if value >= 70:
        return "玉の囲いは堅く安定しています"
    if value >= 50:
        return "玉の安全度はまずまずの水準です"
    if value >= 30:
        return "玉の守りにやや不安が残ります"
    return "玉が危険な状態にあります"


def _describe_pressure_text(value: int) -> str:
    """attack_pressure の値を人間可読な日本語に変換."""
    if value >= 60:
        return "相手玉への攻撃圧力が非常に強い状態です"
    if value >= 35:
        return "攻めの形が整いつつあります"
    if value >= 15:
        return "攻撃態勢はまだ構築途中です"
    return "まだ攻めの準備段階です"


def _describe_activity_text(value: int) -> str:
    """piece_activity の値を人間可読な日本語に変換."""
    if value >= 60:
        return "駒の働きが良く活発です"
    if value >= 35:
        return "駒はそれなりに活用されています"
    return "駒の活用がまだ十分ではありません"


# ---------------------------------------------------------------------------
# 公開API
# ---------------------------------------------------------------------------

def generate_template_commentary(
    features: Dict[str, Any],
    seed: Optional[int] = None,
) -> str:
    """特徴量からルールベースのテンプレート解説を生成する.

    Parameters
    ----------
    features : dict
        extract_position_features の出力
    seed : int, optional
        乱数シード（再現性用）

    Returns
    -------
    str
        日本語の解説テキスト（50-200文字程度）
    """
    rng = random.Random(seed)

    phase = features.get("phase", "midgame")
    intent = features.get("move_intent")
    king_safety = features.get("king_safety", 50)
    attack_pressure = features.get("attack_pressure", 0)
    piece_activity = features.get("piece_activity", 50)

    # フェーズ別テンプレート選択
    if phase == "opening":
        templates = _OPENING_TEMPLATES
    elif phase == "endgame":
        templates = _ENDGAME_TEMPLATES
    else:
        templates = _MIDGAME_TEMPLATES

    template = rng.choice(templates)

    # 意図記述
    intent_options = _INTENT_DESCRIPTIONS.get(intent, _INTENT_DESCRIPTIONS[None])
    intent_desc = rng.choice(intent_options)

    # 数値記述
    safety_desc = _describe_safety_text(king_safety)
    pressure_desc = _describe_pressure_text(attack_pressure)

    # テンプレート適用
    text = template.format(
        safety_desc=safety_desc,
        pressure_desc=pressure_desc,
        intent_desc=intent_desc,
    )

    # 駒活用の情報を追加（文字数が短い場合）
    if len(text) < 80:
        text += f"　{_describe_activity_text(piece_activity)}。"

    return text
