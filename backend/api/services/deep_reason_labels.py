"""backend/api/services/deep_reason_labels.py

deep_reason の中間ラベル体系.
ExplanationPlanner が局面特徴量から付与し、
解説テンプレートやLLMプロンプトで利用する.

ラベル一覧:
  king_form_keep    玉形維持
  attack_continue   攻め継続
  defense_priority  受け優先
  mate_speed        寄せ速度
  material_gain     駒得優先
  outpost_build     拠点作り
  no_rush_promote   成り急がない
  piece_exchange    駒交換の判断
  tempo_gain        手得/先手権
  shape_improve     形の改善
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DeepReasonLabel:
    """1つの中間ラベル定義."""
    key: str
    name_ja: str
    description: str
    conditions: str  # 付与条件の草案


# ---------------------------------------------------------------------------
# ラベル定義
# ---------------------------------------------------------------------------

DEEP_REASON_LABELS: List[DeepReasonLabel] = [
    DeepReasonLabel(
        key="king_form_keep",
        name_ja="玉形維持",
        description="玉の囲いを崩さず安全を保つ手を選んだ",
        conditions=(
            "king_safety が高い (>= 50) かつ指し手後も king_safety が維持 "
            "(d_king_safety >= -5)。move_intent が defense/development のとき付与。"
        ),
    ),
    DeepReasonLabel(
        key="attack_continue",
        name_ja="攻め継続",
        description="攻めの手を止めず、圧力を維持・強化する",
        conditions=(
            "attack_pressure > 0 かつ d_attack_pressure >= 0。"
            "move_intent が attack のとき付与。"
            "候補手の best が attack 系の手のとき優先。"
        ),
    ),
    DeepReasonLabel(
        key="defense_priority",
        name_ja="受け優先",
        description="相手の攻めに対して受けを優先した",
        conditions=(
            "king_safety が低い (< 35) かつ move_intent が defense。"
            "または d_king_safety < -10 で危険が迫っているとき。"
        ),
    ),
    DeepReasonLabel(
        key="mate_speed",
        name_ja="寄せ速度",
        description="詰みに近い局面で寄せの速度を意識した手",
        conditions=(
            "phase == 'endgame' かつ attack_pressure >= 30。"
            "候補手に score_mate がある、または score_cp > 1000。"
            "king_safety が相手側で低いことが示唆されるとき。"
        ),
    ),
    DeepReasonLabel(
        key="material_gain",
        name_ja="駒得優先",
        description="駒得を優先する手を選んだ (または見送った)",
        conditions=(
            "move_intent が capture/sacrifice。"
            "候補手間の score_cp 差が 100 以上で、駒を取る手がbestのとき。"
            "または user_move が駒取りでないとき「駒得を見送った」として付与。"
        ),
    ),
    DeepReasonLabel(
        key="outpost_build",
        name_ja="拠点作り",
        description="将来の攻めに向けた拠点を構築する手",
        conditions=(
            "phase が midgame 以降。move_intent が development/attack。"
            "打ち駒 (drop) や前進 (advance) の手で、"
            "attack_pressure の増加 (d_attack_pressure > 5) を伴うとき。"
        ),
    ),
    DeepReasonLabel(
        key="no_rush_promote",
        name_ja="成り急がない",
        description="成れるが成らない / 即座に攻めず態勢を整える判断",
        conditions=(
            "user_move が成り (promotion) でない手を選択し、"
            "候補手のbestが成り手 ('+' 付き) のとき。"
            "または attack_pressure が上がるが king_safety が下がる場面で "
            "安全策を選んだとき。"
        ),
    ),
    DeepReasonLabel(
        key="piece_exchange",
        name_ja="駒交換の判断",
        description="駒交換の損得を判断した手",
        conditions=(
            "move_intent が capture/sacrifice/exchange。"
            "d_piece_activity の変動が大きい (abs > 10)。"
            "大駒交換後 (piece_activity の急落) の局面で特に付与。"
        ),
    ),
    DeepReasonLabel(
        key="tempo_gain",
        name_ja="手得/先手権",
        description="相手に手番を渡さず先手権を握る手",
        conditions=(
            "候補手のbestが attack/advance 系で score_cp 差が小さい (< 30)。"
            "user_move もbestと同系統の攻め手で、テンポを意識した選択。"
            "move_intent が attack かつ d_attack_pressure > 0 のとき。"
        ),
    ),
    DeepReasonLabel(
        key="shape_improve",
        name_ja="形の改善",
        description="駒の配置を改善し効率を上げる手",
        conditions=(
            "move_intent が development。d_piece_activity > 5。"
            "attack_pressure の変化が小さく (abs < 5)、"
            "直接的な攻防ではなく駒効率の改善を目的とするとき。"
        ),
    ),
]

# key → label のルックアップ
LABEL_MAP: Dict[str, DeepReasonLabel] = {lb.key: lb for lb in DEEP_REASON_LABELS}


# ---------------------------------------------------------------------------
# ラベル推定 (ルールベース)
# ---------------------------------------------------------------------------

def infer_deep_reason_labels(
    features: Optional[Dict[str, Any]] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
    user_move: Optional[str] = None,
    delta_cp: Optional[int] = None,
) -> List[str]:
    """局面情報から該当する deep_reason ラベルを推定して返す.

    Returns:
        マッチしたラベルの key リスト (優先度順, 最大3つ)
    """
    if features is None:
        features = {}
    if candidates is None:
        candidates = []

    labels: List[str] = []
    phase = features.get("phase", "unknown")
    ks = features.get("king_safety", 50)
    ap = features.get("attack_pressure", 0)
    pa = features.get("piece_activity", 50)
    intent = features.get("move_intent", "")
    td = features.get("tension_delta", {})
    d_ks = td.get("d_king_safety", 0)
    d_ap = td.get("d_attack_pressure", 0)
    d_pa = td.get("d_piece_activity", 0)

    best_move = candidates[0]["move"] if candidates else None
    best_cp = candidates[0].get("score_cp") if candidates else None
    has_mate = any(c.get("score_mate") is not None for c in candidates)

    # mate_speed
    if phase == "endgame" and (ap >= 30 or has_mate or (best_cp and best_cp > 1000)):
        labels.append("mate_speed")

    # defense_priority
    if ks < 35 and (intent == "defense" or d_ks < -10):
        labels.append("defense_priority")

    # king_form_keep
    if ks >= 50 and d_ks >= -5 and intent in ("defense", "development"):
        labels.append("king_form_keep")

    # attack_continue
    if ap > 0 and d_ap >= 0 and intent == "attack":
        labels.append("attack_continue")

    # material_gain
    if intent in ("capture", "sacrifice"):
        labels.append("material_gain")
    elif delta_cp is not None and abs(delta_cp) >= 100 and candidates:
        labels.append("material_gain")

    # no_rush_promote
    if user_move and best_move:
        user_is_promote = user_move.endswith("+")
        best_is_promote = best_move.endswith("+")
        if best_is_promote and not user_is_promote:
            labels.append("no_rush_promote")

    # outpost_build
    if phase in ("midgame", "endgame") and d_ap > 5:
        if intent in ("development", "attack") or (user_move and "*" in user_move):
            labels.append("outpost_build")

    # piece_exchange
    if intent in ("capture", "sacrifice", "exchange") and abs(d_pa) > 10:
        labels.append("piece_exchange")

    # tempo_gain
    if intent == "attack" and d_ap > 0 and delta_cp is not None and abs(delta_cp) < 30:
        labels.append("tempo_gain")

    # shape_improve
    if intent == "development" and d_pa > 5 and abs(d_ap) < 5:
        labels.append("shape_improve")

    # 重複除去して最大3つ
    seen = set()
    unique: List[str] = []
    for lb in labels:
        if lb not in seen:
            seen.add(lb)
            unique.append(lb)
    return unique[:3]
