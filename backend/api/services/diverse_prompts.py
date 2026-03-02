"""多様性指向プロンプトビルダー.

指定されたスタイル・着目点・深度に応じた解説生成プロンプトを構築する。
同一局面から異なる視点の解説を生成し、訓練データの多様性を確保する。
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.api.schemas.annotation import DEPTH_LEVELS, FOCUS_LABELS
from backend.api.services.commentary_enhancer import FOCUS_DESCRIPTIONS
from backend.api.services.ml_trainer import STYLES

# ---------------------------------------------------------------------------
# Style instructions
# ---------------------------------------------------------------------------
_STYLE_INSTRUCTIONS: Dict[str, str] = {
    "technical": "具体的な駒の配置や手順に言及し、数値的・論理的に解説してください。",
    "encouraging": "初心者にもわかりやすく、前向きで励ます口調で解説してください。",
    "dramatic": "緊迫感のある、ドラマチックな語り口で解説してください。",
    "neutral": "客観的で淡々とした口調で解説してください。",
}

# ---------------------------------------------------------------------------
# Depth instructions
# ---------------------------------------------------------------------------
_DEPTH_INSTRUCTIONS: Dict[str, str] = {
    "surface": "指し手の事実のみを1文で簡潔に述べてください（30文字以内）。",
    "strategic": "指し手の意図や狙いを2-3文で説明してください（30-80文字）。",
    "deep": (
        "この手の背景にある戦略や、今後の展開の可能性も含めて"
        "詳しく解説してください（80文字以上）。"
        "条件分岐（もし〜なら）も使ってください。"
    ),
}

# ---------------------------------------------------------------------------
# Phase descriptions (Japanese)
# ---------------------------------------------------------------------------
_PHASE_JP: Dict[str, str] = {
    "opening": "序盤",
    "midgame": "中盤",
    "endgame": "終盤",
}

# ---------------------------------------------------------------------------
# Diversity target combinations (underrepresented categories prioritized)
# ---------------------------------------------------------------------------
DIVERSITY_TARGETS: List[Dict[str, Any]] = [
    {"style": "technical", "focus": ["attack_pressure"], "depth": "surface"},
    {"style": "technical", "focus": ["king_safety"], "depth": "deep"},
    {"style": "technical", "focus": ["positional", "tempo"], "depth": "strategic"},
    {"style": "dramatic", "focus": ["attack_pressure"], "depth": "deep"},
    {"style": "dramatic", "focus": ["king_safety", "endgame_technique"], "depth": "strategic"},
    {"style": "dramatic", "focus": ["piece_activity"], "depth": "surface"},
    {"style": "encouraging", "focus": ["endgame_technique"], "depth": "strategic"},
    {"style": "encouraging", "focus": ["tempo"], "depth": "surface"},
    {"style": "neutral", "focus": ["positional"], "depth": "deep"},
    {"style": "neutral", "focus": ["attack_pressure", "tempo"], "depth": "strategic"},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_diverse_prompt(
    features: Dict[str, Any],
    target_style: str,
    target_focus: List[str],
    target_depth: str,
) -> str:
    """多様性制御付き解説プロンプトを生成.

    Parameters
    ----------
    features : dict
        extract_position_features() 形式の局面特徴量。
    target_style : str
        解説スタイル (technical / encouraging / dramatic / neutral)。
    target_focus : list[str]
        着目すべき要素ラベルのリスト。
    target_depth : str
        解説深度 (surface / strategic / deep)。

    Returns
    -------
    str
        Gemini API に渡すプロンプト文字列。
    """
    # Features block
    phase = _PHASE_JP.get(features.get("phase", "midgame"), "中盤")
    ks = features.get("king_safety", 50)
    pa = features.get("piece_activity", 50)
    ap = features.get("attack_pressure", 0)
    ply = features.get("ply", 0)

    features_block = (
        f"局面: {phase}（{ply}手目）\n"
        f"玉の安全度: {ks}/100\n"
        f"駒の活用度: {pa}/100\n"
        f"攻めの圧力: {ap}/100"
    )

    # Style instruction
    style_inst = _STYLE_INSTRUCTIONS.get(
        target_style, _STYLE_INSTRUCTIONS["neutral"]
    )

    # Focus instruction
    focus_descs = [
        FOCUS_DESCRIPTIONS.get(f, f)
        for f in target_focus
        if f in FOCUS_LABELS
    ]
    if not focus_descs:
        focus_descs = [FOCUS_DESCRIPTIONS.get("positional", "形勢・陣形のバランス")]
    focus_inst = "以下の点に特に注目して解説してください: " + "、".join(focus_descs)

    # Depth instruction
    depth_inst = _DEPTH_INSTRUCTIONS.get(
        target_depth, _DEPTH_INSTRUCTIONS["strategic"]
    )

    prompt = (
        "あなたは将棋の局面解説AIです。\n"
        f"\n【局面情報】\n{features_block}\n"
        f"\n【スタイル指示】\n{style_inst}\n"
        f"\n【着目点】\n{focus_inst}\n"
        f"\n【深度指示】\n{depth_inst}\n"
        "\nルール:\n"
        "- 地の文のみ。箇条書き・見出し・記号禁止\n"
        "- です/ます調\n"
        "- 文章を途中で切らないこと"
    )

    return prompt


def compute_target_match(
    target: Dict[str, Any],
    annotation: Dict[str, Any],
) -> Dict[str, Any]:
    """生成結果がターゲット指示に従えたか評価.

    Parameters
    ----------
    target : dict
        {style, focus, depth} — 指定した目標。
    annotation : dict
        annotate_text() の出力 {focus, importance, depth, style}。

    Returns
    -------
    dict
        {style_match: bool, focus_recall: float, depth_match: bool}
    """
    style_match = annotation.get("style") == target.get("style")
    depth_match = annotation.get("depth") == target.get("depth")

    target_focus = set(target.get("focus", []))
    actual_focus = set(annotation.get("focus", []))
    if target_focus:
        overlap = len(target_focus & actual_focus)
        focus_recall = round(overlap / len(target_focus), 2)
    else:
        focus_recall = 1.0

    return {
        "style_match": style_match,
        "focus_recall": focus_recall,
        "depth_match": depth_match,
    }
