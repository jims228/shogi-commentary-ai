"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PieceBase, PieceCode } from "@/lib/sfen";
import type { BoardMatrix } from "@/lib/board";
import { ShogiBoard } from "@/components/ShogiBoard";
import { showToast } from "@/components/ui/toast";

type Side = "sente" | "gote";
type Sq = { x: number; y: number };
type Move = { from?: Sq; to: Sq; piece: string; drop?: boolean };

const PIECE_VALUE: Record<PieceBase, number> = {
  P: 1,
  L: 3,
  N: 3,
  S: 5,
  G: 6,
  B: 8,
  R: 10,
  K: 0,
};

const PIECE_LABEL: Record<PieceBase, string> = {
  P: "歩",
  L: "香",
  N: "桂",
  S: "銀",
  G: "金",
  B: "角",
  R: "飛",
  K: "玉",
};

function pieceScore(base: PieceBase) {
  // 飛100 角80 金60 銀50 桂香30 歩10
  return (PIECE_VALUE[base] ?? 1) * 10;
}

function makeEmptyBoard(): BoardMatrix {
  return Array.from({ length: 9 }, () => Array.from({ length: 9 }, () => null));
}
function cloneBoard(board: BoardMatrix): BoardMatrix {
  return board.map((r) => r.slice());
}
function inside({ x, y }: Sq) {
  return x >= 0 && x < 9 && y >= 0 && y < 9;
}
function keyOf(sq: Sq) {
  return `${sq.x},${sq.y}`;
}
function get(board: BoardMatrix, sq: Sq): PieceCode | null {
  return board[sq.y]?.[sq.x] ?? null;
}
function set(board: BoardMatrix, sq: Sq, p: PieceCode | null): BoardMatrix {
  const nb = cloneBoard(board);
  nb[sq.y][sq.x] = p;
  return nb;
}
function dirY(side: Side) {
  return side === "sente" ? -1 : 1;
}

function isLowerPieceCode(pc: PieceCode) {
  const t = pc.startsWith("+") ? pc.slice(1) : pc;
  return t === t.toLowerCase();
}
function ownerOf(pc: PieceCode): Side {
  return isLowerPieceCode(pc) ? "gote" : "sente";
}
function baseOf(pc: PieceCode): PieceBase {
  const t = pc.startsWith("+") ? pc.slice(1) : pc;
  return t.toUpperCase() as PieceBase;
}
function toOwnerCode(base: PieceBase, side: Side): PieceCode {
  return (side === "sente" ? base : (base.toLowerCase() as any)) as PieceCode;
}

function pick<T>(arr: T[]): T | null {
  if (!arr.length) return null;
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * 利き（成りは今回扱わない）
 */
function getAttacks(board: BoardMatrix, from: Sq, pc: PieceCode): Sq[] {
  const res: Sq[] = [];
  const side = ownerOf(pc);
  const base = baseOf(pc);
  const dy = dirY(side);

  const push = (sq: Sq) => {
    if (inside(sq)) res.push(sq);
  };

  const slide = (dx: number, dy2: number) => {
    let x = from.x + dx;
    let y = from.y + dy2;
    while (inside({ x, y })) {
      const sq = { x, y };
      res.push(sq);
      if (get(board, sq)) break;
      x += dx;
      y += dy2;
    }
  };

  switch (base) {
    case "P":
      push({ x: from.x, y: from.y + dy });
      break;
    case "N":
      push({ x: from.x - 1, y: from.y + 2 * dy });
      push({ x: from.x + 1, y: from.y + 2 * dy });
      break;
    case "S":
      push({ x: from.x - 1, y: from.y + dy });
      push({ x: from.x, y: from.y + dy });
      push({ x: from.x + 1, y: from.y + dy });
      push({ x: from.x - 1, y: from.y - dy });
      push({ x: from.x + 1, y: from.y - dy });
      break;
    case "G":
      push({ x: from.x - 1, y: from.y + dy });
      push({ x: from.x, y: from.y + dy });
      push({ x: from.x + 1, y: from.y + dy });
      push({ x: from.x - 1, y: from.y });
      push({ x: from.x + 1, y: from.y });
      push({ x: from.x, y: from.y - dy });
      break;
    case "K":
      for (let ox = -1; ox <= 1; ox++) {
        for (let oy = -1; oy <= 1; oy++) {
          if (ox === 0 && oy === 0) continue;
          push({ x: from.x + ox, y: from.y + oy });
        }
      }
      break;
    case "L":
      slide(0, dy);
      break;
    case "B":
      slide(1, 1);
      slide(1, -1);
      slide(-1, 1);
      slide(-1, -1);
      break;
    case "R":
      slide(1, 0);
      slide(-1, 0);
      slide(0, 1);
      slide(0, -1);
      break;
  }

  return res;
}

function collectAttackSet(board: BoardMatrix, side: Side): Set<string> {
  const s = new Set<string>();
  for (let y = 0; y < 9; y++) {
    for (let x = 0; x < 9; x++) {
      const pc = board[y][x];
      if (!pc) continue;
      if (ownerOf(pc) !== side) continue;
      for (const a of getAttacks(board, { x, y }, pc)) s.add(keyOf(a));
    }
  }
  return s;
}

function listPieces(board: BoardMatrix, side: Side): { sq: Sq; pc: PieceCode }[] {
  const out: { sq: Sq; pc: PieceCode }[] = [];
  for (let y = 0; y < 9; y++) {
    for (let x = 0; x < 9; x++) {
      const pc = board[y][x];
      if (!pc) continue;
      if (ownerOf(pc) !== side) continue;
      out.push({ sq: { x, y }, pc });
    }
  }
  return out;
}

/**
 * targetSq が「浮き」＝同サイド他駒に守られていない
 */
function isHanging(board: BoardMatrix, targetSq: Sq, enemySide: Side): boolean {
  for (let y = 0; y < 9; y++) {
    for (let x = 0; x < 9; x++) {
      const pc = board[y][x];
      if (!pc) continue;
      if (ownerOf(pc) !== enemySide) continue;
      if (x === targetSq.x && y === targetSq.y) continue;

      const attacks = getAttacks(board, { x, y }, pc);
      if (attacks.some((a) => a.x === targetSq.x && a.y === targetSq.y)) return false;
    }
  }
  return true;
}

function findPlayerSq(board: BoardMatrix, playerSide: Side, playerPiece: PieceBase): Sq | null {
  for (let y = 0; y < 9; y++) {
    for (let x = 0; x < 9; x++) {
      const pc = board[y][x];
      if (!pc) continue;
      if (ownerOf(pc) !== playerSide) continue;
      if (baseOf(pc) !== playerPiece) continue;
      return { x, y };
    }
  }
  return null;
}

export type UkiCaptureResult = {
  gain: number;
  loss: number;
  net: number;
  captures: number;
};

export function UkiCaptureShogiGame(props: {
  durationSec?: number; // default 60
  playerSide?: Side; // default sente
  playerPiece?: PieceBase; // default S
  playerStart?: Sq; // default {4,6}
  targetPool?: PieceBase[]; // default ["P","L","N","S","G","B","R"]
  targetCount?: number; // default 4
  onTick?: (secLeft: number) => void;
  onScore?: (result: UkiCaptureResult) => void;
  onFinish?: (result: UkiCaptureResult) => void;
}) {
  const { onTick, onScore, onFinish } = props;

  const durationSec = props.durationSec ?? 60;
  const playerSide: Side = props.playerSide ?? "sente";
  const enemySide: Side = playerSide === "sente" ? "gote" : "sente";
  const playerPiece: PieceBase = props.playerPiece ?? "S";
  const playerStart: Sq = props.playerStart ?? { x: 4, y: 6 };
  const targetPool: PieceBase[] = props.targetPool ?? ["P", "L", "N", "S", "G", "B", "R"];
  const targetCount = props.targetCount ?? 4;

  const emptyHands = useMemo(() => ({ b: {}, w: {} }), []);

  const [board, setBoard] = useState<BoardMatrix>(() => {
    let b = makeEmptyBoard();
    b = set(b, playerStart, toOwnerCode(playerPiece, playerSide));
    return b;
  });

  const [hands, setHands] = useState<any>(emptyHands);

  const [running, setRunning] = useState(false);
  const [secLeft, setSecLeft] = useState(durationSec);

  const [gain, setGain] = useState(0);
  const [loss, setLoss] = useState(0);
  const [captures, setCaptures] = useState(0);

  const result = useMemo<UkiCaptureResult>(() => {
    return { gain, loss, net: gain - loss, captures };
  }, [gain, loss, captures]);

  // 親へスコア通知（resultが変わった時だけ）
  useEffect(() => {
    onScore?.(result);
  }, [onScore, result]);

  // 終了時に最新resultを使う
  const resultRef = useRef(result);
  useEffect(() => {
    resultRef.current = result;
  }, [result]);

  // 不正操作の巻き戻し用
  const lastGoodRef = useRef<{ board: BoardMatrix; hands: any }>({ board, hands });
  useEffect(() => {
    lastGoodRef.current = { board, hands };
  }, [board, hands]);

  // 「次の onBoardChange は無視して巻き戻す」フラグ（不正move対策）
  const rejectNextBoardChangeRef = useRef(false);

  // 救済toastのスパム防止
  const lastRescueToastAtRef = useRef(0);

  /**
   * 盤面保守（副作用なし！）
   * - 相手駒数が足りなければ補充
   * - 取れる浮き駒が0なら、相手駒1枚をワープして「取れる浮き駒」を作る
   */
  const maintainBoardPure = useCallback(
    (baseBoard: BoardMatrix): { board: BoardMatrix; rescued: boolean; spawned: number } => {
      let b = baseBoard;

      // 自駒の位置・利き
      let playerSq = findPlayerSq(b, playerSide, playerPiece);
      if (!playerSq) {
        // 自駒が消えていたら復元（念のため）
        b = set(b, playerStart, toOwnerCode(playerPiece, playerSide));
        playerSq = playerStart;
      }
      const playerPc = get(b, playerSq);
      if (!playerPc) {
        b = set(b, playerStart, toOwnerCode(playerPiece, playerSide));
      }

      const reserved = new Set<string>([keyOf(playerStart)]); // startは敵スポーン禁止
      const pSqNow = findPlayerSq(b, playerSide, playerPiece);
      if (pSqNow) reserved.add(keyOf(pSqNow));

      const pcNow = pSqNow ? get(b, pSqNow) : null;
      const attacksSet = pcNow ? new Set(getAttacks(b, pSqNow!, pcNow).map(keyOf)) : new Set<string>();

      // ---- 1) 相手駒の補充（足りない分だけ）
      let spawned = 0;

      const countEnemy = (bb: BoardMatrix) => listPieces(bb, enemySide).length;

      const spawnOne = (bb: BoardMatrix): BoardMatrix | null => {
        const emptiesInAttack: Sq[] = [];
        for (let y = 0; y < 9; y++) {
          for (let x = 0; x < 9; x++) {
            const sq = { x, y };
            if (get(bb, sq)) continue;
            if (reserved.has(keyOf(sq))) continue;
            if (!attacksSet.has(keyOf(sq))) continue; // 取れる位置を優先（=利き内）
            emptiesInAttack.push(sq);
          }
        }
        if (!emptiesInAttack.length) return null;

        for (let t = 0; t < 300; t++) {
          const sq = pick(emptiesInAttack);
          if (!sq) break;
          if (get(bb, sq)) continue;

          const base = pick(targetPool);
          if (!base) break;
          const code = toOwnerCode(base, enemySide);

          const trial = set(bb, sq, code);
          if (!isHanging(trial, sq, enemySide)) continue; // 浮き優先
          return trial;
        }
        return null;
      };

      while (countEnemy(b) < targetCount) {
        const nb = spawnOne(b);
        if (!nb) break;
        b = nb;
        spawned += 1;
      }

      // ---- 2) 「取れる浮き駒」があるか？
      const hasCapturableHanging = (bb: BoardMatrix) => {
        const enemies = listPieces(bb, enemySide);
        return enemies.some(({ sq }) => attacksSet.has(keyOf(sq)) && isHanging(bb, sq, enemySide));
      };

      if (hasCapturableHanging(b)) {
        return { board: b, rescued: false, spawned };
      }

      // ---- 3) 救済：相手駒1枚を “ワープ” して取れる浮き駒を作る（消さない）
      const enemies = listPieces(b, enemySide);
      if (!enemies.length) return { board: b, rescued: false, spawned };

      // ワープ先候補：空き & 利き内 & reserved以外
      const dests: Sq[] = [];
      for (let y = 0; y < 9; y++) {
        for (let x = 0; x < 9; x++) {
          const sq = { x, y };
          if (get(b, sq)) continue;
          if (reserved.has(keyOf(sq))) continue;
          if (!attacksSet.has(keyOf(sq))) continue;
          dests.push(sq);
        }
      }
      if (!dests.length) return { board: b, rescued: false, spawned };

      // 候補の敵（できれば「今取れない」やつ）
      const enemyCandidates = enemies.filter(({ sq }) => !attacksSet.has(keyOf(sq)) || !isHanging(b, sq, enemySide));
      const candidates = enemyCandidates.length ? enemyCandidates : enemies;

      for (let t = 0; t < 600; t++) {
        const from = pick(candidates);
        const to = pick(dests);
        if (!from || !to) break;
        if (from.sq.x === to.x && from.sq.y === to.y) continue;

        const pc = from.pc;
        let trial = b;
        trial = set(trial, from.sq, null);
        trial = set(trial, to, pc);

        // ワープした駒が「浮き」になること
        if (!isHanging(trial, to, enemySide)) continue;

        // ワープした結果、取れる浮きができたか
        if (!hasCapturableHanging(trial)) continue;

        return { board: trial, rescued: true, spawned };
      }

      return { board: b, rescued: false, spawned };
    },
    [enemySide, playerPiece, playerSide, playerStart, targetCount, targetPool],
  );

  const resetAll = useCallback(() => {
    let b = makeEmptyBoard();
    b = set(b, playerStart, toOwnerCode(playerPiece, playerSide));
    setBoard(b);
    setHands(emptyHands);
    setGain(0);
    setLoss(0);
    setCaptures(0);
    setSecLeft(durationSec);
    setRunning(false);
  }, [durationSec, emptyHands, playerPiece, playerSide, playerStart]);

  const start = useCallback(() => {
    setGain(0);
    setLoss(0);
    setCaptures(0);
    setSecLeft(durationSec);
    setHands(emptyHands);

    // 初期配置を整形（ここは副作用なし関数なのでOK）
    setBoard((prev) => maintainBoardPure(prev).board);
    setRunning(true);
  }, [durationSec, emptyHands, maintainBoardPure]);

  // タイマー
  useEffect(() => {
    if (!running) return;

    const end = Date.now() + durationSec * 1000;
    const id = window.setInterval(() => {
      const leftMs = Math.max(0, end - Date.now());
      const s = Math.ceil(leftMs / 1000);
      setSecLeft(s);
      onTick?.(s);

      if (leftMs <= 0) {
        window.clearInterval(id);
        setRunning(false);
        onFinish?.(resultRef.current);

        showToast({
          title: "終了！",
          description: `Net ${resultRef.current.net}（駒得${resultRef.current.gain} / 駒損${resultRef.current.loss}）`,
        });
      }
    }, 200);

    return () => window.clearInterval(id);
  }, [durationSec, onFinish, onTick, running]);

  /**
   * moveの段階で：
   * - 自分の練習駒以外は不可
   * - 打ちは不可
   * - 利きに沿わない移動は不可（効きの学習）
   * - 取ったら駒得加点
   */
  const handleMove = useCallback(
    (move: Move) => {
      if (!running) return;

      if (move.drop || !move.from) {
        rejectNextBoardChangeRef.current = true;
        showToast({ title: "操作不可", description: "この練習では駒を打てません。" });
        return;
      }

      const before = lastGoodRef.current.board;
      const fromPc = get(before, move.from);

      if (!fromPc || ownerOf(fromPc) !== playerSide || baseOf(fromPc) !== playerPiece) {
        rejectNextBoardChangeRef.current = true;
        showToast({ title: "操作不可", description: `自分の練習駒（${PIECE_LABEL[playerPiece]}）だけ動かしてください。` });
        return;
      }

      // 利きに沿わない移動は不可
      const legal = new Set(getAttacks(before, move.from, fromPc).map(keyOf));
      if (!legal.has(keyOf(move.to))) {
        rejectNextBoardChangeRef.current = true;
        showToast({ title: "そこには動けない", description: "利きの範囲に動かしてください。" });
        return;
      }

      // 取った駒の点数（駒得）
      const captured = get(before, move.to);
      if (captured && ownerOf(captured) === enemySide) {
        const base = baseOf(captured);
        const add = pieceScore(base);
        setGain((v) => v + add);
        setCaptures((v) => v + 1);
        showToast({ title: `駒得！ +${add}`, description: `${PIECE_LABEL[base]}を取った` });
      }
    },
    [enemySide, playerPiece, playerSide, running],
  );

  /**
   * board更新を受け取った後に：
   * - 不正moveなら巻き戻す
   * - 危険マスに置いたら取られる（駒損＋初期位置へ戻す）
   * - その後、敵補充＆救済（浮き駒生成）を行う
   */
  const handleBoardChange = useCallback(
    (nextBoard: BoardMatrix) => {
      if (!running) {
        setBoard(nextBoard);
        return;
      }

      // 不正moveの直後にShogiBoardがboardChangeしてきたら巻き戻す
      if (rejectNextBoardChangeRef.current) {
        rejectNextBoardChangeRef.current = false;
        const snap = lastGoodRef.current;
        setBoard(snap.board);
        setHands(snap.hands);
        return;
      }

      let b = nextBoard;

      // 1) 危険マスなら取られる扱い（駒損）
      const playerSq = findPlayerSq(b, playerSide, playerPiece);
      if (playerSq) {
        const enemyAtk = collectAttackSet(b, enemySide);
        if (enemyAtk.has(keyOf(playerSq))) {
          const penalty = pieceScore(playerPiece);
          setLoss((v) => v + penalty);

          showToast({
            title: `駒損！ -${penalty}`,
            description: `相手の利きの中（${PIECE_LABEL[playerPiece]}が取られる扱い）`,
          });

          b = set(b, playerSq, null);
          // startが埋まってたら困るので、ここで強制的に置く（敵はstart禁止にしてる）
          b = set(b, playerStart, toOwnerCode(playerPiece, playerSide));
        }
      }

      // 2) 敵補充＆救済
      const m = maintainBoardPure(b);
      b = m.board;

      // 3) 最終反映
      setBoard(b);

      // 救済toast（スパム防止：0.8秒クールダウン）
      if (m.rescued) {
        const now = Date.now();
        if (now - lastRescueToastAtRef.current > 800) {
          lastRescueToastAtRef.current = now;
          showToast({
            title: "救済：取れる浮き駒を作った",
            description: "取れる浮き駒が無かったので、相手駒を1枚ワープしました。",
          });
        }
      }
    },
    [enemySide, maintainBoardPure, playerPiece, playerSide, playerStart, running],
  );

  /**
   * hands更新を受け取っても常に空に戻す（ドロップ/持ち駒化を防ぐ）
   */
  const handleHandsChange = useCallback(
    (_nextHands: any) => {
      if (!running) {
        setHands(emptyHands);
        return;
      }
      setHands(emptyHands);
    },
    [emptyHands, running],
  );

  return (
    <div className="w-full h-full">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-3 text-sm">
          <div className="font-bold">
            Time{" "}
            <span className={secLeft <= 10 && running ? "text-red-600 font-extrabold" : ""}>{secLeft}s</span>
          </div>
          <div className="font-bold">
            駒得 <span className="text-emerald-700">{gain}</span>
          </div>
          <div className="font-bold">
            駒損 <span className="text-rose-700">{loss}</span>
          </div>
          <div className="font-extrabold">Net {gain - loss}</div>
        </div>

        <div className="flex items-center gap-2">
          {!running ? (
            <button
              onClick={start}
              className="px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold active:scale-95 transition"
            >
              Start 60s
            </button>
          ) : (
            <button
              onClick={() => setRunning(false)}
              className="px-3 py-2 rounded-xl border font-bold hover:bg-accent active:scale-95 transition"
            >
              Stop
            </button>
          )}
          <button
            onClick={resetAll}
            className="px-3 py-2 rounded-xl border font-bold hover:bg-accent active:scale-95 transition"
          >
            Reset
          </button>
        </div>
      </div>

      <ShogiBoard
        board={board}
        hands={hands}
        mode="edit"
        onMove={handleMove}
        onBoardChange={handleBoardChange}
        onHandsChange={handleHandsChange}
        orientation="sente"
      />
    </div>
  );
}
