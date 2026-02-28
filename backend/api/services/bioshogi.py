"""
bioshogi_service (Ruby/Sinatra) への HTTP クライアント
"""
from __future__ import annotations
import os
import httpx
from typing import Optional
from pydantic import BaseModel

BIOSHOGI_URL = os.getenv("BIOSHOGI_URL", "http://localhost:7070")


class BioshogiPlayer(BaseModel):
    player: int
    attack: list[str] = []
    defense: list[str] = []
    technique: list[str] = []
    note: list[str] = []


class BioshogiResult(BaseModel):
    ok: bool
    players: list[BioshogiPlayer] = []
    error: Optional[str] = None


def analyze_kifu(kifu: str) -> BioshogiResult:
    """棋譜文字列をbioshogiに送って戦型・囲い・手筋を取得"""
    try:
        resp = httpx.post(
            f"{BIOSHOGI_URL}/analyze",
            json={"kifu": kifu},
            timeout=10.0,
        )
        resp.raise_for_status()
        return BioshogiResult(**resp.json())
    except Exception as e:
        return BioshogiResult(ok=False, error=str(e))


def is_available() -> bool:
    """bioshogiサービスが起動しているか確認"""
    try:
        resp = httpx.get(f"{BIOSHOGI_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False