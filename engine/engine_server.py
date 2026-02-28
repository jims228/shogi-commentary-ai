from __future__ import annotations
import asyncio, os, re, shlex
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

USI_CMD = os.getenv("USI_CMD", "/usr/local/bin/yaneuraou")  # コンテナ内の実行パス
USI_BOOT_TIMEOUT = float(os.getenv("USI_BOOT_TIMEOUT", "10"))
USI_GO_TIMEOUT = float(os.getenv("USI_GO_TIMEOUT", "20"))

app = FastAPI(title="USI Engine Gateway")

# --- CORS ---
_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]
_env_origins = os.getenv("FRONTEND_ORIGINS", "")
_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeIn(BaseModel):
    # 例: "startpos" / "sfen <...>" / "startpos moves 7g7f 3c3d ..."
    position: str
    depth: int = 16
    multipv: int = 3

class EngineState:
    def __init__(self):
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.lock = asyncio.Lock()

    async def ensure_alive(self):
        if self.proc and self.proc.returncode is None:
            return
        # 起動
        self.proc = await asyncio.create_subprocess_exec(
            *shlex.split(USI_CMD),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        # 初期ハンドシェイク
        await self._send_line("usi")
        # USI応答待ち
        await self._wait_until(lambda l: "usiok" in l, USI_BOOT_TIMEOUT)
        # 準備完了待ち
        await self._send_line("isready")
        await self._wait_until(lambda l: "readyok" in l, USI_BOOT_TIMEOUT)
        # 新対局宣言
        await self._send_line("usinewgame")

    async def _send_line(self, s: str):
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((s + "\n").encode())
        await self.proc.stdin.drain()

    async def _read_line(self, timeout: float | None = None) -> Optional[str]:
        assert self.proc and self.proc.stdout
        try:
            line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        if not line:
            return None
        return line.decode(errors="ignore").strip()

    async def _wait_until(self, pred, timeout: float) -> List[str]:
        buf: List[str] = []
        end = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end:
            line = await self._read_line(timeout=timeout)
            if line is None:
                break
            buf.append(line)
            if pred(line):
                return buf
        return buf

    async def analyze(self, position: str, depth: int, multipv: int) -> Dict[str, Any]:
        async with self.lock:
            await self.ensure_alive()
            # 局面設定
            await self._send_line(f"position {position}")
            # 解析コマンド
            await self._send_line(f"go depth {depth} multipv {multipv}")
            # 'bestmove' が来るまでログ収集
            logs: List[str] = []
            bestmove: Optional[str] = None
            multipv_items: List[Dict[str, Any]] = []

            # USI info 行の簡易パーサ
            bestmove_re = re.compile(r"bestmove\s+(\S+)")
            info_re = re.compile(r"info .*?score (cp|mate) ([\-0-9]+).*?pv (.+)")
            mpv_re = re.compile(r"multipv\s+(\d+)")
            end_time = asyncio.get_event_loop().time() + USI_GO_TIMEOUT

            while asyncio.get_event_loop().time() < end_time:
                line = await self._read_line(timeout=0.5)
                if not line:
                    continue
                logs.append(line)
                m = bestmove_re.search(line)
                if m:
                    bestmove = m.group(1)
                    break
                mi = info_re.search(line)
                if mi:
                    kind, val, pv = mi.group(1), mi.group(2), mi.group(3)
                    mpv = 1
                    mm = mpv_re.search(line)
                    if mm:
                        mpv = int(mm.group(1))
                    score: Dict[str, Any] = {"type": kind}
                    if kind == "cp":
                        score["cp"] = int(val)
                    else:
                        score["mate"] = int(val)
                    multipv_items.append({"multipv": mpv, "score": score, "pv": pv})

            raw = "\n".join(logs)
            return {
                "ok": bestmove is not None,
                "bestmove": bestmove,
                "multipv": sorted(multipv_items, key=lambda x: x.get("multipv", 99)) or None,
                "raw": raw,
            }

engine = EngineState()

@app.get("/")
def root(): return {"message": "engine ok (usi)"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(body: AnalyzeIn, request: Request):
    # minimal request logging
    try:
        print(f"[engine] /analyze from {request.client.host if request.client else '?'} position[:60]={body.position[:60]!r} depth={body.depth} multipv={body.multipv}")
    except Exception:
        pass
    try:
        result = await engine.analyze(body.position, body.depth, body.multipv)
        status = 200 if result.get("ok") else 502
        return result if status == 200 else (result, status)
    except Exception as e:
        return {"ok": False, "error": "engine_exception", "detail": str(e)}, 500

@app.post("/reload")
async def reload_engine():
    # 簡易：プロセスを落として次回 ensure_alive で再起動
    if engine.proc and engine.proc.returncode is None:
        engine.proc.kill()
    engine.proc = None
    return {"ok": True}

# ====== entrypoint ======
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("ENGINE_HOST", os.getenv("HOST", "0.0.0.0"))
    try:
        port = int(os.getenv("ENGINE_PORT", os.getenv("PORT", "8001")))
    except Exception:
        port = 8001
    log_level = os.getenv("LOG_LEVEL", "info")
    print(f"[engine] Starting uvicorn on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level=log_level)
