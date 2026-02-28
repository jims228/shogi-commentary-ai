"""
reasoning_llm.py

GeminiやChatGPTを使って自然な言い換えを生成するモジュール。
環境変数でON/OFFとプロバイダーを切り替え可能。
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List
import time


def _env_flag(name: str) -> bool:
    return os.getenv(name, "0") == "1"


def call_llm_for_reasoning(base_reasoning: str, 
                          features: Dict[str, Any], 
                          context: Dict[str, Any]) -> Optional[str]:
    """
    LLMを呼び出して自然な言い換えを生成
    
    Args:
        base_reasoning: ルールベースで生成された基本文
        features: 手の特徴情報
        context: 追加の文脈情報
        
    Returns:
        Optional[str]: LLMで改善された文章、またはNone（失敗時）
    """
    # v1入口はv2へ委譲（呼び出し経路の重複を防ぐ）
    return call_llm_for_reasoning_v2(base_reasoning, features, context)


def _gemini_models_to_try() -> List[str]:
    """環境変数からGeminiモデルを取得し、既知モデルのフォールバック順で返す"""
    primary = os.getenv("GEMINI_MODEL", "").strip()
    # デフォルト候補には 2.5 を先頭に含める
    defaults = ["gemini-2.5-flash", "gemini-2.0-flash"]
    candidates = [m for m in [primary] + defaults if m]
    # 重複排除（順序維持）
    seen = set()
    ordered = []
    for m in candidates:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def _call_gemini(base_reasoning: str, features: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
    """
    Google Gemini APIを呼び出し
    
    Args:
        base_reasoning: 基本の根拠文
        features: 特徴データ
        context: 文脈情報
        
    Returns:
        Optional[str]: 改善された文章
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    sdk_only = _env_flag("GEMINI_SDK_ONLY")
    http_only = _env_flag("GEMINI_HTTP_ONLY")
    disable_fallback = _env_flag("GEMINI_DISABLE_FALLBACK")
    forced_api_ver = (os.getenv("GEMINI_API_VERSION") or "").strip()
    
    try:
        prompt = _build_gemini_prompt(base_reasoning, features, context)

        # まずは公式SDKで試行（利用可能ならエンドポイント差分を吸収できる）
        if not http_only:
            try:
                import google.generativeai as genai
                from backend.api.utils.gemini_client import ensure_configured, get_model_name
                if not ensure_configured():
                    return None
                model_name = get_model_name()
                print(f"Gemini SDK calling model: {model_name}")
                generation_config = {
                    "temperature": 0.3,
                    "top_k": 20,
                    "top_p": 0.8,
                    "max_output_tokens": 200,
                }
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(prompt, generation_config=generation_config)
                text = getattr(resp, "text", None)
                if text:
                    return _clean_llm_output(text)
            except Exception as sdk_e:
                if sdk_only or disable_fallback:
                    print(f"Gemini SDK path failed: {sdk_e}")
                    return None
                print(f"Gemini SDK path failed, fallback to HTTP: {sdk_e}")

        if sdk_only:
            return None

        if disable_fallback:
            # フォールバック多重呼び出し抑制: SDK失敗時もHTTPへ行かない
            return None

        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "topK": 20,
                "topP": 0.8,
                "maxOutputTokens": 200,
                "stopSequences": []
            }
        }

        api_versions = [forced_api_ver] if forced_api_ver else (["v1"] if disable_fallback else ["v1beta", "v1"])
        models = _gemini_models_to_try()
        if disable_fallback and models:
            models = [models[0]]

        last_error: Optional[Exception] = None
        for model in models:
            try:
                last_http_error: Optional[Exception] = None
                result: Optional[Dict[str, Any]] = None
                for api_ver in api_versions:
                    url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={api_key}"
                    print(f"Gemini calling model: {model} via {api_ver}")
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=10) as response:
                            result = json.loads(response.read().decode("utf-8"))
                        last_http_error = None
                        break
                    except urllib.error.HTTPError as he_inner:
                        last_http_error = he_inner
                        if he_inner.code == 404:
                            print(f"Gemini HTTP 404 via {api_ver} for {model}, trying other version...")
                            continue
                        else:
                            raise
                if result and "candidates" in result and result["candidates"]:
                    content = result["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and "text" in parts[0]:
                        generated_text = parts[0]["text"].strip()
                        return _clean_llm_output(generated_text)
                # 期待する構造でない場合は次候補へ
                last_error = RuntimeError("Gemini response missing candidates")
            except urllib.error.HTTPError as he:
                last_error = he
                if he.code == 404:
                    # モデル未対応など → 次候補を試す
                    print(f"Gemini model not found (404): {model}, trying fallback...")
                    continue
                else:
                    print(f"Gemini HTTP error {he.code}: {he}")
                    break
            except Exception as e:
                last_error = e
                print(f"Gemini API error with model {model}: {e}")
                break

        if last_error:
            print(f"Gemini API failed after fallbacks: {last_error}")
        return None

    except Exception as e:
        print(f"Gemini API outer error: {e}")
        return None


def _call_openai(base_reasoning: str, features: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
    """
    OpenAI GPT APIを呼び出し
    
    Args:
        base_reasoning: 基本の根拠文
        features: 特徴データ
        context: 文脈情報
        
    Returns:
        Optional[str]: 改善された文章
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        prompt = _build_openai_prompt(base_reasoning, features, context)
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "あなたは将棋の解説者です。将棋の手について、分かりやすく自然な日本語で説明してください。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 150,
            "temperature": 0.3,
            "top_p": 0.8
        }
        
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
        
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            if "content" in message:
                generated_text = message["content"].strip()
                return _clean_llm_output(generated_text)
        
        return None
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def _build_gemini_prompt(base_reasoning: str, features: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Gemini用のプロンプトを構築（v2拡張版）"""
    move = features.get("move", "")
    ply = features.get("ply", 0)
    delta_cp = features.get("delta_cp")
    
    # v2の文脈情報
    phase = context.get("phase", "middlegame")
    plan = context.get("plan", "develop")
    move_type = context.get("move_type", "normal")
    pv_summary = context.get("pv_summary", {})
    
    phase_map = {"opening": "序盤", "middlegame": "中盤", "endgame": "終盤"}
    plan_map = {
        "develop": "駒組み", "attack": "攻撃", "defend": "守備", 
        "trade": "駒交換", "castle": "囲い", "promotion": "成り", 
        "endgame-technique": "終盤技術"
    }
    
    prompt = f"""将棋の{ply}手目「{move}」について説明を改善してください。

現在の説明: {base_reasoning}

局面情報:
- フェーズ: {phase_map.get(phase, phase)} ({phase})
- 計画: {plan_map.get(plan, plan)} ({plan})  
- 手の種類: {move_type}
- 評価値変化: {delta_cp if delta_cp is not None else '不明'}cp

PV分析: {pv_summary.get('line', '不明')}
改善点: {', '.join(pv_summary.get('why_better', [])) if pv_summary.get('why_better') else '特になし'}

以下の指針で2〜3文の自然な日本語に改善してください：
1. 評価値の推移、王手/駒得/受けなど具体的な根拠を示す
2. 初心者にも理解できる表現を使う  
3. 現在のフェーズ（{phase_map.get(phase, phase)}）と計画（{plan_map.get(plan, plan)}）を考慮する
4. 機械的でない人間らしい解説にする
5. 憶測や根拠のない分析は避ける

改善された説明のみを出力してください："""

    return prompt


def _build_openai_prompt(base_reasoning: str, features: Dict[str, Any], context: Dict[str, Any]) -> str:
    """OpenAI用のプロンプトを構築（v2拡張版）"""
    move = features.get("move", "")
    ply = features.get("ply", 0)
    delta_cp = features.get("delta_cp")
    
    # v2の文脈情報
    phase = context.get("phase", "middlegame")
    plan = context.get("plan", "develop")
    move_type = context.get("move_type", "normal")
    pv_summary = context.get("pv_summary", {})
    
    prompt = f"""将棋の指し手について説明を改善してください。

【手】{ply}手目: {move}
【評価値変化】{delta_cp if delta_cp is not None else '不明'}cp
【フェーズ】{phase}
【計画】{plan}
【手の種類】{move_type}
【現在の説明】{base_reasoning}
【PV分析】{pv_summary.get('line', '情報なし')}
【改善点】{', '.join(pv_summary.get('why_better', ['特になし']))}

この説明を以下の条件で改善してください：
- 2〜3文の自然な日本語
- フェーズ（{phase}）と計画（{plan}）を考慮
- 評価値、戦術的要素を具体的に言及
- 初心者にも分かりやすく
- 憶測ではなく与えられた情報に基づく分析

改善された説明のみを回答してください："""

    return prompt


def _validate_llm_output(text: str, context: Dict[str, Any]) -> bool:
    """
    LLM出力の妥当性を検証（安全性チェック）
    
    Args:
        text: LLMの出力テキスト
        context: 入力コンテキスト
        
    Returns:
        bool: 出力が妥当かどうか
    """
    import re

    if not text or len(text.strip()) < 10:
        return False
    
    # 長すぎる出力を拒否
    if len(text) > 300:
        return False
    
    # 不適切なキーワードをチェック
    inappropriate_keywords = [
        "わかりません", "申し訳ありません", "確信できません",
        "推測", "憶測", "おそらく", "たぶん", "かもしれません"
    ]
    
    text_lower = text.lower()
    for keyword in inappropriate_keywords:
        if keyword in text_lower:
            return False

    # 戦術的な手種では、最低限「将棋っぽさ」がない出力（英語のみ等）を拒否
    if context.get("move_type") in ["check", "capture", "promote"]:
        shogi_terms = ["王手", "駒", "成り", "攻", "守", "評価", "局面"]
        has_shogi_terms = any(term in text for term in shogi_terms)
        has_japanese = bool(re.search(r"[ぁ-んァ-ン一-龥]", text))
        if not has_shogi_terms and not has_japanese:
            return False
    
    return True


def _clean_llm_output(text: str) -> str:
    """LLMの出力をクリーンアップ（v2安全性向上）"""
    # 不要な改行や空白を除去
    text = text.replace('\n', ' ').replace('\r', '')
    text = ' '.join(text.split())
    
    # 不要な接頭辞を除去
    prefixes_to_remove = [
        "改善された説明：", "説明：", "回答：", "解説：",
        "改善案：", "改良版：", "修正版：", "＞", "】",
        "将棋の", "この手は", "手目："
    ]
    
    for prefix in prefixes_to_remove:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    
    # 不要な句読点の調整
    text = text.strip('。').strip()
    
    # 連続する句読点を整理
    import re
    text = re.sub(r'[。]{2,}', '。', text)
    text = re.sub(r'[、]{2,}', '、', text)
    
    # 最大長制限（安全性）
    if len(text) > 200:
        # 文の境界で切断
        sentences = text.split('。')
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence + "。") <= 200:
                truncated += sentence + "。"
            else:
                break
        text = truncated.rstrip('。')
    
    return text


def call_llm_for_reasoning_v2(base_reasoning: str, 
                              features: Dict[str, Any], 
                              context: Dict[str, Any]) -> Optional[str]:
    """
    LLMを呼び出して自然な言い換えを生成（v2版）
    
    Args:
        base_reasoning: ルールベースで生成された基本文
        features: 手の特徴情報
        context: v2拡張文脈情報（phase, plan, move_type, pv_summaryなど）
        
    Returns:
        Optional[str]: LLMで改善された文章、またはNone（失敗時）
    """
    # 環境変数チェック（上位許可 + 用途別トグル）
    use_llm = os.getenv("USE_LLM", "0") == "1"
    # 後方互換: USE_LLM_REASONING 未設定なら「有効」扱い
    use_reasoning_raw = os.getenv("USE_LLM_REASONING")
    use_reasoning = True if use_reasoning_raw is None else (use_reasoning_raw == "1")
    if not use_llm or not use_reasoning:
        return None
    
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    try:
        if provider == "gemini":
            result = _call_gemini(base_reasoning, features, context)
        elif provider == "openai":
            result = _call_openai(base_reasoning, features, context)
        else:
            return None
        
        # 安全性検証
        if result and _validate_llm_output(result, context):
            return result
        else:
            print(f"LLM output validation failed: {result}")
            return None
            
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None


def enhance_multiple_explanations(explanations: List[str], 
                                context: Dict[str, Any]) -> List[str]:
    """
    複数の説明を一括でLLMで改善
    
    Args:
        explanations: 基本説明のリスト
        context: 全体的な文脈情報
        
    Returns:
        List[str]: 改善された説明のリスト
    """
    # 環境変数チェック（上位許可 + 用途別トグル）
    use_llm = os.getenv("USE_LLM", "0") == "1"
    use_reasoning_raw = os.getenv("USE_LLM_REASONING")
    use_reasoning = True if use_reasoning_raw is None else (use_reasoning_raw == "1")
    if not use_llm or not use_reasoning:
        return explanations
    
    enhanced = []
    
    for i, explanation in enumerate(explanations):
        # レート制限を避けるため少し待機
        if i > 0:
            time.sleep(0.5)
        
        features = {"ply": i + 1, "move": f"手{i+1}"}
        enhanced_text = call_llm_for_reasoning(explanation, features, context)
        
        if enhanced_text:
            enhanced.append(enhanced_text)
        else:
            enhanced.append(explanation)  # フォールバック
    
    return enhanced


def generate_overall_summary_llm(notes: List[Dict[str, Any]], 
                                features: Dict[str, Any]) -> Optional[str]:
    """
    LLMで棋譜全体の総括を生成
    
    Args:
        notes: 全ての手のノート
        features: 全体特徴
        
    Returns:
        Optional[str]: 生成された総括、またはNone
    """
    use_llm = os.getenv("USE_LLM", "0") == "1"
    use_reasoning_raw = os.getenv("USE_LLM_REASONING")
    use_reasoning = True if use_reasoning_raw is None else (use_reasoning_raw == "1")
    if not use_llm or not use_reasoning:
        return None
    
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    # 要約用プロンプトを構築
    moves_count = features.get("total_moves", 0)
    balance = features.get("game_balance", "balanced")
    lead_changes = features.get("lead_changes", 0)
    
    # 代表的な手を抜粋
    def _dcp(n):
        v = n.get("delta_cp")
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0
    significant_moves = [note for note in notes if abs(_dcp(note)) > 80][:5]
    moves_summary = ", ".join([f"{note.get('ply', 0)}手目{note.get('move', '')}" 
                              for note in significant_moves])
    
    base_summary = f"{moves_count}手の将棋。バランス: {balance}、形勢変化: {lead_changes}回、注目手: {moves_summary}"
    
    summary_prompt = f"""この将棋の対局を総括してください。

基本情報: {base_summary}

以下の観点で、2〜3文で自然な日本語の総括を作成してください：
1. 全体的な対局の特徴
2. 印象的だった場面
3. 両者の指し回しの評価

総括のみを回答してください："""
    
    if provider == "gemini":
        return _call_gemini_simple(summary_prompt)
    elif provider == "openai":
        return _call_openai_simple(summary_prompt)
    
    return None


def _call_gemini_simple(prompt: str) -> Optional[str]:
    """シンプルなGemini呼び出し"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    sdk_only = _env_flag("GEMINI_SDK_ONLY")
    http_only = _env_flag("GEMINI_HTTP_ONLY")
    disable_fallback = _env_flag("GEMINI_DISABLE_FALLBACK")
    forced_api_ver = (os.getenv("GEMINI_API_VERSION") or "").strip()
    
    try:
        # SDK優先
        if not http_only:
            try:
                import google.generativeai as genai
                from backend.api.utils.gemini_client import ensure_configured, get_model_name
                if not ensure_configured():
                    return None
                model_name = get_model_name()
                print(f"Gemini SDK (summary) calling model: {model_name}")
                generation_config = {"temperature": 0.4, "max_output_tokens": 150}
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(prompt, generation_config=generation_config)
                text = getattr(resp, "text", None)
                if text:
                    return _clean_llm_output(text)
            except Exception as sdk_e:
                if sdk_only or disable_fallback:
                    print(f"Gemini SDK (summary) failed: {sdk_e}")
                    return None
                print(f"Gemini SDK (summary) failed, fallback to HTTP: {sdk_e}")

        if sdk_only:
            return None

        if disable_fallback:
            return None

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 150}
        }

        api_versions = [forced_api_ver] if forced_api_ver else (["v1"] if disable_fallback else ["v1beta", "v1"])
        models = _gemini_models_to_try()
        if disable_fallback and models:
            models = [models[0]]

        last_error: Optional[Exception] = None
        for model in models:
            try:
                last_http_error: Optional[Exception] = None
                result: Optional[Dict[str, Any]] = None
                for api_ver in api_versions:
                    url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={api_key}"
                    print(f"Gemini (summary) calling model: {model} via {api_ver}")
                    req = urllib.request.Request(
                        url,
                        json.dumps(payload).encode(),
                        {"Content-Type": "application/json"}
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=10) as response:
                            result = json.loads(response.read().decode())
                        last_http_error = None
                        break
                    except urllib.error.HTTPError as he_inner:
                        last_http_error = he_inner
                        if he_inner.code == 404:
                            print(f"Gemini (summary) 404 via {api_ver} for {model}, trying other version...")
                            continue
                        else:
                            raise
                if result and "candidates" in result and result["candidates"]:
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    return _clean_llm_output(text)
                last_error = RuntimeError("Gemini summary missing candidates")
            except urllib.error.HTTPError as he:
                last_error = he
                if he.code == 404:
                    print(f"Gemini (summary) model 404: {model}, trying fallback...")
                    continue
                else:
                    print(f"Gemini (summary) HTTP error {he.code}: {he}")
                    break
            except Exception as e:
                last_error = e
                print(f"Gemini (summary) error with model {model}: {e}")
                break

        if last_error:
            print(f"Gemini (summary) failed after fallbacks: {last_error}")
    except Exception as e:
        print(f"Gemini (summary) outer error: {e}")

    return None


def _call_openai_simple(prompt: str) -> Optional[str]:
    """シンプルなOpenAI呼び出し"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "将棋の対局を分析する解説者として回答してください。"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 120,
            "temperature": 0.4
        }
        
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            json.dumps(payload).encode(),
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
        
        if "choices" in result and result["choices"]:
            text = result["choices"][0]["message"]["content"]
            return _clean_llm_output(text)
            
    except Exception as e:
        print(f"OpenAI summary error: {e}")
    
    return None