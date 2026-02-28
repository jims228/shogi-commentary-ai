"""
backend/api/routers/games.py
/api/games エンドポイント - 棋譜の保存・取得
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(tags=["games"])


class GameCreateRequest(BaseModel):
    title: Optional[str] = None
    kifu_text: str
    kifu_format: str  # "kif" | "csa" | "usi"


class GameResponse(BaseModel):
    id: str
    title: Optional[str] = None
    kifu_format: str
    move_count: Optional[int] = None


@router.post("/games", response_model=GameResponse)
async def create_game(body: GameCreateRequest):
    """
    棋譜を保存する。
    TODO: Supabase 連携の実装
    """
    raise NotImplementedError("not implemented")


@router.get("/games", response_model=List[GameResponse])
async def list_games():
    """
    棋譜一覧を返す。
    TODO: Supabase 連携の実装
    """
    return []
