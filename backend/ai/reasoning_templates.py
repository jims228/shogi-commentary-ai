"""
reasoning_templates.py

ルールベースの日本語テンプレートで根拠文を生成するモジュール。
特徴から自然な日本語の説明を構築します。
"""

import random
from typing import List, Dict, Any, Optional
from .reasoning_features import MoveFeatures


# テンプレート定義
STRENGTH_TEMPLATES = {
    "絶好手": [
        "非常に優秀な手で、局面を大きく好転させています。",
        "素晴らしい着眼点の一手です。",
        "この手により形勢が大幅に良くなりました。",
    ],
    "好手": [
        "良い手で、わずかに局面を改善しています。",
        "適切な判断による良手です。",
        "この手で優位を築いています。",
    ],
    "良手": [
        "自然で理にかなった手です。",
        "堅実な一手と言えるでしょう。",
        "無難な選択です。",
    ],
    "通常手": [
        "普通の手です。",
        "平凡な一手。",
        "特に問題のない手順です。",
    ],
    "疑問手": [
        "少し疑問の残る手です。",
        "他にもっと良い手がありそうです。",
        "やや不正確な判断かもしれません。",
    ],
    "悪手": [
        "明らかに悪い手です。",
        "この手は局面を悪化させています。",
        "避けるべき手でした。",
    ],
    "大悪手": [
        "非常に悪い手で、致命的なミスです。",
        "この手により形勢が大きく傾きました。",
        "大きな見落としがあります。",
    ]
}


TACTICAL_TEMPLATES = {
    "王手": [
        "王手をかけて相手を追い詰めています。",
        "王手により相手の自由を奪っています。",
        "攻撃的な王手です。",
    ],
    "駒取り": [
        "駒を取って駒得を図っています。",
        "駒交換により局面を単純化しています。",
        "相手の駒を捕獲しました。",
    ],
    "成り": [
        "駒を成って戦力を向上させています。",
        "成ることで攻撃力を高めています。",
        "駒の価値を上げる成りです。",
    ],
    "打ち駒": [
        "持ち駒を効果的に使っています。",
        "駒を打って局面に変化をもたらしています。",
        "適所への駒打ちです。",
    ],
    "囲い": [
        "玉の安全性を高めています。",
        "守備を固めています。",
        "堅陣を構築しています。",
    ]
}


STRATEGIC_TEMPLATES = {
    "攻め": [
        "積極的な攻めの姿勢を見せています。",
        "攻撃的な手で相手を圧迫しています。",
        "攻勢に転じています。",
    ],
    "守り": [
        "守備を重視した手です。",
        "慎重な守りの姿勢です。",
        "安全を第一に考えた手順です。",
    ],
    "筋を開ける": [
        "角道や飛車筋を活用しています。",
        "大駒の利きを通しています。",
        "攻撃路を開拓しています。",
    ],
    "駒組み": [
        "駒の働きを良くしています。",
        "効率的な駒組みです。",
        "駒の連携を図っています。",
    ],
    "中央制圧": [
        "中央を制圧する狙いです。",
        "盤面の要所を押さえています。",
        "中央での主導権を握っています。",
    ]
}


PHASE_TEMPLATES = {
    "序盤": [
        "序盤らしい駒組みの一手です。",
        "開始局面での基本的な手順です。",
        "定跡に沿った手です。",
    ],
    "middle": [
        "中盤戦での重要な判断です。",
        "戦いが激化する局面での一手です。",
    ],
    "終盤": [
        "終盤戦での正確性が求められる局面です。",
        "詰みを目指した手順です。",
        "勝負の分かれ目となる一手です。",
    ]
}


IMPROVEMENT_TEMPLATES = [
    "代案として{bestmove}が考えられます。",
    "{bestmove}の方が良かったかもしれません。",
    "エンジン推奨は{bestmove}です。",
    "最善手は{bestmove}とされています。",
]


def generate_reasoning_text(features: MoveFeatures, note: Dict[str, Any]) -> str:
    """
    特徴から日本語の根拠文を生成
    
    Args:
        features: 抽出された特徴
        note: 元のMoveNoteデータ
        
    Returns:
        str: 生成された根拠文
    """
    parts = []
    
    # 1. 評価値ベースの判定
    if features.delta_cp is not None:
        strength = _classify_move_strength(features.delta_cp)
        template = random.choice(STRENGTH_TEMPLATES.get(strength, STRENGTH_TEMPLATES["通常手"]))
        parts.append(template)
    
    # 2. 戦術的特徴
    tactical_parts = []
    
    if features.is_check:
        tactical_parts.append(random.choice(TACTICAL_TEMPLATES["王手"]))
    if features.is_capture:
        tactical_parts.append(random.choice(TACTICAL_TEMPLATES["駒取り"]))
    if features.is_promotion:
        tactical_parts.append(random.choice(TACTICAL_TEMPLATES["成り"]))
    if features.is_drop:
        tactical_parts.append(random.choice(TACTICAL_TEMPLATES["打ち駒"]))
    if features.is_castle:
        tactical_parts.append(random.choice(TACTICAL_TEMPLATES["囲い"]))
    
    if tactical_parts:
        parts.append(tactical_parts[0])  # 最初の特徴のみ使用
    
    # 3. 戦略的特徴
    strategic_parts = []
    
    if features.is_attack:
        strategic_parts.append(random.choice(STRATEGIC_TEMPLATES["攻め"]))
    elif features.is_defense:
        strategic_parts.append(random.choice(STRATEGIC_TEMPLATES["守り"]))
    
    if features.opens_line:
        strategic_parts.append(random.choice(STRATEGIC_TEMPLATES["筋を開ける"]))
    if features.develops_piece:
        strategic_parts.append(random.choice(STRATEGIC_TEMPLATES["駒組み"]))
    if features.centralizes:
        strategic_parts.append(random.choice(STRATEGIC_TEMPLATES["中央制圧"]))
    
    if strategic_parts:
        parts.append(strategic_parts[0])  # 最初の特徴のみ使用
    
    # 4. 局面フェーズ
    if features.position_phase in PHASE_TEMPLATES:
        phase_template = random.choice(PHASE_TEMPLATES[features.position_phase])
        if len(parts) == 1:  # 他の説明が少ない場合のみ追加
            parts.append(phase_template)
    
    # 5. 改善案の提案
    if not features.is_best_move and features.bestmove:
        improvement_template = random.choice(IMPROVEMENT_TEMPLATES)
        improvement_text = improvement_template.format(bestmove=features.bestmove)
        parts.append(improvement_text)
    
    # 文章を結合
    if not parts:
        return "普通の一手です。"
    
    return " ".join(parts[:3])  # 最大3つの要素で構成


def _classify_move_strength(delta_cp: int) -> str:
    """評価値変化から手の強さを分類"""
    if delta_cp >= 200:
        return "絶好手"
    elif delta_cp >= 120:
        return "好手"
    elif delta_cp >= 30:
        return "良手"
    elif delta_cp >= -30:
        return "通常手"
    elif delta_cp >= -80:
        return "疑問手"
    elif delta_cp >= -150:
        return "悪手"
    else:
        return "大悪手"


def generate_summary_from_features(notes: List[Dict[str, Any]], 
                                 position_features: Dict[str, Any]) -> str:
    """
    全体特徴から棋譜の総括を生成
    
    Args:
        notes: 全てのMoveNoteのリスト
        position_features: 局面全体の特徴
        
    Returns:
        str: 総括文
    """
    parts = []
    
    total_moves = position_features.get("total_moves", 0)
    balance = position_features.get("game_balance", "balanced")
    lead_changes = position_features.get("lead_changes", 0)
    
    # 基本情報
    parts.append(f"{total_moves}手の将棋です。")
    
    # ゲームバランス
    balance_texts = {
        "balanced": "互角の戦いでした。",
        "advantage": "一方的な展開もありましたが、見応えのある内容でした。",
        "decisive": "大差の付いた対局でした。"
    }
    parts.append(balance_texts.get(balance, ""))
    
    # リードチェンジ
    if lead_changes > 3:
        parts.append("形勢が目まぐるしく変わる激戦でした。")
    elif lead_changes > 1:
        parts.append("数回の形勢逆転がありました。")
    elif lead_changes == 1:
        parts.append("一度の形勢逆転がありました。")
    
    # 特徴的な手の統計
    def _dcp(n):
        v = n.get("delta_cp")
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0
    
    good_moves = sum(1 for note in notes if _dcp(note) >= 120)
    bad_moves = sum(1 for note in notes if _dcp(note) <= -80)
    
    if good_moves > bad_moves * 2:
        parts.append("全体的に正確性の高い棋譜でした。")
    elif bad_moves > good_moves * 2:
        parts.append("いくつかの疑問手が見られました。")
    else:
        parts.append("好手と疑問手が混在した内容でした。")
    
    return " ".join(parts)


def generate_contextual_explanation(features: MoveFeatures, 
                                   previous_features: Optional[MoveFeatures],
                                   context: Dict[str, Any]) -> str:
    """
    文脈を考慮した説明を生成
    
    Args:
        features: 現在の手の特徴
        previous_features: 前の手の特徴
        context: 追加の文脈情報
        
    Returns:
        str: 文脈を考慮した説明
    """
    explanation = generate_reasoning_text(features, {})
    
    # 前の手との関連性を考慮
    if previous_features:
        if features.is_check and previous_features.is_attack:
            explanation = "攻めを継続し、" + explanation.lower()
        elif features.is_defense and previous_features.is_attack:
            explanation = "攻勢から一転して守りに回り、" + explanation.lower()
        elif features.is_capture and previous_features.is_capture:
            explanation = "駒交換を続け、" + explanation.lower()
    
    return explanation


# 将棋格言・教訓のテンプレート
PROVERBS_TEMPLATES = {
    "攻め": [
        "攻撃は最大の防御と言います。",
        "先手必勝の精神を体現した手です。",
    ],
    "守り": [
        "玉の早逃げ八手の得とも言われます。",
        "堅い玉、薄い玉を意識した手です。",
    ],
    "駒得": [
        "駒得は一局の大勢を左右します。",
    ],
    "駒交換": [
        "駒の損得を見極めることが大切です。",
    ]
}


# フェーズ別テンプレート（v2拡張）
PHASE_CONTEXT_TEMPLATES = {
    "opening": {
        "develop": ["序盤らしい駒組みで、バランスの取れた展開です。", "駒の協調を重視した手順です。"],
        "attack": ["序盤から積極的に仕掛ける意欲的な手です。", "早い攻撃で相手を牽制しています。"],
        "castle": ["玉の安全確保を優先した慎重な判断です。", "堅陣を目指す手堅い方針です。"],
        "default": ["序盤戦の基本的な手順です。"]
    },
    "middlegame": {
        "attack": ["中盤戦での積極的な攻撃です。", "戦いの局面で攻勢に転じました。"],
        "defend": ["中盤の複雑な局面で守りを固めています。", "相手の攻撃を受け止める手です。"],
        "trade": ["中盤での駒交換により局面を整理しています。", "駒の損得を見極めた交換です。"],
        "default": ["中盤戦での重要な選択です。"]
    },
    "endgame": {
        "endgame-technique": ["終盤の正確性が求められる局面です。", "詰みを目指した精密な手順です。"],
        "attack": ["終盤での決定的な攻撃です。", "勝負を決する攻めの手です。"],
        "promotion": ["終盤での駒の成りが効果的です。", "成り駒による戦力アップです。"],
        "default": ["終盤戦での慎重な判断です。"]
    }
}


# 手の種類別テンプレート（v2追加）
MOVE_TYPE_TEMPLATES = {
    "check": ["王手により相手の動きを制限しています。", "王手で攻撃の主導権を握っています。"],
    "capture": ["駒を取って材質面で優位に立っています。", "駒得を活かした展開を目指します。"],
    "promote": ["駒の成りで戦力を大幅に強化しました。", "成り駒の威力を活用する手です。"],
    "sacrifice": ["一時的な犠牲で戦術的な利益を狙っています。", "駒損を承知で攻撃を継続します。"],
    "quiet-improve": ["静かながら局面を改善する手です。", "じわじわと優位を広げています。"],
    "blunder-flag": ["この手は局面を大きく悪化させています。", "避けるべき大きなミスです。"],
    "normal": ["標準的な手順です。", "自然な流れの一手です。"]
}


def generate_reasoning_text_v2(features: MoveFeatures, note: Dict[str, Any], 
                               context: Dict[str, Any]) -> str:
    """
    特徴から日本語の根拠文を生成（v2版）
    
    Args:
        features: 抽出された特徴
        note: 元のMoveNoteデータ
        context: フェーズ、計画、手の種類などの文脈
        
    Returns:
        str: 生成された根拠文
    """
    parts = []
    
    phase = context.get("phase", "middlegame")
    plan = context.get("plan", "develop")
    move_type = context.get("move_type", "normal")
    
    # 1. フェーズと計画に基づく文脈テンプレート
    phase_templates = PHASE_CONTEXT_TEMPLATES.get(phase, {})
    context_template = phase_templates.get(plan, phase_templates.get("default", ["普通の手です。"]))
    parts.append(random.choice(context_template))
    
    # 2. 手の種類に基づく説明
    if move_type in MOVE_TYPE_TEMPLATES:
        type_template = random.choice(MOVE_TYPE_TEMPLATES[move_type])
        parts.append(type_template)
    
    # 3. 評価値に基づく判定（既存の強度分類）
    if features.delta_cp is not None:
        strength = _classify_move_strength(features.delta_cp)
        if strength != "通常手":
            strength_template = random.choice(STRENGTH_TEMPLATES.get(strength, ["特記事項なし。"]))
            parts.append(strength_template)
    
    # 4. PV比較情報の追加
    pv_summary = context.get("pv_summary", {})
    why_better = pv_summary.get("why_better", [])
    if why_better and why_better != ["最善手です"]:
        improvement_text = f"改善案: {', '.join(why_better[:2])}。"
        parts.append(improvement_text)
    elif not features.is_best_move and features.bestmove:
        improvement_template = random.choice(IMPROVEMENT_TEMPLATES)
        improvement_text = improvement_template.format(bestmove=features.bestmove)
        parts.append(improvement_text)
    
    # 文章を結合（最大3つの要素）
    if not parts:
        return "普通の一手です。"
    
    # 重複排除と長さ調整
    unique_parts = []
    total_length = 0
    for part in parts[:3]:
        if part not in unique_parts and total_length + len(part) < 150:
            unique_parts.append(part)
            total_length += len(part)
    
    return " ".join(unique_parts) if unique_parts else "普通の一手です。"


def generate_contextual_explanation_v2(features: MoveFeatures,
                                       context: Dict[str, Any],
                                       previous_context: Optional[Dict[str, Any]] = None) -> str:
    """
    文脈を考慮したv2説明を生成
    
    Args:
        features: 現在の手の特徴
        context: 現在の文脈（フェーズ、計画など）
        previous_context: 前の手の文脈
        
    Returns:
        str: 文脈を考慮した説明
    """
    base_explanation = generate_reasoning_text_v2(features, {}, context)
    
    # 前の手との関連性を考慮
    if previous_context:
        prev_plan = previous_context.get("plan")
        curr_plan = context.get("plan")
        
        if prev_plan == "attack" and curr_plan == "attack":
            base_explanation = "攻撃を継続し、" + base_explanation.lower()
        elif prev_plan == "attack" and curr_plan == "defend":
            base_explanation = "攻勢から一転して守りに回り、" + base_explanation.lower()
        elif prev_plan == "develop" and curr_plan == "attack":
            base_explanation = "駒組みから仕掛けに転じ、" + base_explanation.lower()
        elif context.get("phase") != previous_context.get("phase"):
            phase_map = {"opening": "序盤", "middlegame": "中盤", "endgame": "終盤"}
            curr_phase_name = phase_map.get(context.get("phase", ""), "")
            if curr_phase_name:
                base_explanation = f"{curr_phase_name}に入り、" + base_explanation.lower()
    
    return base_explanation


def add_educational_note(features: MoveFeatures) -> Optional[str]:
    """教育的な補足説明を追加"""
    if features.is_capture and features.delta_cp and features.delta_cp > 100:
        return random.choice(PROVERBS_TEMPLATES["駒得"])
    elif features.is_defense and features.position_phase == "endgame":
        return random.choice(PROVERBS_TEMPLATES["守り"])
    elif features.is_attack and features.delta_cp and features.delta_cp > 50:
        return random.choice(PROVERBS_TEMPLATES["攻め"])
    
    return None