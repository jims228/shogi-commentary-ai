"""Tests for AI prompt construction with position features."""
from __future__ import annotations

import pytest

from backend.api.services.ai_service import (
    build_features_block,
    build_digest_features_block,
    _describe_safety,
    _describe_pressure,
)


class TestDescribeSafety:
    def test_high(self):
        assert "堅い" in _describe_safety(85)

    def test_moderate(self):
        assert "ある程度" in _describe_safety(60)

    def test_low(self):
        assert "不安定" in _describe_safety(35)

    def test_critical(self):
        assert "危険" in _describe_safety(10)

    def test_boundary_80(self):
        assert "堅い" in _describe_safety(80)

    def test_boundary_55(self):
        assert "ある程度" in _describe_safety(55)

    def test_boundary_30(self):
        assert "不安定" in _describe_safety(30)


class TestDescribePressure:
    def test_high(self):
        assert "強い" in _describe_pressure(75)

    def test_moderate(self):
        assert "できつつある" in _describe_pressure(45)

    def test_low(self):
        assert "様子見" in _describe_pressure(20)

    def test_none(self):
        assert "なし" in _describe_pressure(5)


class TestBuildFeaturesBlock:
    def test_with_full_features(self):
        """全特徴量が揃っている場合、プロンプトに反映される."""
        features = {
            "king_safety": 75,
            "piece_activity": 50,
            "attack_pressure": 40,
            "phase": "midgame",
            "move_intent": "attack",
            "after": {
                "king_safety": 60,
                "piece_activity": 45,
                "attack_pressure": 55,
            },
        }
        block = build_features_block(features)
        assert "中盤" in block
        assert "75/100" in block
        assert "攻め" in block
        assert "相手側" in block
        assert "この手の意図" in block

    def test_without_after(self):
        """after がない場合でも正常に構築される."""
        features = {
            "king_safety": 85,
            "piece_activity": 30,
            "attack_pressure": 10,
            "phase": "opening",
            "move_intent": "development",
        }
        block = build_features_block(features)
        assert "序盤" in block
        assert "85/100" in block
        assert "相手側" not in block
        assert "駒組み" in block

    def test_without_intent(self):
        """move_intent が None の場合は意図行が出ない."""
        features = {
            "king_safety": 50,
            "piece_activity": 50,
            "attack_pressure": 50,
            "phase": "endgame",
            "move_intent": None,
        }
        block = build_features_block(features)
        assert "終盤" in block
        assert "この手の意図" not in block

    def test_empty_features(self):
        """最小限の特徴量でもクラッシュしない."""
        block = build_features_block({})
        assert "局面の状況" in block

    def test_defense_intent(self):
        features = {
            "king_safety": 30,
            "attack_pressure": 10,
            "phase": "midgame",
            "move_intent": "defense",
        }
        block = build_features_block(features)
        assert "守り" in block

    def test_sacrifice_intent(self):
        features = {
            "king_safety": 50,
            "attack_pressure": 60,
            "phase": "midgame",
            "move_intent": "sacrifice",
        }
        block = build_features_block(features)
        assert "犠牲" in block


class TestBuildDigestFeaturesBlock:
    def test_empty_list(self):
        """空リストは空文字列を返す."""
        assert build_digest_features_block([]) == ""

    def test_single_feature(self):
        """1件でもクラッシュしない."""
        features = [
            {"king_safety": 70, "piece_activity": 40, "attack_pressure": 20, "phase": "opening"},
        ]
        block = build_digest_features_block(features)
        assert "局面特徴量サマリー" in block

    def test_phase_transitions(self):
        """フェーズ推移が表示される."""
        features = [
            {"king_safety": 70, "attack_pressure": 10, "phase": "opening"},
            {"king_safety": 65, "attack_pressure": 20, "phase": "opening"},
            {"king_safety": 50, "attack_pressure": 40, "phase": "midgame"},
            {"king_safety": 40, "attack_pressure": 60, "phase": "midgame"},
            {"king_safety": 30, "attack_pressure": 80, "phase": "endgame"},
            {"king_safety": 20, "attack_pressure": 90, "phase": "endgame"},
        ]
        block = build_digest_features_block(features)
        assert "序盤" in block
        assert "中盤" in block
        assert "終盤" in block

    def test_pressure_jump(self):
        """攻守の切り替わりが検出される."""
        features = [
            {"king_safety": 70, "attack_pressure": 10, "phase": "opening"},
            {"king_safety": 70, "attack_pressure": 10, "phase": "opening"},
            {"king_safety": 50, "attack_pressure": 50, "phase": "midgame"},  # +40 jump
            {"king_safety": 40, "attack_pressure": 60, "phase": "midgame"},
        ]
        block = build_digest_features_block(features)
        assert "切り替わり" in block

    def test_no_jump_when_stable(self):
        """圧力変化が小さければ切り替わりは表示されない."""
        features = [
            {"king_safety": 70, "attack_pressure": 30, "phase": "opening"},
            {"king_safety": 68, "attack_pressure": 32, "phase": "opening"},
            {"king_safety": 65, "attack_pressure": 35, "phase": "midgame"},
        ]
        block = build_digest_features_block(features)
        assert "切り替わり" not in block

    def test_segment_averages(self):
        """序盤/中盤/終盤の平均値が出る."""
        features = [
            {"king_safety": 80, "attack_pressure": 10, "phase": "opening"},
            {"king_safety": 80, "attack_pressure": 10, "phase": "opening"},
            {"king_safety": 50, "attack_pressure": 40, "phase": "midgame"},
            {"king_safety": 50, "attack_pressure": 40, "phase": "midgame"},
            {"king_safety": 20, "attack_pressure": 80, "phase": "endgame"},
            {"king_safety": 20, "attack_pressure": 80, "phase": "endgame"},
        ]
        block = build_digest_features_block(features)
        # 序盤の平均 king_safety = 80
        assert "80/100" in block
        # 終盤の平均 attack_pressure = 80
        assert "強い攻撃態勢" in block
