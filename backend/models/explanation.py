"""
backend/models/explanation.py
将棋解説AI のコアデータ構造
"""
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class MoveType(str, Enum):
    attack = "attack"
    defense = "defense"
    both = "both"
    technique = "technique"


class Phase(str, Enum):
    opening = "opening"
    middle = "middle"
    endgame = "endgame"


class MoveExplanation(BaseModel):
    ply: int
    move: str
    eval_before: Optional[int] = None
    eval_after: Optional[int] = None
    eval_delta: Optional[int] = None
    best_move_loss: Optional[int] = None
    move_type: Optional[MoveType] = None
    tactical_themes: List[str] = []
    position_phase: Optional[Phase] = None
    primary_reason: Optional[str] = None
    secondary_effects: List[str] = []
    risk_factors: List[str] = []
    castle_info: Optional[str] = None
    attack_info: Optional[str] = None
    technique_info: List[str] = []
    narrative: Optional[str] = None


class GameReport(BaseModel):
    game_id: str
    moves: List[MoveExplanation] = []
    turning_points: List[int] = []
    overall_narrative: Optional[str] = None
