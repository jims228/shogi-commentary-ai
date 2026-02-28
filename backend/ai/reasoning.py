"""
reasoning.py

AI層の統合モジュール。
各手に対して特徴抽出→テンプレート生成→LLM改善の流れで
reasoning フィールドを構築する。
"""

import os
from typing import Dict, List, Any, Optional
from .reasoning_features import (
    extract_move_features, 
    extract_tags_from_features, 
    analyze_position_features,
    MoveFeatures,
    # v2 new functions
    detect_phase,
    classify_plan, 
    classify_move,
    analyze_pv_comparison,
    compute_confidence
)
from .reasoning_templates import (
    generate_reasoning_text,
    generate_summary_from_features,
    generate_contextual_explanation,
    add_educational_note,
    # v2 new functions
    generate_reasoning_text_v2,
    generate_contextual_explanation_v2
)
from .reasoning_llm import (
    call_llm_for_reasoning,
    enhance_multiple_explanations,
    generate_overall_summary_llm,
    # v2 new function
    call_llm_for_reasoning_v2
)


def build_reasoning(note: Dict[str, Any], 
                   context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    単一の手に対してreasoning情報を構築
    
    Args:
        note: MoveNoteの辞書表現
        context: 追加の文脈情報（前の手、全体特徴など）
        
    Returns:
        Dict: reasoning フィールドの内容
        {
            "summary": "自然な日本語の根拠文",
            "tags": ["特徴タグ", ...],
            "confidence": 0.8,  # 信頼度
            "method": "rule_based" | "llm_enhanced",
            "context": {"phase": str, "plan": str, "move_type": str},
            "pv_summary": { ... }
        }
    """
    if not note:
        return _empty_reasoning_v2()
    
    try:
        # 1. 特徴抽出
        features = extract_move_features(note)
        
        # 2. v2新機能：フェーズ・計画・手の種類を検出
        phase_info = detect_phase(note)
        plan_info = classify_plan(note)  
        move_type_info = classify_move(note)
        pv_summary = analyze_pv_comparison(note)
        
        # 3. v2信頼度計算
        confidence = compute_confidence(note)
        
        # 4. タグ生成
        tags = extract_tags_from_features(features)
        
        # 5. v2拡張文脈
        v2_context = {
            "phase": phase_info["phase"],
            "turn": phase_info["turn"],
            "plan": plan_info["plan"],
            "move_type": move_type_info["move_type"],
            "pv_summary": pv_summary,
            "tags": tags
        }
        
        # 6. v2ルールベースの説明生成
        base_reasoning = generate_reasoning_text_v2(features, note, v2_context)
        
        # 7. 文脈を考慮した改善
        previous_context = None
        if context and "previous_note" in context:
            previous_features = extract_move_features(context["previous_note"])
            prev_phase_info = detect_phase(context["previous_note"])
            prev_plan_info = classify_plan(context["previous_note"])
            previous_context = {
                "phase": prev_phase_info["phase"],
                "plan": prev_plan_info["plan"]
            }
        
        if previous_context:
            base_reasoning = generate_contextual_explanation_v2(
                features, v2_context, previous_context
            )
        
        # 8. 教育的な補足
        educational_note = add_educational_note(features)
        if educational_note:
            base_reasoning = f"{base_reasoning} {educational_note}"
        
        # 9. v2 LLMによる改善（環境変数で制御）
        enhanced_reasoning = None
        method = "rule_based"
        
        if os.getenv("USE_LLM", "0") == "1":
            enhanced_reasoning = call_llm_for_reasoning_v2(
                base_reasoning, 
                features.__dict__, 
                v2_context
            )
            if enhanced_reasoning:
                method = "llm_enhanced"
        
        # 10. 最終的なreasoning構築（v2スキーマ）
        final_summary = enhanced_reasoning if enhanced_reasoning else base_reasoning
        
        return {
            "summary": final_summary,
            "tags": tags,
            "confidence": confidence,
            "method": method,
            "context": {
                "phase": v2_context["phase"],
                "plan": v2_context["plan"], 
                "move_type": v2_context["move_type"]
            },
            "pv_summary": pv_summary
        }
        
    except Exception as e:
        print(f"Error in build_reasoning: {e}")
        return _empty_reasoning_v2()


def build_multiple_reasoning(notes: List[Dict[str, Any]], 
                           global_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    複数の手に対して一括でreasoning情報を構築（v2対応）
    
    Args:
        notes: MoveNoteのリスト
        global_context: 全体的な文脈情報
        
    Returns:
        List[Dict]: reasoning フィールドのリスト
    """
    if not notes:
        return []
    
    try:
        # 全体特徴を分析
        moves = [note.get("move", "") for note in notes]
        scores = [note.get("score_after_cp") for note in notes]
        position_features = analyze_position_features(moves, scores)
        
        reasonings = []
        
        for i, note in enumerate(notes):
            # 前の手の情報を文脈として追加
            context = global_context.copy() if global_context else {}
            if i > 0:
                context["previous_note"] = notes[i-1]
            context["position_features"] = position_features
            context["total_moves"] = len(notes)
            context["current_index"] = i
            
            reasoning = build_reasoning(note, context)
            reasonings.append(reasoning)
        
        # v2バッチ改善（重要な手のみ）
        if os.getenv("USE_LLM", "0") == "1":
            _enhance_reasonings_batch_v2(reasonings, notes, position_features)
        
        return reasonings
        
    except Exception as e:
        print(f"Error in build_multiple_reasoning: {e}")
        return [_empty_reasoning_v2() for _ in notes]


def _enhance_reasonings_batch_v2(reasonings: List[Dict[str, Any]], 
                                notes: List[Dict[str, Any]], 
                                position_features: Dict[str, Any]) -> None:
    """
    一括でreasoningを改善（v2版、重要な手を選択的に改善）
    """
    try:
        # 改善候補を選別（重要な手のみ）
        important_indices = []
        for i, note in enumerate(notes):
            delta_raw = note.get("delta_cp")
            try:
                delta = int(delta_raw) if delta_raw is not None else 0
            except Exception:
                delta = 0
            reasoning = reasonings[i] if i < len(reasonings) else {}
            move_type = reasoning.get("context", {}).get("move_type", "normal")
            
            # 重要度判定
            is_important = (
                (abs(delta) > 100) or  # 大きな評価値変化
                move_type in ["check", "capture", "sacrifice", "blunder-flag"] or  # 戦術的手
                i < 5 or  # 序盤
                i >= len(notes) - 5  # 終盤
            )
            
            if is_important:
                important_indices.append(i)
        
        # 重要な手のみをLLMで改善（最大8手まで）
        for i in important_indices[:8]:
            if i < len(reasonings) and reasonings[i]["method"] == "rule_based":
                original = reasonings[i]["summary"]
                features = extract_move_features(notes[i])
                v2_context = {
                    "phase": reasonings[i]["context"]["phase"],
                    "plan": reasonings[i]["context"]["plan"],
                    "move_type": reasonings[i]["context"]["move_type"],
                    "pv_summary": reasonings[i]["pv_summary"],
                    "tags": reasonings[i]["tags"]
                }
                
                enhanced = call_llm_for_reasoning_v2(original, features.__dict__, v2_context)
                if enhanced:
                    reasonings[i]["summary"] = enhanced
                    reasonings[i]["method"] = "llm_enhanced"
                    reasonings[i]["confidence"] = min(reasonings[i]["confidence"] + 0.1, 1.0)
                    
    except Exception as e:
        print(f"Error in batch enhancement v2: {e}")


def _empty_reasoning_v2() -> Dict[str, Any]:
    """空のreasoning情報を返す（v2スキーマ）"""
    return {
        "summary": "この手について分析できませんでした。",
        "tags": [],
        "confidence": 0.3,
        "method": "fallback",
        "context": {
            "phase": "middlegame",
            "plan": "develop", 
            "move_type": "normal"
        },
        "pv_summary": {
            "line": "",
            "why_better": []
        }
    }


# Legacy v1 function moved to the bottom

def build_multiple_reasoning_legacy(notes: List[Dict[str, Any]], 
                           global_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    複数の手に対して一括でreasoning情報を構築
    
    Args:
        notes: MoveNoteのリスト
        global_context: 全体的な文脈情報
        
    Returns:
        List[Dict]: reasoning フィールドのリスト
    """
    if not notes:
        return []
    
    try:
        # 全体特徴を分析
        moves = [note.get("move", "") for note in notes]
        scores = [note.get("score_after_cp") for note in notes]
        position_features = analyze_position_features(moves, scores)
        
        reasonings = []
        
        for i, note in enumerate(notes):
            # 前の手の情報を文脈として追加
            context = global_context.copy() if global_context else {}
            if i > 0:
                context["previous_note"] = notes[i-1]
            context["position_features"] = position_features
            context["total_moves"] = len(notes)
            context["current_index"] = i
            
            reasoning = build_reasoning(note, context)
            reasonings.append(reasoning)
        
        # LLMが有効な場合は一括改善を試行
        if os.getenv("USE_LLM", "0") == "1":
            _enhance_reasonings_batch(reasonings, notes, position_features)
        
        return reasonings
        
    except Exception as e:
        print(f"Error in build_multiple_reasoning: {e}")
        return [_empty_reasoning() for _ in notes]


def build_summary_reasoning(notes: List[Dict[str, Any]], 
                          reasonings: List[Dict[str, Any]]) -> str:
    """
    全体の要約reasoning（棋譜総括）を生成
    
    Args:
        notes: 全てのMoveNote
        reasonings: 各手のreasoning情報
        
    Returns:
        str: 棋譜全体の要約
    """
    try:
        # 基本統計を分析
        moves = [note.get("move", "") for note in notes]
        scores = [note.get("score_after_cp") for note in notes]
        position_features = analyze_position_features(moves, scores)
        
        # ルールベースの要約
        base_summary = generate_summary_from_features(notes, position_features)
        
        # LLMによる改善
        if os.getenv("USE_LLM", "0") == "1":
            llm_summary = generate_overall_summary_llm(notes, position_features)
            if llm_summary:
                return llm_summary
        
        return base_summary
        
    except Exception as e:
        print(f"Error in build_summary_reasoning: {e}")
        return "棋譜の解析中にエラーが発生しました。"


def _enhance_reasonings_batch(reasonings: List[Dict[str, Any]], 
                            notes: List[Dict[str, Any]], 
                            position_features: Dict[str, Any]) -> None:
    """
    一括でreasoningを改善（LLM利用）
    """
    try:
        # 改善候補を選別（重要な手のみ）
        important_indices = []
        for i, note in enumerate(notes):
            delta_raw = note.get("delta_cp")
            try:
                delta = int(delta_raw) if delta_raw is not None else 0
            except Exception:
                delta = 0
            if (abs(delta) > 80) or i < 5 or i >= len(notes) - 5:  # 大きな変化 or 序盤/終盤
                important_indices.append(i)
        
        # 重要な手のみをLLMで改善
        for i in important_indices[:10]:  # 最大10手まで
            if i < len(reasonings) and reasonings[i]["method"] == "rule_based":
                original = reasonings[i]["summary"]
                features = extract_move_features(notes[i])
                context = {"tags": reasonings[i]["tags"], "phase": features.position_phase}
                
                enhanced = call_llm_for_reasoning(original, features.__dict__, context)
                if enhanced:
                    reasonings[i]["summary"] = enhanced
                    reasonings[i]["method"] = "llm_enhanced"
                    reasonings[i]["confidence"] = min(reasonings[i]["confidence"] + 0.1, 1.0)
                    
    except Exception as e:
        print(f"Error in batch enhancement: {e}")


def _calculate_confidence(features: MoveFeatures, llm_enhanced: bool) -> float:
    """
    reasoning の信頼度を計算
    
    Args:
        features: 手の特徴
        llm_enhanced: LLMで改善されたかどうか
        
    Returns:
        float: 0.0〜1.0の信頼度
    """
    base_confidence = 0.6
    
    # 評価値があれば信頼度up
    if features.delta_cp is not None:
        base_confidence += 0.2
    
    # 明確な戦術特徴があれば信頼度up
    if features.is_check or features.is_capture or features.is_promotion:
        base_confidence += 0.1
    
    # エンジンの最善手と比較できれば信頼度up
    if features.bestmove:
        base_confidence += 0.05
    
    # LLMで改善されていれば信頼度up
    if llm_enhanced:
        base_confidence += 0.1
    
    return min(base_confidence, 1.0)


def _empty_reasoning() -> Dict[str, Any]:
    """空のreasoning情報を返す"""
    return {
        "summary": "この手について分析できませんでした。",
        "tags": [],
        "confidence": 0.3,
        "method": "fallback"
    }


def get_reasoning_stats(reasonings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    reasoning情報の統計を取得
    
    Args:
        reasonings: reasoning情報のリスト
        
    Returns:
        Dict: 統計情報
    """
    if not reasonings:
        return {}
    
    total = len(reasonings)
    llm_enhanced = sum(1 for r in reasonings if r.get("method") == "llm_enhanced")
    avg_confidence = sum(r.get("confidence", 0) for r in reasonings) / total
    
    # タグの頻度統計
    tag_counts = {}
    for reasoning in reasonings:
        for tag in reasoning.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    most_common_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "total_moves": total,
        "llm_enhanced_count": llm_enhanced,
        "llm_enhancement_rate": llm_enhanced / total if total > 0 else 0,
        "average_confidence": avg_confidence,
        "most_common_tags": most_common_tags,
        "method_distribution": _get_method_distribution(reasonings)
    }


def _get_method_distribution(reasonings: List[Dict[str, Any]]) -> Dict[str, int]:
    """メソッド別の分布を取得"""
    distribution = {}
    for reasoning in reasonings:
        method = reasoning.get("method", "unknown")
        distribution[method] = distribution.get(method, 0) + 1
    return distribution


# 設定用のヘルパー関数
def configure_reasoning_system(use_llm: bool = False, 
                             llm_provider: str = "gemini",
                             api_key: Optional[str] = None) -> bool:
    """
    reasoning システムの設定
    
    Args:
        use_llm: LLMを使用するかどうか
        llm_provider: "gemini" or "openai"
        api_key: APIキー（設定する場合）
        
    Returns:
        bool: 設定成功かどうか
    """
    try:
        os.environ["USE_LLM"] = "1" if use_llm else "0"
        os.environ["LLM_PROVIDER"] = llm_provider.lower()
        
        if api_key:
            if llm_provider.lower() == "gemini":
                os.environ["GEMINI_API_KEY"] = api_key
            elif llm_provider.lower() == "openai":
                os.environ["OPENAI_API_KEY"] = api_key
        
        return True
    except Exception as e:
        print(f"Configuration error: {e}")
        return False


def test_reasoning_system() -> Dict[str, Any]:
    """
    reasoning システムのテスト
    
    Returns:
        Dict: テスト結果
    """
    try:
        # テスト用の簡単なnote
        test_note = {
            "ply": 1,
            "move": "7g7f",
            "delta_cp": 10,
            "score_after_cp": 20,
            "bestmove": "7g7f",
            "tags": ["序盤"],
            "evidence": {"tactical": {"is_check": False, "is_capture": False}}
        }
        
        # reasoning生成テスト
        reasoning = build_reasoning(test_note)
        
        # 環境設定のチェック
        use_llm = os.getenv("USE_LLM", "0") == "1"
        provider = os.getenv("LLM_PROVIDER", "none")
        
        api_key_available = False
        if provider == "gemini":
            api_key_available = bool(os.getenv("GEMINI_API_KEY"))
        elif provider == "openai":
            api_key_available = bool(os.getenv("OPENAI_API_KEY"))
        
        return {
            "success": True,
            "reasoning_generated": bool(reasoning.get("summary")),
            "method": reasoning.get("method", "unknown"),
            "confidence": reasoning.get("confidence", 0),
            "tags_count": len(reasoning.get("tags", [])),
            "use_llm": use_llm,
            "llm_provider": provider,
            "api_key_configured": api_key_available,
            "test_summary": reasoning.get("summary", "")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }