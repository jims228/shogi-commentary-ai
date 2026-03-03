"""ML パイプライン向けエンジン解析サービス.

engine_state.py を変更せずに、同期コンテキスト（スクリプト等）から
やねうら王エンジンの解析結果を取得できるようにラップする。

Usage (standalone)::

    svc = EngineAnalysisService()
    svc.start()
    result = svc.analyze_position("position startpos moves 7g7f")
    svc.stop()

Usage (context manager)::

    with EngineAnalysisService() as svc:
        result = svc.analyze_position("position startpos")
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional

# .env を手動ロード（dotenv に依存しない）
_ENV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".env"
)
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

ENGINE_CMD = os.getenv("ENGINE_CMD", "/usr/local/bin/yaneuraou")
ENGINE_WORK_DIR = os.getenv("ENGINE_WORK_DIR", os.path.dirname(ENGINE_CMD) or "/usr/local/bin")
EVAL_DIR = os.getenv("ENGINE_EVAL_DIR", "")
SCORE_SCALE = 0.7


class AnalysisResult:
    """1 局面の解析結果."""

    __slots__ = ("ok", "bestmove", "score_cp", "score_mate", "pv", "multipv", "raw_infos")

    def __init__(
        self,
        ok: bool = False,
        bestmove: str = "",
        score_cp: Optional[int] = None,
        score_mate: Optional[int] = None,
        pv: str = "",
        multipv: Optional[List[Dict[str, Any]]] = None,
        raw_infos: Optional[List[str]] = None,
    ):
        self.ok = ok
        self.bestmove = bestmove
        self.score_cp = score_cp
        self.score_mate = score_mate
        self.pv = pv
        self.multipv = multipv or []
        self.raw_infos = raw_infos or []

    def to_eval_info(self) -> Dict[str, Any]:
        """position_features.extract_position_features の eval_info に渡せる辞書."""
        return {
            "score_cp": self.score_cp,
            "score_mate": self.score_mate,
            "bestmove": self.bestmove,
            "pv": self.pv,
        }

    def __repr__(self) -> str:
        return (
            f"AnalysisResult(ok={self.ok}, bestmove={self.bestmove!r}, "
            f"score_cp={self.score_cp}, score_mate={self.score_mate}, "
            f"pv={self.pv!r})"
        )


def _parse_info_line(line: str) -> Optional[Dict[str, Any]]:
    """USI info 行をパースする (engine_state.parse_usi_info と同等ロジック)."""
    if "score" not in line or "pv" not in line:
        return None
    try:
        data: Dict[str, Any] = {"multipv": 1}
        mp = re.search(r"multipv\s+(\d+)", line)
        if mp:
            data["multipv"] = int(mp.group(1))
        sc = re.search(
            r"score\s+(cp|mate)\s+(?:lowerbound\s+|upperbound\s+)?([\+\-]?\d+)", line
        )
        if sc:
            kind = sc.group(1)
            val = int(sc.group(2))
            if kind == "cp":
                val = int(val * SCORE_SCALE)
            data["score"] = {"type": kind, ("cp" if kind == "cp" else "mate"): val}
        else:
            return None
        pv = re.search(r" pv\s+(.*)", line)
        if pv:
            data["pv"] = pv.group(1).strip()
        return data
    except Exception:
        return None


class EngineAnalysisService:
    """同期コンテキストから USI エンジンを使って局面解析する.

    内部で専用の asyncio イベントループをバックグラウンドスレッドで動かし、
    そこでエンジンプロセスを管理する。
    """

    def __init__(
        self,
        engine_cmd: Optional[str] = None,
        eval_dir: Optional[str] = None,
        nodes: int = 150000,
        multipv: int = 1,
        timeout: float = 15.0,
    ):
        self._engine_cmd = engine_cmd or ENGINE_CMD
        self._eval_dir = eval_dir or EVAL_DIR
        self._nodes = nodes
        self._multipv = multipv
        self._timeout = timeout

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._alive = False

    # ------ lifecycle ------

    def start(self) -> None:
        """エンジンを起動する."""
        if self._alive:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # エンジン起動を待つ
        fut = asyncio.run_coroutine_threadsafe(self._boot_engine(), self._loop)
        fut.result(timeout=20.0)
        self._alive = True

    def stop(self) -> None:
        """エンジンを停止する."""
        if not self._alive:
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._shutdown_engine(), self._loop)
            fut.result(timeout=5.0)
        except Exception:
            pass
        self._alive = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3.0)
        self._loop = None
        self._thread = None

    def __enter__(self) -> "EngineAnalysisService":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    # ------ public API ------

    def analyze_position(self, position_cmd: str) -> AnalysisResult:
        """1 局面を解析して AnalysisResult を返す.

        Parameters
        ----------
        position_cmd : str
            USI position コマンド (例: "position startpos moves 7g7f")
        """
        if not self._alive or not self._loop:
            return AnalysisResult(ok=False)
        fut = asyncio.run_coroutine_threadsafe(
            self._analyze(position_cmd), self._loop
        )
        try:
            return fut.result(timeout=self._timeout)
        except Exception:
            return AnalysisResult(ok=False)

    def analyze_game(
        self,
        base_position: str,
        moves: List[str],
        sample_interval: int = 1,
    ) -> List[Dict[str, Any]]:
        """棋譜全手を解析して各手の eval_info リストを返す.

        Parameters
        ----------
        base_position : str
            基本局面 (例: "position startpos")
        moves : list[str]
            USI 手のリスト
        sample_interval : int
            N 手ごとにサンプリング (default: 1 = 全手)

        Returns
        -------
        list[dict]
            各サンプル手の {ply, move, ...AnalysisResult.to_eval_info()} のリスト
        """
        results: List[Dict[str, Any]] = []
        prev_score_cp: Optional[int] = None

        for ply in range(0, len(moves) + 1, sample_interval):
            applied = moves[:ply]
            if applied:
                pos_cmd = base_position + " moves " + " ".join(applied)
            else:
                pos_cmd = base_position

            res = self.analyze_position(pos_cmd)

            # 先手視点に統一
            score_cp_sente: Optional[int] = None
            if res.score_cp is not None:
                # エンジンは手番視点で返す。偶数 ply = 先手番（そのまま）、奇数 = 後手番（反転）
                score_cp_sente = res.score_cp if ply % 2 == 0 else -res.score_cp

            delta_cp: Optional[int] = None
            if score_cp_sente is not None and prev_score_cp is not None:
                sente_diff = score_cp_sente - prev_score_cp
                is_sente_move = (ply % 2 == 0)
                delta_cp = sente_diff if is_sente_move else -sente_diff

            current_move = moves[ply] if ply < len(moves) else None

            record = {
                "ply": ply,
                "move": current_move,
                "score_cp": score_cp_sente,
                "score_mate": res.score_mate,
                "bestmove": res.bestmove,
                "pv": res.pv,
                "delta_cp": delta_cp,
            }
            results.append(record)

            if score_cp_sente is not None:
                prev_score_cp = score_cp_sente

        return results

    # ------ internal async ------

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _send(self, cmd: str) -> None:
        if self._proc and self._proc.stdin:
            self._proc.stdin.write((cmd + "\n").encode())
            await self._proc.stdin.drain()

    async def _readline(self, timeout: float = 1.0) -> Optional[str]:
        if not self._proc or not self._proc.stdout:
            return None
        try:
            raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=timeout)
            if not raw:
                return None
            return raw.decode(errors="ignore").strip()
        except asyncio.TimeoutError:
            return None

    async def _wait_for(self, keyword: str, timeout: float = 10.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            line = await self._readline(timeout=1.0)
            if line and keyword in line:
                return True
        return False

    async def _boot_engine(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            self._engine_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ENGINE_WORK_DIR,
        )
        await self._send("usi")
        if not await self._wait_for("usiok", timeout=10.0):
            raise RuntimeError("Engine did not respond with usiok")

        await self._send("setoption name Threads value 1")
        await self._send("setoption name USI_Hash value 64")
        if self._eval_dir and os.path.isdir(self._eval_dir):
            await self._send(f"setoption name EvalDir value {self._eval_dir}")
        await self._send("setoption name OwnBook value false")
        if self._multipv > 1:
            await self._send(f"setoption name MultiPV value {self._multipv}")

        await self._send("isready")
        if not await self._wait_for("readyok", timeout=15.0):
            raise RuntimeError("Engine did not respond with readyok")

        await self._send("usinewgame")

    async def _shutdown_engine(self) -> None:
        if self._proc:
            try:
                await self._send("quit")
                await asyncio.wait_for(self._proc.wait(), timeout=3.0)
            except Exception:
                self._proc.kill()
            self._proc = None

    async def _analyze(self, position_cmd: str) -> AnalysisResult:
        if not self._proc or self._proc.returncode is not None:
            return AnalysisResult(ok=False)

        # 前の解析が残っていたらフラッシュ
        await self._send("isready")
        await self._wait_for("readyok", timeout=2.0)

        cmd = position_cmd if position_cmd.startswith("position") else f"position {position_cmd}"
        await self._send(cmd)
        await self._send(f"go nodes {self._nodes} multipv {self._multipv}")

        cands_map: Dict[int, Dict[str, Any]] = {}
        raw_infos: List[str] = []
        bestmove = ""
        end_time = time.time() + self._timeout

        while time.time() < end_time:
            line = await self._readline(timeout=1.0)
            if not line:
                if self._proc.returncode is not None:
                    return AnalysisResult(ok=False)
                continue
            if line.startswith("info") and "score" in line:
                raw_infos.append(line)
                info = _parse_info_line(line)
                if info:
                    cands_map[info["multipv"]] = info
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) > 1:
                    bestmove = parts[1]
                break

        if not bestmove:
            return AnalysisResult(ok=False, raw_infos=raw_infos)

        sorted_cands = sorted(cands_map.values(), key=lambda x: x["multipv"])

        # 最善候補のスコア
        score_cp: Optional[int] = None
        score_mate: Optional[int] = None
        pv_str = ""
        if sorted_cands:
            top = sorted_cands[0]
            score = top.get("score", {})
            if score.get("type") == "cp":
                score_cp = score.get("cp")
            elif score.get("type") == "mate":
                score_mate = score.get("mate")
            pv_str = top.get("pv", "")

        return AnalysisResult(
            ok=True,
            bestmove=bestmove,
            score_cp=score_cp,
            score_mate=score_mate,
            pv=pv_str,
            multipv=sorted_cands,
            raw_infos=raw_infos,
        )
