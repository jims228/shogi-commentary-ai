"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PieceBase, PieceCode } from "@/lib/sfen";
import type { BoardMatrix } from "@/lib/board";
import { ShogiBoard } from "@/components/ShogiBoard";
import { showToast } from "@/components/ui/toast";

type Side = "sente" | "gote";
type Sq = { x: number; y: number };

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

function makeEmptyBoard(): BoardMatrix {
  return Array.from({ length: 9 }, () => Array.from({ length: 9 }, () => null));
}

function inside({ x, y }: Sq) {
  return x >= 0 && x < 9 && y >= 0 && y < 9;
}

function key(sq: Sq) {
  return `${sq.x},${sq.y}`;
}

function cloneBoard(board: BoardMatrix): BoardMatrix {
  return board.map((row) => row.slice());
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
  // "+p" みたいな形式もあるので先頭+を外して判定
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

function pieceScore(base: PieceBase) {
  return (PIECE_VALUE[base] ?? 1) * 10;
}

/**
 * 最小の「利き」生成（成りは今回は使わない前提。必要なら拡張可）
 * - 盤上の PieceCode に対して owner を見て前方向を変える
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
      for (let ox = -1; ox <= 1; ox++) for (let oy = -1; oy <= 1; oy++) {
        if (ox === 0 && oy === 0) continue;
        push({ x: from.x + ox, y: from.y + oy });
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
  for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
    const pc = board[y][x];
    if (!pc) continue;
    if (ownerOf(pc) !== side) continue;
    for (const a of getAttacks(board, { x, y }, pc)) s.add(key(a));
  }
  return s;
}

function listPieces(board: BoardMatrix, side: Side): { sq: Sq; pc: PieceCode }[] {
  const out: { sq: Sq; pc: PieceCode }[] = [];
  for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
    const pc = board[y][x];
    if (!pc) continue;
    if (ownerOf(pc) !== side) continue;
    out.push({ sq: { x, y }, pc });
  }
  return out;
}

/** 相手駒が「浮き」＝同サイド他駒に守られていない */
function isHanging(board: BoardMatrix, targetSq: Sq, enemySide: Side): boolean {
  for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
    const pc = board[y][x];
    if (!pc) continue;
    if (ownerOf(pc) !== enemySide) continue;
    if (x === targetSq.x && y === targetSq.y) continue;
    const attacks = getAttacks(board, { x, y }, pc);
    if (attacks.some((a) => a.x === targetSq.x && a.y === targetSq.y)) return false;
  }
  return true;
}

function findPlayerSq(board: BoardMatrix, playerSide: Side, playerPiece: PieceBase): Sq | null {
  for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
    const pc = board[y][x];
    if (!pc) continue;
    if (ownerOf(pc) !== playerSide) continue;
    if (baseOf(pc) !== playerPiece) continue;
    return { x, y };
  }
  return null;
}

function pick<T>(arr: T[]): T | null {
  if (!arr.length) return null;
  return arr[Math.floor(Math.random() * arr.length)];
}

export type UkiCaptureResult = {
  gain: number;
  loss: number;
  net: number;
  captures: number;
};

export function UkiCaptureShogiGame(props: {
  durationSec?: number;            // default 60
  playerSide?: Side;               // default "sente"
  playerPiece?: PieceBase;         // default "S"
  playerStart?: Sq;                // default {4,6}
  targetPool?: PieceBase[];        // default ["P","L","N","S","G","B","R"]
  targetCount?: number;            // default 4 (安定)
  onTick?: (secLeft: number) => void;
  onFinish?: (result: UkiCaptureResult) => void;
  /** 外側でスコア表示したい場合 */
  onScore?: (result: UkiCaptureResult) => void;
}) {
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

  const [gain, setGain] = useState(0); // 駒得
  const [loss, setLoss] = useState(0); // 駒損
  const [captures, setCaptures] = useState(0);

  // 内部スナップショット（不正操作を即戻す用）
  const lastGoodRef = useRef<{ board: BoardMatrix; hands: any }>({ board, hands });
  useEffect(() => {
    lastGoodRef.current = { board, hands };
  }, [board, hands]);

  const result = useMemo<UkiCaptureResult>(() => {
    return { gain, loss, net: gain - loss, captures };
  }, [gain, loss, captures]);

  useEffect(() => {
    props.onScore?.(result);
  }, [result, props]);

  // タイマー
  useEffect(() => {
    if (!running) return;
    const end = Date.now() + durationSec * 1000;

    const id = window.setInterval(() => {
      const leftMs = Math.max(0, end - Date.now());
      const s = Math.ceil(leftMs / 1000);
      setSecLeft(s);
      props.onTick?.(s);

      if (leftMs <= 0) {
        window.clearInterval(id);
        setRunning(false);
        props.onFinish?.(result);
        showToast({ title: "終了！", description: `スコア ${result.net}（駒得${result.gain} / 駒損${result.loss}）` });
      }
    }, 200);

    return () => window.clearInterval(id);
    // result は終了時に最新を使いたいので依存に入れない（toastは最後に出る）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, durationSec]);

  // 初期化 / リスタート
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

  // 目標数まで “浮き駒” を補充（常に取れる位置＝自分の利き内に出す）
  const maintainTargets = useCallback(
    (baseBoard: BoardMatrix) => {
      let b = baseBoard;

      const playerSq = findPlayerSq(b, playerSide, playerPiece);
      if (!playerSq) return b;

      const playerPc = get(b, playerSq);
      if (!playerPc) return b;

      const playerAttacks = new Set(getAttacks(b, playerSq, playerPc).map(key));

      const enemies = listPieces(b, enemySide);
      let need = Math.max(0, targetCount - enemies.length);
      if (need <= 0) return b;

      // 候補：空マスかつ自分の利きの中（=今すぐ取れる）
      const empties: Sq[] = [];
      for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
        const sq = { x, y };
        if (get(b, sq)) continue;
        if (!playerAttacks.has(key(sq))) continue;
        empties.push(sq);
      }

      // fallback：利き内が空なら、どこでも良い（詰み防止）
      const fallbackEmpties: Sq[] = [];
      if (empties.length === 0) {
        for (let y = 0; y < 9; y++) for (let x = 0; x < 9; x++) {
          const sq = { x, y };
          if (get(b, sq)) continue;
          fallbackEmpties.push(sq);
        }
      }

      const pool = empties.length ? empties : fallbackEmpties;
      if (!pool.length) return b;

      for (let i = 0; i < need; i++) {
        // 何度か試して “浮き” を満たす配置を探す
        let placed = false;
        for (let t = 0; t < 200; t++) {
          const sq = pick(pool);
          if (!sq) break;
          if (get(b, sq)) continue;
          const code = toOwnerCode(pick(targetPool)!, enemySide);

          const trial = set(b, sq, code);
          if (!isHanging(trial, sq, enemySide)) continue;

          b = trial;
          placed = true;
          break;
        }
        if (!placed) break;
      }
      return b;
    },
    [enemySide, playerPiece, playerSide, targetCount, targetPool],
  );

  // board が変わったら補充＆手駒を空に戻す（手駒ドロップ防止）
  useEffect(() => {
    if (!running) return;
    const next = maintainTargets(board);
    if (next !== board) setBoard(next);
    // 手駒が増えていたら消す
    if (hands?.b && Object.keys(hands.b).length) setHands(emptyHands);
    if (hands?.w && Object.keys(hands.w).length) setHands(emptyHands);
  }, [board, running, maintainTargets, hands, emptyHands]);

  // 「駒損」判定：指した後に自駒が相手の利きに入っていたら減点＆初期位置へ戻す
  const applyLossIfUnsafe = useCallback(
    (b: BoardMatrix) => {
      const playerSq = findPlayerSq(b, playerSide, playerPiece);
      if (!playerSq) return b;

      const enemyAttack = collectAttackSet(b, enemySide);
      if (!enemyAttack.has(key(playerSq))) return b;

      const penalty = pieceScore(playerPiece);
      setLoss((v) => v + penalty);

      showToast({
        title: `駒損！ -${penalty}`,
        description: `その位置は相手の利きの中（${PIECE_LABEL[playerPiece]}が取られる扱い）`,
      });

      // 自駒を初期位置へ戻す（盤上の自駒を消して置き直し）
      let nb = b;
      nb = set(nb, playerSq, null);
      nb = set(nb, playerStart, toOwnerCode(playerPiece, playerSide));

      return nb;
    },
    [enemySide, playerPiece, playerSide, playerStart],
  );

  const handleMove = useCallback(
    (move: { from?: Sq; to: Sq; piece: string; drop?: boolean }) => {
      if (!running) return;

      // ドロップは禁止
      if (move.drop || !move.from) {
        showToast({ title: "操作不可", description: "この練習では駒を打てません。" });
        // 即復元
        const snap = lastGoodRef.current;
        setBoard(snap.board);
        setHands(snap.hands);
        return;
      }

      // 動かす駒が自分側かチェック（enemyを動かしたら戻す）
      const before = lastGoodRef.current.board;
      const fromPc = get(before, move.from);
      if (!fromPc || ownerOf(fromPc) !== playerSide || baseOf(fromPc) !== playerPiece) {
        showToast({ title: "操作不可", description: "自分の練習駒だけ動かしてください。" });
        const snap = lastGoodRef.current;
        setBoard(snap.board);
        setHands(snap.hands);
        return;
      }

      // 取った駒（move.to の元の駒）を判定して駒得加点
      const captured = get(before, move.to);
      if (captured && ownerOf(captured) === enemySide) {
        const base = baseOf(captured);
        const add = pieceScore(base);
        setGain((v) => v + add);
        setCaptures((v) => v + 1);

        showToast({ title: `駒得！ +${add}`, description: `${PIECE_LABEL[base]}を取った` });
      }

      // ※盤面自体は ShogiBoard が onBoardChange で更新してくれる前提
      // 次のレンダーで useEffect が補充する

      // ちょっと遅延して「駒損」判定（boardが更新された後に見る）
      setTimeout(() => {
        setBoard((b) => applyLossIfUnsafe(b));
      }, 0);
    },
    [running, playerPiece, playerSide, enemySide, applyLossIfUnsafe],
  );

  const start = useCallback(() => {
    // 始める前にターゲット補充
    setBoard((b) => maintainTargets(b));
    setHands(emptyHands);
    setGain(0);
    setLoss(0);
    setCaptures(0);
    setSecLeft(durationSec);
    setRunning(true);
  }, [durationSec, emptyHands, maintainTargets]);

  const header = (
    <div className="flex items-center gap-2 text-sm">
      <span className="font-bold">Time</span>
      <span className={secLeft <= 10 && running ? "font-extrabold text-red-600" : "font-bold"}>
        {secLeft}s
      </span>
      <span className="mx-2 text-slate-300">|</span>
      <span className="font-bold">駒得</span>
      <span className="font-bold text-emerald-700">{gain}</span>
      <span className="font-bold ml-2">駒損</span>
      <span className="font-bold text-rose-700">{loss}</span>
      <span className="font-bold ml-2">Net</span>
      <span className="font-extrabold">{gain - loss}</span>
    </div>
  );

  return (
    <div className="w-full h-full">
      <div className="flex items-center justify-between gap-2 mb-2">
        {header}
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
        onBoardChange={setBoard}
        onHandsChange={setHands}
        orientation="sente"
      />

      {!running && secLeft !== durationSec && (
        <div className="mt-3 rounded-2xl border bg-white/80 p-3">
          <div className="font-bold">Result</div>
          <div className="text-sm text-slate-700 mt-1">
            Net <span className="font-extrabold">{gain - loss}</span>（駒得 {gain} / 駒損 {loss}） / Capture {captures}
          </div>
        </div>
      )}
    </div>
  );
}
