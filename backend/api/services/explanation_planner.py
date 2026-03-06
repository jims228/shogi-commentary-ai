"""構造化解説プラン生成モジュール.

局面の特徴量 + 盤面分析 + 前後文脈から、LLMに渡す前の
構造化中間表現（ExplanationPlan）を生成する。

設計意図:
- LLMに直接「80文字で解説して」と投げる代わりに、
  まず「何を・なぜ・どう言うべきか」を構造化する
- 中間表現があれば、LLMの出力品質が向上し、
  どこでズレたか検証可能になる
- 前後文脈を含めることで、流れを意識した解説が可能になる

Usage::

    from backend.api.services.explanation_planner import ExplanationPlanner

    planner = ExplanationPlanner()
    plan = planner.build_plan(
        sfen="position startpos moves 7g7f 3c3d ...",
        move="7f7e",
        ply=23,
        candidates=[{"move": "7f7e", "score_cp": 145}],
        delta_cp=-50,
        prev_moves=["2g2f", "8c8d", "7g7f"],  # 直前3手
    )
    print(plan.topic_keyword)  # "飛車先の歩交換"
    print(plan.to_prompt_block())  # LLMプロンプト用テキスト
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.api.services.board_analyzer import BoardAnalyzer, BoardAnalysis
from backend.api.services.position_features import extract_position_features
from backend.api.utils.shogi_explain_core import (
    PIECE_JP,
    PIECE_VALUE,
    apply_usi_move,
    parse_position_cmd,
    piece_kind_upper,
    piece_side,
)
from backend.api.utils.shogi_utils import ShogiUtils


# ---------------------------------------------------------------------------
# ExplanationPlan データクラス
# ---------------------------------------------------------------------------

@dataclass
class ExplanationPlan:
    """LLM生成の前段となる構造化解説プラン."""

    # 流れ: この手が対局の中でどういう位置づけか
    flow: str = ""  # "攻めの継続" / "守りから反撃" / "局面転換" / "駒組み"

    # 話題の中心キーワード: 読者に刺さる概念
    topic_keyword: str = ""  # "飛車成り" / "と金攻め" / "穴熊崩し"

    # 戦術モチーフ: 手筋・テクニック
    tactical_motif: Optional[str] = None  # "王手飛車" / "両取り" / "田楽刺し"

    # 戦略テーマ: 大局的な方針
    strategic_theme: str = ""  # "手厚い攻め" / "速い寄せ" / "持久戦"

    # 表層的理由: なぜこの手を指したか (1文)
    surface_reason: str = ""

    # 深層理由: 代替手との比較 (1文)
    deep_reason: str = ""

    # 根拠リスト
    evidence: List[str] = field(default_factory=list)

    # 確信度 (0-1)
    confidence: float = 0.5

    # 直前の流れ要約
    context_summary: str = ""

    # 解説ヒント (BoardAnalyzer由来)
    commentary_hints: List[str] = field(default_factory=list)

    # 囲い情報
    castle_info: str = ""

    # 形勢判断
    evaluation_summary: str = ""

    def to_prompt_block(self) -> str:
        """LLMプロンプトに埋め込む構造化ブロックを生成."""
        lines = []

        if self.context_summary:
            lines.append(f"【直前の流れ】{self.context_summary}")

        lines.append(f"【この手の位置づけ】{self.flow}")

        if self.topic_keyword:
            lines.append(f"【注目ポイント】{self.topic_keyword}")

        if self.tactical_motif:
            lines.append(f"【手筋】{self.tactical_motif}")

        if self.strategic_theme:
            lines.append(f"【戦略テーマ】{self.strategic_theme}")

        if self.castle_info:
            lines.append(f"【囲い】{self.castle_info}")

        if self.evaluation_summary:
            lines.append(f"【形勢】{self.evaluation_summary}")

        if self.surface_reason:
            lines.append(f"【この手の理由】{self.surface_reason}")

        if self.deep_reason:
            lines.append(f"【代替手との比較】{self.deep_reason}")

        if self.evidence:
            lines.append("【根拠】" + "／".join(self.evidence[:3]))

        if self.commentary_hints:
            lines.append("【解説ヒント】" + "。".join(self.commentary_hints[:3]))

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """ログ・検証用にdict化."""
        return {
            "flow": self.flow,
            "topic_keyword": self.topic_keyword,
            "tactical_motif": self.tactical_motif,
            "strategic_theme": self.strategic_theme,
            "surface_reason": self.surface_reason,
            "deep_reason": self.deep_reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "context_summary": self.context_summary,
            "commentary_hints": self.commentary_hints,
            "castle_info": self.castle_info,
            "evaluation_summary": self.evaluation_summary,
        }


# ---------------------------------------------------------------------------
# 定数・マッピング
# ---------------------------------------------------------------------------

_PHASE_JP = {"opening": "序盤", "midgame": "中盤", "endgame": "終盤"}

_INTENT_TO_FLOW = {
    "attack": "攻めの継続",
    "defense": "守りの手",
    "exchange": "駒交換",
    "sacrifice": "勝負手",
    "development": "駒組み・陣形整備",
}

_INTENT_TO_THEME = {
    "attack": "積極的な攻め",
    "defense": "堅実な受け",
    "exchange": "駒のさばき合い",
    "sacrifice": "踏み込んだ勝負",
    "development": "陣形の整備",
}


# ---------------------------------------------------------------------------
# キーワード抽出
# ---------------------------------------------------------------------------

def _extract_topic_keyword(
    move: str,
    features: Dict[str, Any],
    board_analysis: BoardAnalysis,
    captured_piece: Optional[str],
) -> str:
    """手の内容から読者に刺さるキーワードを抽出."""

    is_drop = "*" in move
    is_promotion = move.endswith("+")

    # 成り駒系
    if is_promotion:
        if not is_drop:
            pos = parse_position_cmd("position startpos")  # dummy
            # move の元の駒を推定: board_analysis.move_impact から
            impact = board_analysis.move_impact or {}
            moved = impact.get("moved_piece", "")
            if "飛" in moved:
                return "飛車成り（龍の誕生）"
            if "角" in moved:
                return "角成り（馬の誕生）"
            if "銀" in moved:
                return "銀が成って攻めに加勢"
            if "桂" in moved:
                return "桂馬の成り"
            return f"{moved}成り"

    # 駒打ち
    if is_drop:
        piece_char = move.split("*")[0].upper()
        piece_jp = PIECE_JP.get(piece_char, piece_char)
        return f"{piece_jp}打ちの一手"

    # 駒取り
    if captured_piece:
        cap_kind = piece_kind_upper(captured_piece)
        cap_jp = PIECE_JP.get(cap_kind, cap_kind)
        cap_val = PIECE_VALUE.get(cap_kind, 0)
        if cap_val >= 8:
            return f"{cap_jp}を奪う大きな駒取り"
        if cap_val >= 5:
            return f"{cap_jp}を取って駒得"
        return f"{cap_jp}を取る"

    # 特殊な盤面状況
    threats = board_analysis.threats
    for t in threats:
        if t.get("type") == "check":
            return "王手で迫る"
        if t.get("type") == "fork_potential":
            return "両取りの筋"

    # 浮き駒: 駒名だけ表示（座標は避ける）
    hanging = board_analysis.hanging_pieces
    if hanging:
        top = hanging[0]
        piece_name = top.get("piece", "駒")
        # 座標表記（例: "4d銀"）から駒名だけ抽出
        clean_name = piece_name
        for ch in "0123456789abcdefghi":
            clean_name = clean_name.replace(ch, "")
        clean_name = clean_name.strip() or "駒"
        return f"{clean_name}が浮いている局面"

    # 汎用
    phase = features.get("phase", "midgame")
    intent = features.get("move_intent", "development")
    if phase == "opening":
        return "序盤の駒組み"
    if phase == "endgame":
        return "終盤の寄せ"
    if intent == "attack":
        return "攻めの手"
    if intent == "defense":
        return "受けの手"

    return "局面を進める一手"


def _detect_tactical_motif(board_analysis: BoardAnalysis) -> Optional[str]:
    """戦術モチーフを検出."""
    threats = board_analysis.threats

    for t in threats:
        if t.get("type") == "fork_potential":
            return "両取り（フォーク）"
        if t.get("type") == "check":
            return "王手"

    impact = board_analysis.move_impact or {}
    if impact.get("opened_lines"):
        return "大駒の筋通し"
    if impact.get("is_promotion"):
        return "成り駒で攻めの強化"

    hanging = board_analysis.hanging_pieces
    if len(hanging) >= 2:
        return "浮き駒が多い不安定な局面"

    return None


# ---------------------------------------------------------------------------
# 前後文脈の構築
# ---------------------------------------------------------------------------

def _build_context_summary(
    prev_moves: List[str],
    sfen_base: str,
    current_ply: int,
) -> str:
    """直前の数手から流れを要約."""
    if not prev_moves:
        return ""

    # 各手を日本語に変換
    move_descriptions = []
    # prev_moves は直前の手を新しい順ではなく、古い順 (時系列順) で格納
    n_prev = len(prev_moves)
    start_ply = max(1, current_ply - n_prev)

    for i, mv in enumerate(prev_moves):
        ply = start_ply + i
        turn = "b" if ply % 2 == 1 else "w"
        prefix = "▲" if turn == "b" else "△"
        label = ShogiUtils.format_move_label(mv, turn)
        move_descriptions.append(f"{ply}手目{label}")

    if len(move_descriptions) <= 3:
        return " → ".join(move_descriptions)
    return " → ".join(move_descriptions[-3:])


# ---------------------------------------------------------------------------
# 形勢テキスト
# ---------------------------------------------------------------------------

def _evaluation_text(
    candidates: List[Dict[str, Any]],
    delta_cp: Optional[int],
) -> str:
    """候補手の評価値からテキストを生成."""
    parts = []

    if candidates:
        top = candidates[0]
        score_cp = top.get("score_cp")
        score_mate = top.get("score_mate")
        if score_mate is not None:
            if score_mate > 0:
                parts.append(f"詰み筋あり（{score_mate}手）")
            else:
                parts.append(f"相手に詰み筋（{abs(score_mate)}手）")
        elif score_cp is not None:
            abs_cp = abs(score_cp)
            if abs_cp > 2000:
                label = "先手勝勢" if score_cp > 0 else "後手勝勢"
            elif abs_cp > 800:
                label = "先手優勢" if score_cp > 0 else "後手優勢"
            elif abs_cp > 300:
                label = "先手有利" if score_cp > 0 else "後手有利"
            else:
                label = "互角"
            parts.append(f"{label}（{score_cp:+d}cp）")

    if delta_cp is not None:
        if delta_cp <= -150:
            parts.append(f"この手で評価値が大きく下がった（{delta_cp:+d}cp）→ 悪手")
        elif delta_cp <= -50:
            parts.append(f"やや疑問の残る手（{delta_cp:+d}cp）")
        elif delta_cp >= 150:
            parts.append(f"好手（{delta_cp:+d}cp）")

    return "。".join(parts) if parts else "形勢不明"


# ---------------------------------------------------------------------------
# 代替手比較
# ---------------------------------------------------------------------------

def _move_nature(move: str) -> str:
    """USI手の性質を簡易推定."""
    if not move:
        return "unknown"
    if "*" in move:
        return "drop"
    if move.endswith("+"):
        return "promotion"
    # 前進 vs 後退 (先手基準: rank数字が小さい方が前)
    try:
        src_rank = int(move[1])
        dst_rank = int(move[3])
        if dst_rank < src_rank:
            return "advance"
        if dst_rank > src_rank:
            return "retreat"
    except (IndexError, ValueError):
        pass
    return "move"


def _deep_reason_from_comparison(
    best_jp: str,
    second_jp: str,
    diff: int,
    best_move: str,
    second_move: str,
) -> str:
    """top1/top2の手の性質比較から自然な deep_reason を生成."""
    best_nature = _move_nature(best_move)
    second_nature = _move_nature(second_move)

    # 性質が異なる場合、対比文を生成
    if best_nature == "promotion" and second_nature != "promotion":
        if diff > 50:
            return f"{best_jp}と成る手が明確に優ります。成りを逃すと攻めが遅れます"
        return f"{best_jp}の成りが自然ですが、{second_jp}も有力です"

    if best_nature == "advance" and second_nature == "retreat":
        if diff > 50:
            return f"受ける手もありますが、{best_jp}と踏み込む方が速いです"
        return f"{best_jp}と攻める手と{second_jp}の受けが拮抗しています"

    if best_nature == "retreat" and second_nature == "advance":
        if diff > 50:
            return f"攻め合いの手もありますが、ここは{best_jp}と受ける方が堅実です"
        return f"{best_jp}の受けと{second_jp}の攻めが互角の選択肢です"

    if best_nature == "drop" and second_nature != "drop":
        return f"持ち駒を使う{best_jp}が効果的。盤上の駒を動かすより効率が良いです"

    if second_nature == "drop" and best_nature != "drop":
        return f"駒を打つ手もありますが、{best_jp}の方が自然な流れです"

    # 汎用: 差分ベース
    if diff > 100:
        return f"{best_jp}が明確に最善で、{second_jp}とは差があります"
    if diff > 30:
        return f"{best_jp}がやや優りますが、{second_jp}も有力な手です"
    return f"{best_jp}と{second_jp}はほぼ同等で、どちらも成立する局面です"


def _build_deep_reason(
    candidates: List[Dict[str, Any]],
    user_move: Optional[str],
    turn: str,
) -> str:
    """候補手との比較から深層理由を構築."""
    if not candidates or len(candidates) < 2:
        return ""

    best = candidates[0]
    best_move = best.get("move", "")
    best_cp = best.get("score_cp")

    # ユーザーの手が最善手と異なる場合
    if user_move and user_move != best_move and best_cp is not None:
        best_jp = ShogiUtils.format_move_label(best_move, turn)
        user_jp = ShogiUtils.format_move_label(user_move, turn)
        user_cp = None
        for c in candidates:
            if c.get("move") == user_move:
                user_cp = c.get("score_cp")
                break
        if user_cp is not None:
            diff = best_cp - user_cp
            if diff > 100:
                return f"AI推奨の{best_jp}の方が良く、{user_jp}は少し損な手です"
            elif diff > 0:
                return f"{best_jp}がわずかに優りますが、{user_jp}も十分有力です"

    # 1位と2位の比較
    second = candidates[1]
    second_move = second.get("move", "")
    second_cp = second.get("score_cp")
    if best_cp is not None and second_cp is not None:
        diff = best_cp - second_cp
        best_jp = ShogiUtils.format_move_label(best_move, turn)
        second_jp = ShogiUtils.format_move_label(second_move, turn)
        return _deep_reason_from_comparison(
            best_jp, second_jp, diff, best_move, second_move,
        )

    return ""


# ---------------------------------------------------------------------------
# 囲い情報テキスト
# ---------------------------------------------------------------------------

def _castle_text(board_analysis: BoardAnalysis) -> str:
    """囲い情報をテキスト化."""
    detail = board_analysis.king_safety_detail
    parts = []
    for side_key, side_jp in [("sente", "先手"), ("gote", "後手")]:
        info = detail.get(side_key, {})
        castle = info.get("castle_type", "不明")
        if castle not in ("不明", "その他"):
            escape = info.get("escape_squares", 0)
            defenders = info.get("adjacent_defenders", 0)
            parts.append(f"{side_jp}:{castle}（守り駒{defenders},逃げ道{escape}）")
    return "、".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# ExplanationPlanner メインクラス
# ---------------------------------------------------------------------------

class ExplanationPlanner:
    """構造化解説プランを生成するプランナー."""

    def __init__(self) -> None:
        self._board_analyzer = BoardAnalyzer()

    def build_plan(
        self,
        sfen: str,
        move: Optional[str] = None,
        ply: int = 0,
        candidates: Optional[List[Dict[str, Any]]] = None,
        delta_cp: Optional[int] = None,
        user_move: Optional[str] = None,
        prev_moves: Optional[List[str]] = None,
        prev_features: Optional[Dict[str, Any]] = None,
    ) -> ExplanationPlan:
        """局面情報から構造化解説プランを生成.

        Parameters
        ----------
        sfen : str
            position コマンド文字列
        move : str, optional
            この局面で指した手 (USI形式)
        ply : int
            手数
        candidates : list, optional
            エンジン候補手リスト
        delta_cp : int, optional
            評価値変動
        user_move : str, optional
            ユーザーが実際に指した手
        prev_moves : list, optional
            直前の手順リスト (時系列順、最大5手程度)
        prev_features : dict, optional
            前局面の特徴量 (tension_delta用)
        """
        candidates = candidates or []
        prev_moves = prev_moves or []
        target_move = user_move or move

        # 1. 特徴量抽出
        features = extract_position_features(
            sfen=sfen,
            move=target_move,
            ply=ply,
            prev_features=prev_features,
        )

        # 2. 盤面分析
        board_analysis = self._board_analyzer.analyze(
            position_cmd=sfen,
            move=target_move,
            ply=ply,
        )

        # 3. 取った駒を判定
        captured_piece = None
        if target_move and "*" not in target_move:
            pos = parse_position_cmd(sfen)
            # move適用前の盤面で移動先を確認
            from backend.api.utils.shogi_explain_core import sq_to_xy
            dst = target_move[2:4]
            dx, dy = sq_to_xy(dst)
            if 0 <= dy < 9 and 0 <= dx < 9:
                captured_piece = pos.board[dy][dx]
                if captured_piece and piece_side(captured_piece) == pos.turn:
                    captured_piece = None  # 味方駒は取れない

        # 4. 各要素の構築
        phase = features.get("phase", "midgame")
        intent = features.get("move_intent", "development")
        turn = features.get("turn", "b")

        # flow
        flow = _INTENT_TO_FLOW.get(intent, "局面を進める")
        # 前手との関連で flow を補強
        if prev_features:
            prev_intent = prev_features.get("move_intent")
            if prev_intent == "attack" and intent == "attack":
                flow = "攻めの継続（連続攻撃）"
            elif prev_intent == "attack" and intent == "defense":
                flow = "攻めを受けて守りに転換"
            elif prev_intent == "defense" and intent == "attack":
                flow = "守りから反撃に転じる"

        # topic_keyword
        topic_keyword = _extract_topic_keyword(
            target_move or "", features, board_analysis, captured_piece,
        )

        # tactical_motif
        tactical_motif = _detect_tactical_motif(board_analysis)

        # strategic_theme
        strategic_theme = _INTENT_TO_THEME.get(intent, "")
        if phase == "endgame" and intent == "attack":
            strategic_theme = "速い寄せを目指す"
        elif phase == "opening" and intent == "development":
            strategic_theme = "駒組みを進める"

        # surface_reason
        surface_reason = self._build_surface_reason(
            features, board_analysis, target_move, captured_piece, delta_cp,
        )

        # deep_reason
        deep_reason = _build_deep_reason(candidates, user_move, turn)

        # evidence
        evidence = self._collect_evidence(features, candidates, delta_cp)

        # context_summary
        context_summary = _build_context_summary(prev_moves, sfen, ply)

        # castle_info
        castle_info = _castle_text(board_analysis)

        # evaluation_summary
        evaluation_summary = _evaluation_text(candidates, delta_cp)

        # confidence
        confidence = self._estimate_confidence(features, candidates, delta_cp)

        return ExplanationPlan(
            flow=flow,
            topic_keyword=topic_keyword,
            tactical_motif=tactical_motif,
            strategic_theme=strategic_theme,
            surface_reason=surface_reason,
            deep_reason=deep_reason,
            evidence=evidence,
            confidence=confidence,
            context_summary=context_summary,
            commentary_hints=board_analysis.commentary_hints[:5],
            castle_info=castle_info,
            evaluation_summary=evaluation_summary,
        )

    def _build_surface_reason(
        self,
        features: Dict[str, Any],
        board_analysis: BoardAnalysis,
        move: Optional[str],
        captured_piece: Optional[str],
        delta_cp: Optional[int],
    ) -> str:
        """表層的な手の理由を構築."""
        parts = []
        phase_jp = _PHASE_JP.get(features.get("phase", ""), "")
        phase = features.get("phase", "midgame")
        intent = features.get("move_intent", "")
        ks = features.get("king_safety", 50)
        ap = features.get("attack_pressure", 0)
        pa = features.get("piece_activity", 50)

        impact = board_analysis.move_impact or {}

        if impact.get("is_promotion"):
            parts.append("駒を成って戦力を増強")
        if captured_piece:
            cap_jp = PIECE_JP.get(piece_kind_upper(captured_piece), "駒")
            parts.append(f"{cap_jp}を取って駒得")
        if impact.get("opened_lines"):
            parts.append("大駒の筋を通して攻めの幅を広げた")

        # 王手
        for t in board_analysis.threats:
            if t.get("type") == "check":
                parts.append("王手で相手玉に迫る")
                break

        if not parts:
            if intent == "attack":
                if phase == "endgame":
                    parts.append("寄せの速度を優先した攻め")
                elif ap >= 50:
                    parts.append("攻めの継続で圧力を維持")
                else:
                    parts.append("攻めの形を作りにいく手")
            elif intent == "defense":
                if ks <= 30:
                    parts.append("危険な玉を安全にする受け")
                elif phase == "endgame":
                    parts.append("終盤の受けで粘る")
                else:
                    parts.append("玉の安全を確保する守りの手")
            elif intent == "exchange":
                parts.append("駒交換で局面を動かす")
            elif intent == "sacrifice":
                parts.append("駒損覚悟で踏み込む勝負手")
            elif intent == "development":
                if phase == "opening":
                    if pa < 40:
                        parts.append("駒の活用を図る序盤の手")
                    else:
                        parts.append("序盤の駒組みを進める")
                elif ks < 40:
                    parts.append("玉の安全確保を優先")
                elif ap < 10:
                    parts.append("様子を見ながら態勢を整える")
                else:
                    parts.append("駒の配置を改善する手")
            else:
                # 汎用: 特徴量から推定
                if phase == "endgame" and ap >= 30:
                    parts.append("寄せに備えた一手")
                elif ks < 30:
                    parts.append("玉の安全確保を急ぐ")
                elif ap >= 40:
                    parts.append("攻めの拠点を作る手")
                elif pa < 35:
                    parts.append("駒の活用を図る")
                else:
                    parts.append(f"{phase_jp}の態勢整備")

        return "。".join(parts[:2])

    def _collect_evidence(
        self,
        features: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        delta_cp: Optional[int],
    ) -> List[str]:
        """根拠リストを収集."""
        evidence = []

        # 特徴量
        ks = features.get("king_safety", 0)
        ap = features.get("attack_pressure", 0)
        evidence.append(f"玉の安全度{ks}/100")
        evidence.append(f"攻撃圧力{ap}/100")

        # 評価値変動
        if delta_cp is not None:
            evidence.append(f"評価値変動{delta_cp:+d}cp")

        # 候補手数
        if candidates:
            top_cp = candidates[0].get("score_cp")
            if top_cp is not None:
                evidence.append(f"最善手評価{top_cp:+d}cp")

        # tension_delta
        td = features.get("tension_delta", {})
        d_ks = td.get("d_king_safety", 0)
        d_ap = td.get("d_attack_pressure", 0)
        if abs(d_ks) >= 10:
            evidence.append(f"玉の安全度が{d_ks:+.0f}変化")
        if abs(d_ap) >= 10:
            evidence.append(f"攻撃圧力が{d_ap:+.0f}変化")

        return evidence[:5]

    def _estimate_confidence(
        self,
        features: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        delta_cp: Optional[int],
    ) -> float:
        """プランの確信度を推定."""
        score = 0.5

        # 候補手がある → 情報量が多い
        if candidates:
            score += 0.1
            if len(candidates) >= 2:
                score += 0.1

        # 評価値変動がある → 手の意味が明確
        if delta_cp is not None:
            if abs(delta_cp) >= 50:
                score += 0.1

        # 特徴量が極端 → 言える事が多い
        ks = features.get("king_safety", 50)
        ap = features.get("attack_pressure", 50)
        if ks <= 20 or ks >= 80:
            score += 0.05
        if ap >= 60:
            score += 0.05

        return min(1.0, score)
