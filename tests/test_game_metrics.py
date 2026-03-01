"""tests/test_game_metrics.py"""
from __future__ import annotations

import pytest

from backend.api.services.game_metrics import (
    calculate_skill_score,
    calculate_tension_timeline,
)


# ============================================================
# calculate_skill_score
# ============================================================


class TestCalculateSkillScore:
    def test_empty_notes(self):
        result = calculate_skill_score(None, 50)
        assert result["score"] == 0
        assert result["grade"] == "D"
        assert result["details"]["evaluated"] == 0

    def test_zero_total_moves(self):
        result = calculate_skill_score([{"ply": 1, "move": "7g7f", "delta_cp": 0}], 0)
        assert result["score"] == 0

    def test_all_best_moves(self):
        """全て最善手一致 → スコア100, グレードS"""
        notes = [{"ply": i, "move": f"m{i}", "delta_cp": 0} for i in range(1, 51)]
        result = calculate_skill_score(notes, 50)
        assert result["score"] == 100
        assert result["grade"] == "S"
        assert result["details"]["best"] == 50
        assert result["details"]["blunder"] == 0

    def test_all_blunders(self):
        """全て悪手 → スコア0, グレードD"""
        notes = [{"ply": i, "move": f"m{i}", "delta_cp": -200} for i in range(1, 51)]
        result = calculate_skill_score(notes, 50)
        assert result["score"] == 0
        assert result["grade"] == "D"
        assert result["details"]["blunder"] == 50

    def test_mixed_moves(self):
        """混合: 30手最善 + 10手次善 + 10手悪手 (total 50手)"""
        notes = (
            [{"ply": i, "move": f"m{i}", "delta_cp": -5} for i in range(1, 31)]       # best: 30 * 3 = 90
            + [{"ply": i, "move": f"m{i}", "delta_cp": -30} for i in range(31, 41)]   # second: 10 * 1 = 10
            + [{"ply": i, "move": f"m{i}", "delta_cp": -200} for i in range(41, 51)]  # blunder: 10 * -2 = -20
        )
        # raw_sum = 90 + 10 - 20 = 80, score = (80/50) * (100/3) = 53.3 → 53
        result = calculate_skill_score(notes, 50)
        assert result["score"] == 53
        assert result["grade"] == "C"
        assert result["details"]["best"] == 30
        assert result["details"]["second"] == 10
        assert result["details"]["blunder"] == 10

    def test_score_clamped_to_100(self):
        """スコア上限が100を超えない"""
        # delta_cp が正 (好手) でも最大は _POINTS_BEST
        notes = [{"ply": i, "move": f"m{i}", "delta_cp": 300} for i in range(1, 11)]
        result = calculate_skill_score(notes, 10)
        assert result["score"] == 100

    def test_notes_with_null_delta(self):
        """delta_cp が None の手は無視される"""
        notes = [
            {"ply": 1, "move": "m1", "delta_cp": 0},
            {"ply": 2, "move": "m2", "delta_cp": None},
            {"ply": 3, "move": "m3", "delta_cp": -5},
        ]
        result = calculate_skill_score(notes, 10)
        assert result["details"]["evaluated"] == 2
        assert result["details"]["best"] == 2

    def test_grade_boundaries(self):
        """グレード境界値"""
        # S: 90+
        notes_s = [{"ply": i, "move": f"m{i}", "delta_cp": 0} for i in range(1, 10)]
        r = calculate_skill_score(notes_s, 9)
        assert r["grade"] == "S"

        # A: 75-89 → score 78 程度を作る
        # 7 best (21) + 2 neutral (0) = 21, total 9, score=(21/9)*(100/3)=77.8→78
        notes_a = (
            [{"ply": i, "move": f"m{i}", "delta_cp": 0} for i in range(1, 8)]
            + [{"ply": i, "move": f"m{i}", "delta_cp": -80} for i in range(8, 10)]
        )
        r = calculate_skill_score(notes_a, 9)
        assert r["grade"] == "A"


# ============================================================
# calculate_tension_timeline
# ============================================================


class TestCalculateTensionTimeline:
    def test_empty_history(self):
        result = calculate_tension_timeline(None)
        assert result["timeline"] == []
        assert result["avg"] == 0.0
        assert result["label"] == "穏やかな展開"

    def test_single_value(self):
        result = calculate_tension_timeline([100])
        assert result["timeline"] == []

    def test_flat_eval(self):
        """評価値が一定 → テンション0"""
        result = calculate_tension_timeline([0, 0, 0, 0, 0])
        assert all(t == 0.0 for t in result["timeline"])
        assert result["avg"] == 0.0
        assert result["label"] == "穏やかな展開"

    def test_high_tension(self):
        """大きな変動 → 高テンション"""
        # 各手 ±500 の変動
        history = [0, 500, 0, 500, 0, 500]
        result = calculate_tension_timeline(history)
        assert result["avg"] > 0.6
        assert result["label"] == "激戦"

    def test_moderate_tension(self):
        """中程度の変動"""
        # 各手 ±100 の変動
        history = [0, 100, 0, 100, 0, 100, 0]
        result = calculate_tension_timeline(history)
        assert 0.3 <= result["avg"] <= 0.6
        assert result["label"] == "攻防あり"

    def test_timeline_length(self):
        """timeline の長さ = len(eval_history) - 1"""
        history = list(range(10))
        result = calculate_tension_timeline(history)
        assert len(result["timeline"]) == 9

    def test_tension_clamped(self):
        """テンション値は 0-1 にクランプ"""
        history = [0, 10000, 0]  # |delta| = 10000, 10000
        result = calculate_tension_timeline(history)
        assert all(0.0 <= t <= 1.0 for t in result["timeline"])

    def test_moving_average_smoothing(self):
        """移動平均により急激な変動が平滑化される"""
        # 1手だけ大きな変動、他は0
        history = [0, 0, 0, 1000, 0, 0, 0]
        result = calculate_tension_timeline(history)
        # index 2 (delta=1000) のtensionは高いが、周辺は平滑化で低め
        timeline = result["timeline"]
        assert timeline[2] > timeline[0]  # 変動があった箇所は高い
        # 最初の手 (index 0) は変動なし → tension=0
        assert timeline[0] == 0.0

    def test_rounding(self):
        """小数第3位まで丸められる"""
        history = [0, 33, 66, 99]
        result = calculate_tension_timeline(history)
        for t in result["timeline"]:
            # 小数第3位まで
            assert t == round(t, 3)
        assert result["avg"] == round(result["avg"], 3)
