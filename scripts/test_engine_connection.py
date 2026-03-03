#!/usr/bin/env python3
"""Step 1: USI エンジン動作確認スクリプト.

やねうら王が正常に起動し、局面解析できることを確認する。
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

# .env を手動ロード（dotenv に依存しない）
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ENGINE_CMD = os.getenv("ENGINE_CMD", "/usr/local/bin/yaneuraou")
EVAL_DIR = os.getenv("ENGINE_EVAL_DIR", "")


async def run_test() -> bool:
    print(f"[1/5] ENGINE_CMD = {ENGINE_CMD}")
    print(f"      ENGINE_EVAL_DIR = {EVAL_DIR}")

    if not os.path.isfile(ENGINE_CMD):
        print(f"  NG: {ENGINE_CMD} が見つかりません")
        return False
    print(f"  OK: バイナリ存在確認")

    if EVAL_DIR and os.path.isdir(EVAL_DIR):
        nn_files = [f for f in os.listdir(EVAL_DIR) if f.endswith(".bin")]
        print(f"  OK: eval ディレクトリに {len(nn_files)} 個の .bin ファイル: {nn_files}")
    else:
        print(f"  WARN: eval ディレクトリが見つかりません ({EVAL_DIR})")

    # --- エンジン起動 ---
    print("\n[2/5] エンジン起動...")
    proc = await asyncio.create_subprocess_exec(
        ENGINE_CMD,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.path.dirname(ENGINE_CMD) or "/usr/local/bin",
    )

    async def send(cmd: str) -> None:
        proc.stdin.write((cmd + "\n").encode())
        await proc.stdin.drain()

    async def read_until(keyword: str, timeout: float = 10.0) -> list[str]:
        lines: list[str] = []
        end = time.time() + timeout
        while time.time() < end:
            try:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if not raw:
                break
            line = raw.decode(errors="ignore").strip()
            if line:
                lines.append(line)
            if keyword in line:
                return lines
        return lines

    # USI ハンドシェイク
    await send("usi")
    lines = await read_until("usiok", timeout=10.0)
    if not any("usiok" in l for l in lines):
        print("  NG: usiok が返りませんでした")
        proc.kill()
        return False
    print("  OK: usi → usiok 成功")

    # オプション設定
    print("\n[3/5] エンジンオプション設定...")
    await send("setoption name Threads value 1")
    await send("setoption name USI_Hash value 64")
    if EVAL_DIR and os.path.isdir(EVAL_DIR):
        await send(f"setoption name EvalDir value {EVAL_DIR}")
    await send("setoption name OwnBook value false")
    await send("setoption name MultiPV value 3")
    await send("isready")
    lines = await read_until("readyok", timeout=15.0)
    if not any("readyok" in l for l in lines):
        print("  NG: readyok が返りませんでした")
        stderr_data = await proc.stderr.read()
        if stderr_data:
            print(f"  STDERR: {stderr_data.decode(errors='ignore')[:500]}")
        proc.kill()
        return False
    print("  OK: isready → readyok 成功")

    # --- 局面解析テスト ---
    print("\n[4/5] 局面解析テスト (position startpos, go nodes 50000 multipv 3)...")
    await send("usinewgame")
    await send("position startpos")
    await send("go nodes 50000 multipv 3")

    info_lines: list[str] = []
    bestmove_line = ""
    end = time.time() + 15.0
    while time.time() < end:
        try:
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=2.0)
        except asyncio.TimeoutError:
            continue
        if not raw:
            break
        line = raw.decode(errors="ignore").strip()
        if not line:
            continue
        if line.startswith("info") and "score" in line:
            info_lines.append(line)
        if line.startswith("bestmove"):
            bestmove_line = line
            break

    if not bestmove_line:
        print("  NG: bestmove が返りませんでした")
        proc.kill()
        return False

    print(f"  OK: bestmove = {bestmove_line}")
    print(f"      info 行数 = {len(info_lines)}")

    # 最終 info 行をパース
    if info_lines:
        last = info_lines[-1]
        print(f"      最終 info: {last[:120]}...")

    # --- 中盤局面テスト ---
    print("\n[5/5] 中盤局面テスト (sfen with moves)...")
    await send("position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e 8d8e")
    await send("go nodes 50000 multipv 1")

    info_lines2: list[str] = []
    bestmove_line2 = ""
    end = time.time() + 15.0
    while time.time() < end:
        try:
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=2.0)
        except asyncio.TimeoutError:
            continue
        if not raw:
            break
        line = raw.decode(errors="ignore").strip()
        if not line:
            continue
        if line.startswith("info") and "score" in line:
            info_lines2.append(line)
        if line.startswith("bestmove"):
            bestmove_line2 = line
            break

    if not bestmove_line2:
        print("  NG: bestmove が返りませんでした")
        proc.kill()
        return False

    print(f"  OK: bestmove = {bestmove_line2}")
    if info_lines2:
        last2 = info_lines2[-1]
        print(f"      最終 info: {last2[:120]}...")

    # 終了
    await send("quit")
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        proc.kill()

    print("\n" + "=" * 50)
    print("全テスト合格: エンジンは正常に動作しています")
    print("=" * 50)
    return True


if __name__ == "__main__":
    ok = asyncio.run(run_test())
    sys.exit(0 if ok else 1)
