"""
reasoning_features.py

エンジン出力から将棋の特徴を抽出するモジュール。
評価値の変化、戦術的要素、盤面情報を分析して構造化データを生成します。
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MoveFeatures:
    """一手の特徴を表すデータクラス"""
    # 基本情報
    ply: int
    move: str
    
    # 評価値関連
    delta_cp: Optional[int] = None
    score_before: Optional[int] = None
    score_after: Optional[int] = None
    is_mate_threat: bool = False
    mate_in: Optional[int] = None
    
    # 戦術的特徴
    is_check: bool = False
    is_capture: bool = False
    is_promotion: bool = False
    is_drop: bool = False
    is_castle: bool = False
    
    # 戦略的特徴
    is_attack: bool = False
    is_defense: bool = False
    opens_line: bool = False
    develops_piece: bool = False
    centralizes: bool = False
    
    # 駒の種類
    piece_moved: Optional[str] = None
    piece_captured: Optional[str] = None
    
    # エンジン推奨との比較
    is_best_move: bool = False
    bestmove: Optional[str] = None
    
    # 局面評価
    position_phase: str = "middle"  # opening, middle, endgame
    king_safety_score: Optional[int] = None


def extract_move_features(note: Dict[str, Any]) -> MoveFeatures:
    """
    MoveNote（辞書形式）から特徴を抽出
    
    Args:
        note: APIの MoveNote オブジェクトの辞書表現
        
    Returns:
        MoveFeatures: 抽出された特徴
    """
    features = MoveFeatures(
        ply=note.get("ply", 0),
        move=note.get("move", ""),
        delta_cp=note.get("delta_cp"),
        score_before=note.get("score_before_cp"),
        score_after=note.get("score_after_cp"),
        bestmove=note.get("bestmove"),
    )
    
    # 基本的な戦術特徴を抽出
    _extract_tactical_features(features, note)
    
    # 評価値から戦略的判断
    _extract_strategic_features(features, note)
    
    # 局面フェーズの判定
    _determine_game_phase(features, note)
    
    return features


def _extract_tactical_features(features: MoveFeatures, note: Dict[str, Any]) -> None:
    """戦術的特徴の抽出"""
    move = features.move
    pv = note.get("pv", "")
    
    # 王手の検出
    if "+" in move or (pv and "+" in pv):
        features.is_check = True
    
    # 駒取りの検出（USI形式での判定は限定的）
    evidence = note.get("evidence", {})
    tactical = evidence.get("tactical", {})
    features.is_capture = tactical.get("is_capture", False)
    
    # 成りの検出
    if "+" in move:
        features.is_promotion = True
    
    # 打ち駒の検出（USI形式: 例 P*5e）
    if "*" in move:
        features.is_drop = True
        # 打った駒の種類を取得
        piece_char = move[0].upper()
        features.piece_moved = _usi_piece_to_japanese(piece_char)
    
    # 移動した駒の推定（USI形式から）
    if not features.is_drop:
        features.piece_moved = _extract_piece_from_move(move)
    
    # エンジンの最善手との比較
    if features.bestmove:
        features.is_best_move = (move == features.bestmove)


def _extract_strategic_features(features: MoveFeatures, note: Dict[str, Any]) -> None:
    """戦略的特徴の抽出"""
    delta = features.delta_cp
    move = features.move
    
    # 評価値変化による攻守判定
    if delta is not None:
        if delta > 50:
            features.is_attack = True
        elif delta < -30:
            features.is_defense = True
    
    # 駒の展開判定（序盤での特定の駒の動き）
    if features.ply <= 20:
        piece = features.piece_moved
        if piece in ["銀", "桂", "角", "飛"]:
            features.develops_piece = True
    
    # 中央への利き
    if move and len(move) >= 4:
        dest_file = _extract_destination_file(move)
        if dest_file in [4, 5, 6]:  # 4〜6筋は中央
            features.centralizes = True
    
    # 角道や飛車筋を開ける
    if features.piece_moved == "歩" and features.ply <= 10:
        features.opens_line = True


def _determine_game_phase(features: MoveFeatures, note: Dict[str, Any]) -> None:
    """局面のフェーズ判定"""
    ply = features.ply
    
    if ply <= 24:
        features.position_phase = "opening"
    elif ply >= 80:
        features.position_phase = "endgame"
    else:
        features.position_phase = "middle"


def _usi_piece_to_japanese(usi_char: str) -> str:
    """USI駒文字を日本語に変換"""
    mapping = {
        "P": "歩", "L": "香", "N": "桂", "S": "銀", 
        "G": "金", "B": "角", "R": "飛", "K": "玉"
    }
    return mapping.get(usi_char.upper(), "駒")


def _extract_piece_from_move(move: str) -> str:
    """USI移動から駒の種類を推定（簡易版）"""
    # 実際の実装では盤面状態が必要だが、ここでは一般的なパターンで推定
    if len(move) >= 4:
        # 7g7f のような歩の動きパターン
        from_pos = move[:2]
        to_pos = move[2:4]
        
        # ファイルが同じで1つだけ進んだ場合は歩の可能性が高い
        if from_pos[0] == to_pos[0]:
            try:
                # USI形式では段はa-iなので、英字から数値に変換
                from_rank_char = from_pos[1]
                to_rank_char = to_pos[1]
                from_rank = ord(from_rank_char) - ord('a') + 1
                to_rank = ord(to_rank_char) - ord('a') + 1
                if abs(from_rank - to_rank) == 1:
                    return "歩"
            except (ValueError, IndexError):
                pass
    
    return "駒"  # 不明な場合


def _extract_destination_file(move: str) -> int:
    """移動先の筋を取得"""
    if len(move) >= 4:
        try:
            # USI形式: 7g7f の場合、移動先は7f
            dest_file_char = move[2]
            if dest_file_char.isdigit():
                return int(dest_file_char)
        except (ValueError, IndexError):
            pass
    return 5  # デフォルトは中央


def analyze_position_features(moves: List[str], scores: List[Optional[int]]) -> Dict[str, Any]:
    """
    全体的な局面特徴の分析
    
    Args:
        moves: 全ての指し手リスト
        scores: 各局面の評価値リスト
        
    Returns:
        Dict: 全体特徴の分析結果
    """
    features = {
        "total_moves": len(moves),
        "score_swings": 0,
        "lead_changes": 0,
        "avg_score": None,
        "max_advantage": None,
        "critical_moments": [],
        "game_balance": "balanced",
    }
    
    # 数値スコアのみ抽出
    numeric_scores = [s for s in scores if s is not None]
    
    if numeric_scores:
        features["avg_score"] = sum(numeric_scores) // len(numeric_scores)
        features["max_advantage"] = max(abs(s) for s in numeric_scores)
        
        # ゲームバランスの判定
        max_abs = max(abs(s) for s in numeric_scores)
        if max_abs > 500:
            features["game_balance"] = "decisive"
        elif max_abs > 200:
            features["game_balance"] = "advantage"
    
    # 評価値の大きな変動を検出
    for i in range(1, len(numeric_scores)):
        diff = abs(numeric_scores[i] - numeric_scores[i-1])
        if diff > 120:
            features["score_swings"] += 1
    
    # リードチェンジの検出
    for i in range(1, len(numeric_scores)):
        prev_sign = 1 if numeric_scores[i-1] > 0 else -1 if numeric_scores[i-1] < 0 else 0
        curr_sign = 1 if numeric_scores[i] > 0 else -1 if numeric_scores[i] < 0 else 0
        if prev_sign != 0 and curr_sign != 0 and prev_sign != curr_sign:
            features["lead_changes"] += 1
    
    return features


def classify_move_strength(delta_cp: Optional[int]) -> str:
    """評価値変化から手の強さを分類"""
    if delta_cp is None:
        return "不明"
    
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


def detect_phase(note: Dict[str, Any]) -> Dict[str, str]:
    """
    局面のフェーズと手番を検出
    
    Args:
        note: MoveNote辞書
        
    Returns:
        Dict: {"phase": "opening|middlegame|endgame", "turn": "sente|gote"}
    """
    ply = int(note.get("ply") or 0)
    mate = note.get("mate")
    score_cp = note.get("score_after_cp")
    if score_cp is None:
        score_cp = note.get("score_cp")

    if isinstance(mate, int) and mate != 0:
        phase = "endgame"
    elif isinstance(score_cp, (int, float)) and abs(score_cp) >= 1500:
        phase = "endgame"
    elif ply >= 60:
        phase = "endgame"
    elif ply >= 24:
        phase = "middlegame"
    else:
        phase = "opening"

    # 手番: ply 1=先手、2=後手…（奇数=先手、偶数=後手）
    if ply <= 0:
        turn = "sente"
    else:
        turn = "sente" if (ply % 2 == 1) else "gote"
    return {"phase": phase, "turn": turn}


def classify_plan(note: Dict[str, Any]) -> Dict[str, str]:
    """
    手の戦略的計画を分類
    
    Args:
        note: MoveNote辞書
        
    Returns:
        Dict: {"plan": "develop|attack|defend|trade|castle|promotion|endgame-technique"}
    """
    delta = note.get("delta_cp")
    mate = note.get("mate")
    tactical = (note.get("evidence") or {}).get("tactical") or {}

    if isinstance(mate, int) and mate != 0:
        return {"plan": "endgame-technique"}

    if isinstance(delta, (int, float)) and delta < 0:
        return {"plan": "defend"}

    if tactical.get("is_check") and isinstance(delta, (int, float)) and delta > 0:
        return {"plan": "attack"}

    phase = detect_phase(note)["phase"]
    return {"plan": "develop" if phase == "opening" else "develop"}


def classify_move(note: Dict[str, Any]) -> Dict[str, str]:
    """
    手のタイプを分類
    
    Args:
        note: MoveNote辞書
        
    Returns:
        Dict: {"move_type": "normal|check|capture|promote|sacrifice|quiet-improve|blunder-flag"}
    """
    move = (note.get("move") or "")
    delta = note.get("delta_cp")
    tags = note.get("tags") or []
    tactical = (note.get("evidence") or {}).get("tactical") or {}

    if "悪手" in tags or (isinstance(delta, (int, float)) and delta <= -200):
        return {"move_type": "blunder-flag"}

    # 「王手」を成りより優先
    if tactical.get("is_check") or "王手" in tags:
        return {"move_type": "check"}

    if tactical.get("is_capture"):
        return {"move_type": "capture"}

    if "+" in move:
        return {"move_type": "promote"}

    return {"move_type": "normal"}


def analyze_pv_comparison(note: Dict[str, Any]) -> Dict[str, Any]:
    """
    PVと最善手の比較分析
    
    Args:
        note: MoveNote辞書
        
    Returns:
        Dict: PV比較の要約
    """
    move = note.get("move")
    best = note.get("bestmove")
    pv = (note.get("pv") or "").strip()
    line = pv.split() if pv else []

    if move and best and move == best:
        why_better = ["最善手"]
    else:
        why_better = []
        if best:
            why_better.append(f"最善手は{best}")
        if line:
            why_better.append("PVを参考に改善")

    return {"line": line, "why_better": why_better}


def compute_confidence(note: Dict[str, Any]) -> float:
    """
    推論の信頼度を計算
    
    Args:
        note: MoveNote辞書
        
    Returns:
        float: 0-1の信頼度
    """
    import math
    import os
    
    # depth情報
    evidence = note.get("evidence", {})
    depth = evidence.get("depth", 6)
    
    # 評価値の安定性
    delta_cp = note.get("delta_cp", 0)
    abs_delta = abs(delta_cp) if delta_cp is not None else 0
    
    # sigmoid関数
    def sigmoid(x):
        return 1 / (1 + math.exp(-x))
    
    # 基本信頼度（探索深度ベース）
    base = sigmoid((depth - 6) / 4)
    
    # 安定性（評価値変化の明確さ）
    stability = sigmoid(abs_delta / 200)
    
    # LLMボーナス
    llm_bonus = 0.1 if os.getenv("USE_LLM", "0") == "1" else 0
    
    # 最終計算
    confidence = 0.5 * base + 0.4 * stability + llm_bonus
    
    # 0-1にクランプ
    return max(0.0, min(1.0, confidence))


def _is_king_move(move: str) -> bool:
    """玉の移動かどうか判定（簡易版）"""
    # USI形式では盤面状態が必要だが、ここでは5筋周辺の動きで推定
    if len(move) >= 4:
        from_file = move[0]
        to_file = move[2]
        # 5筋周辺の動き（4,5,6筋）
        return from_file in "456" and to_file in "456"
    return False


def extract_tags_from_features(features: MoveFeatures) -> List[str]:
    """特徴からタグを生成"""
    tags = []
    
    # 評価値ベース
    if features.delta_cp is not None:
        strength = classify_move_strength(features.delta_cp)
        if strength != "通常手":
            tags.append(strength)
    
    # 戦術的特徴
    if features.is_check:
        tags.append("王手")
    if features.is_capture:
        tags.append("駒取り")
    if features.is_promotion:
        tags.append("成り")
    if features.is_drop:
        tags.append("打ち駒")
    if features.is_castle:
        tags.append("囲い")
    
    # 戦略的特徴
    if features.is_attack:
        tags.append("攻め")
    if features.is_defense:
        tags.append("守り")
    if features.opens_line:
        tags.append("筋を開ける")
    if features.develops_piece:
        tags.append("駒組み")
    if features.centralizes:
        tags.append("中央制圧")
    
    # エンジンとの比較
    if not features.is_best_move and features.bestmove:
        tags.append("次善手")
    
    # 局面フェーズ
    if features.position_phase == "opening":
        tags.append("序盤")
    elif features.position_phase == "endgame":
        tags.append("終盤")
    
    return tags


def detect_opening_style(ply: int, moves_so_far: List[str], board=None) -> Dict[str, Any]:
    """序盤の戦型（居飛車/振り飛車/相振り飛車）を推定する。

    - board がある場合は盤面スキャン（0..80）で飛車の筋を取得し判定する。
    - board が無い / python-shogi が無い場合は、USIの from-square に基づく簡易フォールバック。
    - 後方互換のため、既存フィールドは削除せず、detected を常に返す。
    """

    result: Dict[str, Any] = {
        "style": "unknown",
        "subtype": None,
        "confidence": 0.0,
        "side": "unknown",
        "reasons": [],
        "features": {},
    }

    # 30手以降は序盤判定の信頼度を下げる（序盤戦型としては不安定）
    if ply > 30:
        result["confidence"] = max(0.2, (40 - ply) / 20)  # 40手で0
        result["reasons"].append("中盤以降は序盤判定の信頼度が低い")
        result["detected"] = result["style"] != "unknown" and result["confidence"] >= 0.6
        return result

    try:
        import shogi  # type: ignore
    except Exception:
        shogi = None

    rook_files = {
        "sente": None,  # 先手（黒）基準 1-9
        "gote": None,   # 後手（白）基準 1-9
    }

    # ===== board ベース（推奨） =====
    if shogi is not None and board is not None:
        try:
            rook_piece_types = {7, 14}  # ROOK=7 / PROM_ROOK=14（python-shogi の piece_type）
            for sq in range(81):
                piece = board.piece_at(sq)
                if piece is None:
                    continue
                ptype = getattr(piece, "piece_type", None)
                if ptype not in rook_piece_types:
                    continue

                square_name = shogi.SQUARE_NAMES[sq]
                file_num = int(square_name[0])  # 例: "2h" -> 2

                color = getattr(piece, "color", None)
                if color == 0:  # BLACK
                    rook_files["sente"] = file_num
                elif color == 1:  # WHITE
                    rook_files["gote"] = 10 - file_num  # 黒基準へ正規化

            result["features"] = {
                "sente_rook_file": rook_files["sente"],
                "gote_rook_file": rook_files["gote"],
                "move_count": len(moves_so_far),
            }
        except Exception as e:
            # 盤面スキャン失敗時はフォールバックへ
            result["reasons"].append(f"盤面スキャンエラー: {e}")

    # ===== フォールバック（board/shogi なし） =====
    if not result["features"]:
        features: Dict[str, Any] = {"move_count": len(moves_so_far)}

        # 先手飛車: 初期 2h からの移動
        for mv in moves_so_far:
            if isinstance(mv, str) and len(mv) >= 4 and mv[:2] == "2h" and mv[2].isdigit():
                rook_files["sente"] = int(mv[2])
                features["sente_rook_file"] = rook_files["sente"]

        # 後手飛車: 初期 8b からの移動（黒基準へ正規化）
        for mv in moves_so_far:
            if isinstance(mv, str) and len(mv) >= 4 and mv[:2] == "8b" and mv[2].isdigit():
                gote_file = int(mv[2])
                rook_files["gote"] = 10 - gote_file
                features["gote_rook_file"] = rook_files["gote"]

        result["features"] = features

    # ===== 判定ロジック =====
    # 角換わり（両者の角交換が成立）を最優先で検出
    # 条件: 盤上に角系(角/馬)が0枚 かつ 両者の持ち駒に角が1枚以上
    if shogi is not None and board is not None:
        try:
            bishop_types = {getattr(shogi, "BISHOP", 6), getattr(shogi, "PROM_BISHOP", 13)}
            bishops_on_board = 0
            for sq in range(81):
                piece = board.piece_at(sq)
                if piece is None:
                    continue
                if getattr(piece, "piece_type", None) in bishop_types:
                    bishops_on_board += 1

            # pieces_in_hand は Counter
            b_color = getattr(shogi, "BLACK", 0)
            w_color = getattr(shogi, "WHITE", 1)
            bishop_pt = getattr(shogi, "BISHOP", 6)
            b_hand = 0
            w_hand = 0
            try:
                b_hand = board.pieces_in_hand[b_color][bishop_pt]
                w_hand = board.pieces_in_hand[w_color][bishop_pt]
            except Exception:
                # 念のためのガード（構造が異なる場合）
                b_hand = 0
                w_hand = 0

            if bishops_on_board == 0 and b_hand >= 1 and w_hand >= 1:
                result["style"] = "居飛車"
                result["subtype"] = "角換わり"
                result["side"] = "both"
                # 仕様: confidence >= 0.8
                result["confidence"] = max(0.8, 0.85)
                result["reasons"].append("盤上に角が無く、双方の持ち駒に角があるため角換わり")
                result["features"].update({
                    "bishops_on_board": bishops_on_board,
                    "black_bishop_in_hand": b_hand,
                    "white_bishop_in_hand": w_hand,
                })
                # detected を計算して即返す
                result["detected"] = result["style"] != "unknown" and result["confidence"] >= 0.6
                return result
        except Exception as e:
            result["reasons"].append(f"角換わり判定エラー: {e}")

    # 以降は飛車の位置による基本的な戦型判定
    ranged_set = {5, 6, 7, 8}
    sente_norm = rook_files["sente"]
    gote_norm = rook_files["gote"]
    sente_ranged = sente_norm in ranged_set
    gote_ranged = gote_norm in ranged_set

    subtype_map = {
        5: "中飛車",
        6: "四間飛車",
        7: "三間飛車",
        8: "向かい飛車",
    }

    def opening_confidence(p: int, base: float) -> float:
        # 目安: 序盤(<=10)は 0.8〜0.9、進むほど少し下げる
        if p <= 10:
            return min(0.9, max(0.8, base))
        # 11手目以降は 1手ごとに 0.01 下げ、下限 0.65
        return max(0.65, base - 0.01 * (p - 10))

    if sente_ranged and gote_ranged:
        result["style"] = "相振り飛車"
        result["side"] = "both"
        result["confidence"] = opening_confidence(ply, 0.88)
        result["reasons"].append(f"先手飛車{sente_norm}筋、後手飛車{gote_norm}筋")
    elif sente_ranged and not gote_ranged:
        result["style"] = "振り飛車"
        result["side"] = "black"
        result["subtype"] = subtype_map.get(sente_norm)
        result["confidence"] = opening_confidence(ply, 0.86)
        result["reasons"].append(f"先手振り飛車（{sente_norm}筋）")
    elif gote_ranged and not sente_ranged:
        result["style"] = "振り飛車"
        result["side"] = "white"
        result["subtype"] = subtype_map.get(gote_norm)
        result["confidence"] = opening_confidence(ply, 0.86)
        result["reasons"].append(f"後手振り飛車（{gote_norm}筋）")
    else:
        # 両方振りでない & ply>=8 → 居飛車として検出
        if ply >= 8:
            result["style"] = "居飛車"
            result["side"] = "both"
            result["confidence"] = max(0.65, opening_confidence(ply, 0.85))
            result["reasons"].append("序盤8手以上で飛車が振り飛車筋に動いていない")
        else:
            result["confidence"] = 0.4
            result["reasons"].append("手数が少なく戦型が確定しない")

    # detected を計算（全 return パスで必ず付与）
    result["detected"] = result["style"] != "unknown" and result["confidence"] >= 0.6
    return result