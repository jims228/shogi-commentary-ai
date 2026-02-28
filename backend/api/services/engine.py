"""
backend/api/engine_state.py
Engine process management (StreamEngine / BatchEngine) and shared config.
Extracted from main.py to allow routers to import without circular deps.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import time
from typing import Optional, Dict, Any, List, AsyncGenerator

# ====== 設定 ======
USI_CMD = os.getenv("USI_CMD", "/usr/local/bin/yaneuraou")
ENGINE_WORK_DIR = os.getenv("ENGINE_WORK_DIR", "/usr/local/bin")
EVAL_DIR = os.getenv("EVAL_DIR", "/usr/local/bin/eval")

SCORE_SCALE = 0.7

USI_BOOT_TIMEOUT = 10.0
USI_GO_TIMEOUT = 20.0

# Set by main.py lifespan so _EngineAdapter can schedule coroutines
_MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None


def is_gote_turn(position_cmd: str) -> bool:
    if "startpos" in position_cmd:
        if "moves" not in position_cmd:
            return False
        moves_part = position_cmd.split("moves")[1].strip()
        if not moves_part:
            return False
        moves = moves_part.split()
        return len(moves) % 2 != 0
    if "sfen" in position_cmd:
        parts = position_cmd.split()
        try:
            sfen_index = parts.index("sfen")
            turn = parts[sfen_index + 2]
            return turn == "w"
        except Exception:
            return False
    return False


class BaseEngine:
    def __init__(self, name: str = "Engine"):
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.name = name

    async def _send_line(self, s: str) -> None:
        if self.proc and self.proc.stdin:
            try:
                self.proc.stdin.write((s + "\n").encode())
                await self.proc.stdin.drain()
            except Exception as e:
                print(f"[{self.name}] Send Error: {e}")

    async def _read_line(self, timeout: float = 0.5) -> Optional[str]:
        if not self.proc or not self.proc.stdout:
            return None
        try:
            line_bytes = await asyncio.wait_for(self.proc.stdout.readline(), timeout=timeout)
            if not line_bytes:
                return None
            line = line_bytes.decode(errors="ignore").strip()
            if line and (line.startswith("bestmove") or line.startswith("checkmate")):
                print(f"[{self.name}] <<< {line}")
            return line
        except asyncio.TimeoutError:
            return None

    async def _wait_until(self, pred, timeout: float) -> None:
        end = time.time() + timeout
        while time.time() < end:
            line = await self._read_line(timeout=0.5)
            if line and pred(line):
                break

    async def _log_stderr(self) -> None:
        if self.proc and self.proc.stderr:
            try:
                data = await self.proc.stderr.read()
                if data:
                    msg = data.decode(errors="ignore").strip()
                    print(f"[{self.name}] [STDERR] {msg}")
            except Exception:
                pass

    def parse_usi_info(self, line: str) -> Optional[Dict[str, Any]]:
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


class EngineState(BaseEngine):
    def __init__(self, name: str = "StreamEngine"):
        super().__init__(name=name)
        self.lock = asyncio.Lock()
        self.cancel_event = asyncio.Event()

    async def ensure_alive(self) -> None:
        if self.proc and self.proc.returncode is None:
            return
        print(f"[{self.name}] Starting: {USI_CMD}")
        try:
            self.proc = await asyncio.create_subprocess_exec(
                USI_CMD,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=ENGINE_WORK_DIR,
            )
            await self._send_line("usi")
            await self._wait_until(lambda l: "usiok" in l, USI_BOOT_TIMEOUT)
            await self._send_line("setoption name Threads value 1")
            await self._send_line("setoption name USI_Hash value 64")
            if os.path.exists(EVAL_DIR):
                await self._send_line(f"setoption name EvalDir value {EVAL_DIR}")
            await self._send_line("setoption name OwnBook value false")
            await self._send_line("setoption name MultiPV value 3")
            await self._send_line("isready")
            await self._wait_until(lambda l: "readyok" in l, USI_BOOT_TIMEOUT)
            await self._send_line("usinewgame")
            await self._send_line("isready")
            await self._wait_until(lambda l: "readyok" in l, 5.0)
            print(f"[{self.name}] Ready")
        except Exception as e:
            print(f"[{self.name}] Start Failed: {e}")
            await self._log_stderr()
            self.proc = None

    async def stop_and_flush(self) -> None:
        if not self.proc:
            return
        await self._send_line("stop")
        end_time = time.time() + 0.5
        while time.time() < end_time:
            line = await self._read_line(timeout=0.1)
            if not line:
                continue
            if line.startswith("bestmove"):
                return

    async def cancel_current(self) -> None:
        self.cancel_event.set()

    async def stream_analyze(self, req) -> AsyncGenerator[str, None]:  # req: AnalyzeIn
        async with self.lock:
            self.cancel_event.clear()
            await self.ensure_alive()
            if not self.proc:
                yield f"data: {json.dumps({'error': 'Engine not available'})}\n\n"
                return
            await self.stop_and_flush()
            await self._send_line("isready")
            await self._wait_until(lambda l: "readyok" in l, 2.0)
            pos_cmd = (
                req.position
                if req.position.startswith("position")
                else f"position {req.position}"
            )
            await self._send_line(pos_cmd)
            is_gote = is_gote_turn(pos_cmd)
            await self._send_line(f"go depth {req.depth} multipv {req.multipv}")
            while True:
                if self.cancel_event.is_set():
                    self.cancel_event.clear()
                    await self.stop_and_flush()
                    break
                line = await self._read_line(timeout=2.0)
                if line is None:
                    yield ": keepalive\n\n"
                    if self.proc and self.proc.returncode is not None:
                        break
                    continue
                if not line:
                    break
                if line.startswith("bestmove"):
                    parts = line.split()
                    if len(parts) > 1:
                        yield f"data: {json.dumps({'bestmove': parts[1]})}\n\n"
                    break
                info = self.parse_usi_info(line)
                if info:
                    if is_gote and "score" in info:
                        s = info["score"]
                        if s["type"] == "cp":
                            s["cp"] = -s["cp"]
                        elif s["type"] == "mate":
                            s["mate"] = -s["mate"]
                    yield f"data: {json.dumps({'multipv_update': info})}\n\n"

    async def solve_tsume_hand(self, sfen: str) -> Dict[str, Any]:
        async with self.lock:
            await self.ensure_alive()
            if not self.proc:
                return {"status": "error", "message": "Engine not started"}
            is_idle = False
            try:
                await self._send_line("isready")
                await self._wait_until(lambda l: "readyok" in l, 0.1)
                is_idle = True
            except asyncio.TimeoutError:
                is_idle = False
            if not is_idle:
                await self.stop_and_flush()
                await self._send_line("isready")
                await self._wait_until(lambda l: "readyok" in l, 2.0)
            sfen_cmd = sfen if sfen.startswith("sfen") else f"sfen {sfen}"
            cmd = f"position {sfen_cmd}"
            await self._send_line(cmd)
            await self._send_line("go nodes 2000")
            bestmove = None
            mate_found = False
            start_time = time.time()
            while time.time() - start_time < 5.0:
                line = await self._read_line(timeout=1.0)
                if not line:
                    if self.proc.returncode is not None:
                        self.proc = None
                        return {"status": "error", "message": "Engine crashed"}
                    continue
                if "score mate -" in line:
                    mate_found = True
                elif "score mate +" in line:
                    mate_found = False
                if line.startswith("bestmove"):
                    parts = line.split()
                    if len(parts) > 1:
                        bestmove = parts[1]
                    break
            if not bestmove:
                await self.stop_and_flush()
                return {"status": "error", "message": "Timeout"}
            print(f"[{self.name}] Escape: {bestmove}, Mate: {mate_found}")
            if bestmove == "resign":
                return {"status": "win", "bestmove": "resign", "message": "正解！詰みました！"}
            elif bestmove == "win":
                return {"status": "lose", "bestmove": "win", "message": "不正解：入玉されてしまいました"}
            else:
                if mate_found:
                    return {"status": "continue", "bestmove": bestmove, "message": "正解！"}
                else:
                    return {"status": "incorrect", "bestmove": bestmove, "message": "その手では詰みません"}


class BatchEngineState(EngineState):
    def __init__(self) -> None:
        super().__init__(name="BatchEngine")

    async def fast_analyze_one(self, position_cmd: str) -> Dict[str, Any]:
        if not self.proc:
            return {"ok": False}
        await self._send_line(position_cmd)
        await self._send_line("go nodes 150000 multipv 1")
        bestmove = None
        cands_map: Dict[int, Any] = {}
        end_time = time.time() + 10.0
        while time.time() < end_time:
            line = await self._read_line(timeout=0.5)
            if not line:
                continue
            if "score" in line and "pv" in line:
                info = self.parse_usi_info(line)
                if info and "multipv" in info:
                    cands_map[info["multipv"]] = info
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) > 1:
                    bestmove = parts[1]
                break
        sorted_cands = sorted(cands_map.values(), key=lambda x: x["multipv"])
        return {"ok": bestmove is not None, "bestmove": bestmove, "multipv": sorted_cands}

    async def stream_batch_analyze(
        self, moves: List[str], time_budget_ms: int = None
    ) -> AsyncGenerator[str, None]:
        async with self.lock:
            self.cancel_event.clear()
            await self.ensure_alive()
            await self.stop_and_flush()
            yield json.dumps({"status": "start"}) + (" " * 4096) + "\n"
            start_time = time.time()
            for i in range(len(moves) + 1):
                if self.cancel_event.is_set():
                    self.cancel_event.clear()
                    await self.stop_and_flush()
                    break
                if time_budget_ms and (time.time() - start_time > time_budget_ms / 1000):
                    print(f"[{self.name}] Time budget exceeded at ply {i}")
                    break
                pos_str = "startpos moves " + " ".join(moves[:i]) if i > 0 else "startpos"
                pos_cmd = f"position {pos_str}"
                res = await self.fast_analyze_one(pos_cmd)
                if res["ok"]:
                    if i % 2 != 0:
                        for item in res["multipv"]:
                            if "score" in item:
                                s = item["score"]
                                if s["type"] == "cp":
                                    s["cp"] = -s["cp"]
                                elif s["type"] == "mate":
                                    s["mate"] = -s["mate"]
                    json_str = json.dumps({"ply": i, "result": res})
                    yield json_str + (" " * 4096) + "\n"
                    await asyncio.sleep(0)
                else:
                    print(f"[{self.name}] Analysis failed at ply {i}")


# ★ Singleton instances (created once at import; lifespan wires up _MAIN_LOOP)
stream_engine = EngineState(name="StreamEngine")
batch_engine = BatchEngineState()
