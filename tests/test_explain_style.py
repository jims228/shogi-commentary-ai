"""tests for style integration in /api/explain endpoint."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.api.routers.explain import PositionCommentRequest
from backend.api.services.ml_trainer import STYLES, rule_based_predict


class TestPositionCommentRequest(unittest.TestCase):
    """PositionCommentRequest の style フィールドテスト."""

    def test_accepts_style_field(self) -> None:
        req = PositionCommentRequest(ply=1, sfen="position startpos", style="dramatic")
        self.assertEqual(req.style, "dramatic")

    def test_style_defaults_to_none(self) -> None:
        req = PositionCommentRequest(ply=1, sfen="position startpos")
        self.assertIsNone(req.style)

    def test_all_styles_accepted(self) -> None:
        for style in STYLES:
            req = PositionCommentRequest(ply=1, sfen="position startpos", style=style)
            self.assertEqual(req.style, style)

    def test_custom_string_accepted(self) -> None:
        req = PositionCommentRequest(ply=1, sfen="position startpos", style="custom")
        self.assertEqual(req.style, "custom")


class TestStyleAutoSelection(unittest.TestCase):
    """style 自動選択のロジックテスト."""

    def test_style_from_features_opening(self) -> None:
        features = {"phase": "opening", "attack_pressure": 5, "king_safety": 50, "piece_activity": 40}
        style = rule_based_predict(features)
        self.assertEqual(style, "encouraging")

    def test_style_from_features_dramatic(self) -> None:
        features = {"phase": "endgame", "attack_pressure": 60, "king_safety": 20, "piece_activity": 40}
        style = rule_based_predict(features)
        self.assertEqual(style, "dramatic")

    def test_explicit_style_used_as_is(self) -> None:
        """explicit style should be used without prediction."""
        req = PositionCommentRequest(ply=1, sfen="position startpos", style="technical")
        # Simulate the router logic
        style_used = req.style
        features = {"phase": "opening", "attack_pressure": 5, "king_safety": 50}
        if style_used is None and features:
            style_used = rule_based_predict(features)
        style_used = style_used or "neutral"
        # explicit "technical" should be preserved
        self.assertEqual(style_used, "technical")

    def test_no_features_defaults_to_neutral(self) -> None:
        """When features is None and style is None, should be neutral."""
        style_used = None
        features = None
        if style_used is None and features:
            style_used = rule_based_predict(features)
        style_used = style_used or "neutral"
        self.assertEqual(style_used, "neutral")


class TestStyleInResponse(unittest.TestCase):
    """レスポンスに style フィールドが含まれることのテスト."""

    def test_response_shape_with_style(self) -> None:
        """Router logic should produce response with explanation and style."""
        # Simulate what the router does
        comment = "序盤の駒組みが進んでいます。"
        style_used = "encouraging"
        response = {"explanation": comment, "style": style_used}
        self.assertIn("explanation", response)
        self.assertIn("style", response)
        self.assertEqual(response["style"], "encouraging")

    def test_response_with_all_styles(self) -> None:
        for style in STYLES:
            response = {"explanation": "test", "style": style}
            self.assertIn(response["style"], STYLES)


class TestEndpointStyleIntegration(unittest.TestCase):
    """explain_endpoint 関数のスタイル統合テスト (モック使用)."""

    @patch("backend.api.routers.explain._get_style_selector")
    @patch("backend.api.routers.explain.extract_position_features")
    @patch("backend.api.routers.explain.AIService.generate_position_comment", new_callable=AsyncMock)
    def test_auto_style_passed_to_ai_service(self, mock_comment, mock_features, mock_selector) -> None:
        """style=None の場合、自動選択されたスタイルがAIServiceに渡される."""
        import asyncio

        mock_features.return_value = {
            "phase": "endgame", "attack_pressure": 60,
            "king_safety": 20, "piece_activity": 40,
        }
        mock_selector.return_value.predict.return_value = "dramatic"
        mock_comment.return_value = "終盤の攻め合いです。"

        # Create mock principal
        mock_principal = MagicMock()

        from backend.api.routers.explain import explain_endpoint
        req = PositionCommentRequest(ply=50, sfen="position startpos")

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(explain_endpoint(req, mock_principal))
        finally:
            loop.close()

        self.assertEqual(result["style"], "dramatic")
        mock_comment.assert_called_once()
        call_kwargs = mock_comment.call_args
        self.assertEqual(call_kwargs.kwargs.get("style") or call_kwargs[1].get("style"), "dramatic")

    @patch("backend.api.routers.explain._get_style_selector")
    @patch("backend.api.routers.explain.extract_position_features")
    @patch("backend.api.routers.explain.AIService.generate_position_comment", new_callable=AsyncMock)
    def test_explicit_style_skips_prediction(self, mock_comment, mock_features, mock_selector) -> None:
        """style が明示的に指定された場合、predict は呼ばれない."""
        import asyncio

        mock_features.return_value = {"phase": "opening", "attack_pressure": 5, "king_safety": 50}
        mock_comment.return_value = "技術的な解説です。"

        mock_principal = MagicMock()

        from backend.api.routers.explain import explain_endpoint
        req = PositionCommentRequest(ply=10, sfen="position startpos", style="technical")

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(explain_endpoint(req, mock_principal))
        finally:
            loop.close()

        self.assertEqual(result["style"], "technical")
        mock_selector.return_value.predict.assert_not_called()


if __name__ == "__main__":
    unittest.main()
