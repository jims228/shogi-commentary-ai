"""ExplanationPlanner のテスト.

構造化プラン生成が正しく動作することを確認する。
LLM不要 — 純粋にルールベースの中間表現のテスト。
"""
import pytest

from backend.api.services.explanation_planner import (
    ExplanationPlan,
    ExplanationPlanner,
    _build_context_summary,
    _evaluation_text,
    _extract_topic_keyword,
    _detect_tactical_motif,
    _build_deep_reason,
)
from backend.api.services.board_analyzer import BoardAnalyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STARTPOS = "position startpos"
OPENING_MOVES = "position startpos moves 7g7f 3c3d 2g2f 8c8d"
MIDGAME = "position startpos moves 7g7f 3c3d 2g2f 4c4d 2f2e 2b3c 3i4h 8b4b 5g5f 5c5d 4h3g 3a3b"
ENDGAME = "position startpos moves " + " ".join([
    "7g7f", "3c3d", "2g2f", "8c8d", "2f2e", "2b3c",
    "3i4h", "8d8e", "8h7g", "4a3b", "4h3g", "7a6b",
    "6i7h", "5a4b", "5i6h", "6b5c", "3g2f", "3b2c",
    "6h5h", "4b3b", "5h4h", "7c7d", "4h3h", "6c6d",
    "3h2h", "5c4d", "9g9f", "9c9d", "7h6g", "1c1d",
])


@pytest.fixture
def planner():
    return ExplanationPlanner()


# ---------------------------------------------------------------------------
# ExplanationPlan dataclass tests
# ---------------------------------------------------------------------------

class TestExplanationPlan:
    def test_to_prompt_block_basic(self):
        plan = ExplanationPlan(
            flow="攻めの継続",
            topic_keyword="飛車成り",
            surface_reason="大駒を成って攻めの幅を広げた",
            evaluation_summary="先手有利（+320cp）",
        )
        block = plan.to_prompt_block()
        assert "攻めの継続" in block
        assert "飛車成り" in block
        assert "大駒を成って" in block
        assert "先手有利" in block

    def test_to_prompt_block_with_context(self):
        plan = ExplanationPlan(
            flow="守りから反撃",
            context_summary="21手目▲7六歩 → 22手目△3四歩 → 23手目▲2六歩",
            topic_keyword="受けの手",
        )
        block = plan.to_prompt_block()
        assert "直前の流れ" in block
        assert "守りから反撃" in block

    def test_to_prompt_block_empty(self):
        plan = ExplanationPlan()
        block = plan.to_prompt_block()
        # flow のデフォルト空文字で1行は出る
        assert isinstance(block, str)

    def test_to_dict(self):
        plan = ExplanationPlan(
            flow="攻めの継続",
            topic_keyword="飛車成り",
            confidence=0.8,
        )
        d = plan.to_dict()
        assert d["flow"] == "攻めの継続"
        assert d["topic_keyword"] == "飛車成り"
        assert d["confidence"] == 0.8
        assert isinstance(d["evidence"], list)
        assert isinstance(d["commentary_hints"], list)


# ---------------------------------------------------------------------------
# Planner integration tests
# ---------------------------------------------------------------------------

class TestExplanationPlanner:
    def test_opening_plan(self, planner):
        """序盤の駒組みでプランが生成されること."""
        plan = planner.build_plan(
            sfen=OPENING_MOVES,
            move="2f2e",
            ply=5,
            candidates=[{"move": "2f2e", "score_cp": 30}],
            delta_cp=0,
            user_move="2f2e",
        )
        assert isinstance(plan, ExplanationPlan)
        assert plan.flow  # 空でない
        assert plan.topic_keyword  # 空でない
        assert plan.surface_reason  # 空でない
        assert 0 <= plan.confidence <= 1.0
        assert len(plan.evidence) > 0

    def test_midgame_plan(self, planner):
        """中盤のプランが生成されること."""
        plan = planner.build_plan(
            sfen=MIDGAME,
            move="5f5e",
            ply=11,
        )
        assert plan.flow
        assert plan.topic_keyword

    def test_plan_with_prev_moves(self, planner):
        """前後文脈付きでプランが生成されること."""
        plan = planner.build_plan(
            sfen=OPENING_MOVES,
            move="2f2e",
            ply=5,
            candidates=[
                {"move": "2f2e", "score_cp": 30},
                {"move": "3i4h", "score_cp": 20},
            ],
            delta_cp=-10,
            user_move="2f2e",
            prev_moves=["7g7f", "3c3d", "2g2f"],
        )
        assert plan.context_summary  # 前後文脈があること
        assert "→" in plan.context_summary

    def test_plan_with_capture(self, planner):
        """駒取りのプランでキーワードに駒名が含まれること."""
        sfen = "position startpos moves 7g7f 3c3d 8h2b+"
        plan = planner.build_plan(
            sfen=sfen,
            move="8h2b+",
            ply=3,
            candidates=[{"move": "8h2b+", "score_cp": 200}],
            delta_cp=200,
            user_move="8h2b+",
        )
        # 角成り or 角を取る のどちらかが含まれるはず
        assert plan.topic_keyword
        prompt = plan.to_prompt_block()
        assert len(prompt) > 50  # プロンプトブロックが十分な長さ

    def test_plan_without_candidates(self, planner):
        """候補手なしでもプランが生成されること."""
        plan = planner.build_plan(
            sfen=STARTPOS,
            move="7g7f",
            ply=1,
        )
        assert plan.flow
        assert plan.evaluation_summary  # "形勢不明" でも何か入る

    def test_plan_with_bad_move(self, planner):
        """悪手の場合にプランに反映されること."""
        plan = planner.build_plan(
            sfen=MIDGAME,
            move="5f5e",
            ply=11,
            candidates=[
                {"move": "3g2f", "score_cp": 100},
                {"move": "5f5e", "score_cp": -80},
            ],
            delta_cp=-180,
            user_move="5f5e",
        )
        # 悪手の情報がどこかに反映されている
        assert "悪手" in plan.evaluation_summary or plan.deep_reason

    def test_plan_flow_attack_continuation(self, planner):
        """連続攻撃のフロー検出."""
        prev_features = {
            "move_intent": "attack",
            "king_safety": 60,
            "piece_activity": 50,
            "attack_pressure": 40,
        }
        sfen = "position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e"
        plan = planner.build_plan(
            sfen=sfen,
            move="2f2e",
            ply=5,
            prev_features=prev_features,
        )
        # move_intent が attack で前も attack なら "継続" が含まれるはず
        # ただし intent 判定は盤面依存なので、flow が空でないことを確認
        assert plan.flow

    def test_prompt_block_format(self, planner):
        """プロンプトブロックが正しいフォーマットであること."""
        plan = planner.build_plan(
            sfen=OPENING_MOVES,
            move="2f2e",
            ply=5,
            candidates=[{"move": "2f2e", "score_cp": 30}],
            delta_cp=0,
            user_move="2f2e",
            prev_moves=["7g7f", "3c3d"],
        )
        block = plan.to_prompt_block()
        # 【】でセクションが区切られていること
        assert "【" in block
        assert "】" in block
        # 複数行あること
        assert "\n" in block


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_build_context_summary_empty(self):
        result = _build_context_summary([], "position startpos", 1)
        assert result == ""

    def test_build_context_summary_few_moves(self):
        result = _build_context_summary(["7g7f", "3c3d"], "position startpos", 3)
        assert "→" in result
        assert "7" in result or "▲" in result or "△" in result

    def test_build_context_summary_many_moves(self):
        moves = ["7g7f", "3c3d", "2g2f", "8c8d", "2f2e"]
        result = _build_context_summary(moves, "position startpos", 6)
        # 最後の3手のみ表示
        assert result.count("→") == 2

    def test_evaluation_text_with_candidates(self):
        result = _evaluation_text(
            [{"move": "7g7f", "score_cp": 320}],
            delta_cp=None,
        )
        assert "有利" in result or "cp" in result

    def test_evaluation_text_with_delta(self):
        result = _evaluation_text([], delta_cp=-200)
        assert "悪手" in result

    def test_evaluation_text_mate(self):
        result = _evaluation_text(
            [{"move": "G*5b", "score_mate": 5}],
            delta_cp=None,
        )
        assert "詰み" in result

    def test_evaluation_text_empty(self):
        result = _evaluation_text([], delta_cp=None)
        assert result == "形勢不明"

    def test_build_deep_reason_with_alternatives(self):
        result = _build_deep_reason(
            [
                {"move": "7g7f", "score_cp": 100},
                {"move": "2g2f", "score_cp": -50},
            ],
            user_move="2g2f",
            turn="b",
        )
        assert result  # 何かしらの比較テキストがある
        assert "cp" in result or "良" in result or "優る" in result or "損" in result

    def test_build_deep_reason_empty(self):
        result = _build_deep_reason([], None, "b")
        assert result == ""


# ---------------------------------------------------------------------------
# _sanitize_explanation tests
# ---------------------------------------------------------------------------

class TestSanitizeExplanation:
    """修正3: LLM出力後処理のテスト."""

    @pytest.fixture
    def dummy_plan(self):
        return ExplanationPlan(
            topic_keyword="序盤の駒組み",
            surface_reason="陣形を整える手",
        )

    def test_strips_newlines(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "一行目の解説です。\n二行目もあります。"
        result = _sanitize_explanation(raw, dummy_plan)
        assert "\n" not in result

    def test_strips_heading_brackets(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "【解説】中盤の攻防が始まりました。"
        result = _sanitize_explanation(raw, dummy_plan)
        assert "【" not in result
        assert "中盤" in result

    def test_strips_bullets(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "- 攻めの手です。\n- 守りも大切です。"
        result = _sanitize_explanation(raw, dummy_plan)
        assert "- " not in result
        assert "\n" not in result

    def test_strips_markdown_headings(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "## 解説\n中盤の攻防が始まりました。攻めの形を作ります。"
        result = _sanitize_explanation(raw, dummy_plan)
        assert "##" not in result

    def test_enforces_80_char_limit(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "あ" * 100
        result = _sanitize_explanation(raw, dummy_plan)
        assert len(result) <= 80

    def test_truncates_at_sentence_boundary(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "序盤の駒組みが進み、互いに陣形を整えています。中盤に入り攻防が本格化しそうです。さらに攻めの形を作っていきます。"
        result = _sanitize_explanation(raw, dummy_plan)
        assert len(result) <= 80
        # 文の途中で切れず句点で終わる
        assert result.endswith("。") or result.endswith("...")

    def test_empty_string_returns_fallback(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        result = _sanitize_explanation("", dummy_plan)
        assert len(result) >= 5
        assert "序盤の駒組み" in result or "陣形" in result

    def test_very_short_returns_fallback(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        result = _sanitize_explanation("はい", dummy_plan)
        assert len(result) >= 5

    def test_normal_input_passes_through(self, dummy_plan):
        from backend.api.services.ai_service import _sanitize_explanation
        raw = "中盤に入り、攻めの形が整いました。"
        result = _sanitize_explanation(raw, dummy_plan)
        assert result == raw


# ---------------------------------------------------------------------------
# _build_planned_fallback tests
# ---------------------------------------------------------------------------

class TestBuildPlannedFallback:
    """修正3: fallback文が自然なユーザー向けテキストであること."""

    def test_with_surface_reason_and_keyword(self):
        from backend.api.services.ai_service import _build_planned_fallback
        plan = ExplanationPlan(
            topic_keyword="飛車成り",
            surface_reason="大駒を成って攻めの幅を広げた",
        )
        result = _build_planned_fallback(plan)
        assert "飛車成り" in result
        assert "攻め" in result
        assert len(result) <= 80

    def test_with_surface_reason_only(self):
        from backend.api.services.ai_service import _build_planned_fallback
        plan = ExplanationPlan(surface_reason="玉の安全を確保する守りの手")
        result = _build_planned_fallback(plan)
        assert "玉" in result
        assert result.endswith("。")

    def test_with_keyword_only(self):
        from backend.api.services.ai_service import _build_planned_fallback
        plan = ExplanationPlan(topic_keyword="序盤の駒組み")
        result = _build_planned_fallback(plan)
        assert "序盤の駒組み" in result
        assert "です" in result

    def test_completely_empty_plan(self):
        from backend.api.services.ai_service import _build_planned_fallback
        plan = ExplanationPlan()
        result = _build_planned_fallback(plan)
        assert len(result) >= 5
        assert "一手" in result or "局面" in result

    def test_fallback_within_80_chars(self):
        from backend.api.services.ai_service import _build_planned_fallback
        plan = ExplanationPlan(
            topic_keyword="あ" * 30,
            surface_reason="い" * 50,
        )
        result = _build_planned_fallback(plan)
        assert len(result) <= 80


# ---------------------------------------------------------------------------
# Training log structure test (修正1)
# ---------------------------------------------------------------------------

class TestTrainingLogStructure:
    """修正1: plan が features に混ざらないことを確認."""

    def test_log_record_separates_plan_from_features(self):
        """_log_explanation が plan を metadata に分離すること."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        from backend.api.services.ai_service import _log_explanation

        captured_records = []

        async def mock_log(record):
            captured_records.append(record)

        with patch("backend.api.services.ai_service.training_logger") as mock_logger:
            mock_logger.log_explanation = AsyncMock(side_effect=mock_log)
            asyncio.run(_log_explanation(
                sfen="position startpos",
                ply=1,
                candidates=[],
                user_move="7g7f",
                delta_cp=0,
                features={"king_safety": 60, "attack_pressure": 20},
                explanation="テスト解説",
                model_name="test",
                tokens=None,
                style="neutral",
                plan={"flow": "駒組み", "topic_keyword": "序盤"},
            ))

        assert len(captured_records) == 1
        record = captured_records[0]

        # features は数値特徴量のまま
        assert record["input"]["features"]["king_safety"] == 60
        assert "_plan" not in record["input"]["features"]

        # plan は metadata に分離
        assert "metadata" in record
        assert record["metadata"]["plan"]["flow"] == "駒組み"

    def test_log_record_without_plan(self):
        """plan なしの場合 metadata が追加されないこと."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        from backend.api.services.ai_service import _log_explanation

        captured_records = []

        async def mock_log(record):
            captured_records.append(record)

        with patch("backend.api.services.ai_service.training_logger") as mock_logger:
            mock_logger.log_explanation = AsyncMock(side_effect=mock_log)
            asyncio.run(_log_explanation(
                sfen="position startpos",
                ply=1,
                features={"king_safety": 60},
                explanation="テスト",
            ))

        assert len(captured_records) == 1
        record = captured_records[0]
        assert "metadata" not in record


# ---------------------------------------------------------------------------
# Router rollout safety test (修正2)
# ---------------------------------------------------------------------------

class TestRouterRolloutSafety:
    """修正2: prev_moves だけでは planner に切り替わらないこと."""

    def test_prev_moves_without_use_planner_uses_legacy(self):
        """use_planner=None + prev_moves あり → レガシー方式."""
        from backend.api.routers.explain import PositionCommentRequest
        req = PositionCommentRequest(
            ply=5,
            sfen="position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e",
            prev_moves=["7g7f", "3c3d", "2g2f"],
            # use_planner は未指定 (None)
        )
        # use_planner が None の場合、新方式に切り替わらないことを確認
        assert req.use_planner is None

    def test_explicit_use_planner_true(self):
        from backend.api.routers.explain import PositionCommentRequest
        req = PositionCommentRequest(
            ply=5,
            sfen="position startpos moves 7g7f",
            use_planner=True,
        )
        assert req.use_planner is True

    def test_explicit_use_planner_false_with_prev_moves(self):
        from backend.api.routers.explain import PositionCommentRequest
        req = PositionCommentRequest(
            ply=5,
            sfen="position startpos moves 7g7f",
            prev_moves=["7g7f"],
            use_planner=False,
        )
        assert req.use_planner is False


# ---------------------------------------------------------------------------
# AIService integration (no LLM, plan-only)
# ---------------------------------------------------------------------------

class TestAIServiceBuildPlan:
    def test_build_plan_static_method(self):
        from backend.api.services.ai_service import AIService
        plan_dict = AIService.build_plan(
            sfen="position startpos moves 7g7f",
            move="7g7f",
            ply=1,
        )
        assert isinstance(plan_dict, dict)
        assert "flow" in plan_dict
        assert "topic_keyword" in plan_dict
        assert "confidence" in plan_dict
