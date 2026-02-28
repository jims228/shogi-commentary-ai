"use client";

/**
 * BoardHintsOverlay — ヒントマスの強調 + ドロップ矢印の描画。
 *
 * ★ 盤→盤 の move 矢印は ArrowOverlay に移行済み。
 *    このコンポーネントは hintSquares と drop 矢印のみ担当する。
 */

import React, { useId, useMemo, useEffect, useRef, useState } from "react";

export type HintSquare = { file: number; rank: number };
export type HintArrow = {
  to: HintSquare;
  from?: HintSquare;
  kind?: "move" | "drop";
  dir?: "up" | "down" | "left" | "right" | "hand";
  hand?: "sente" | "gote";
};

type Props = {
  hintSquares?: HintSquare[];
  hintArrows?: HintArrow[];
  coordMode?: "shogi" | "ltr";
  className?: string;
  /** @deprecated boardSize による固定 px は不要になった。props 自体は互換のため残すが無視する */
  boardPxSize?: number;
  flipped?: boolean;
};

// ドロップ矢印の見た目（drop 系のみ — move 系は ArrowOverlay 側で管理）
const DROP_ARROW_STYLE = {
  markerWidth: 0.9,
  markerHeight: 0.9,
  markerRefX: 1,
  markerRefY: 0.5,
  strokeWidth: 0.42,
  strokeOpacity: 1,
  dashArray: "1.0 0.55",
  opacity: 0.98,
} as const;

export default function BoardHintsOverlay({
  hintSquares = [],
  hintArrows = [],
  coordMode = "shogi",
  className,
  boardPxSize: _boardPxSize,  // 互換のため受け取るが使わない
  flipped = false,
}: Props) {
  const rid = useId();
  const markerId = useMemo(() => `hintArrow-${rid.replace(/[:]/g, "")}`, [rid]);
  const hasAnything = hintSquares.length > 0 || hintArrows.length > 0;
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [handMeasureTick, setHandMeasureTick] = useState(0);

  const needsHand = useMemo(
    () => hintArrows.some(a => a.dir === "hand" && (a.kind === "drop" || !a.from)),
    [hintArrows],
  );

  useEffect(() => {
    if (!needsHand) return;
    let n = 0;
    const id = window.setInterval(() => {
      setHandMeasureTick(t => t + 1);
      n++;
      if (n >= 12) window.clearInterval(id);
    }, 100);
    return () => window.clearInterval(id);
  }, [needsHand]);

  if (!hasAnything) return null;

  // ── 座標変換 ──

  const toColRow = (sq: HintSquare) => {
    if (coordMode === "shogi") {
      if (!flipped) {
        return { col: 9 - sq.file, row: sq.rank - 1 };
      }
      return { col: sq.file - 1, row: 9 - sq.rank };
    }
    return { col: sq.file - 1, row: sq.rank - 1 };
  };

  const squareRect = (sq: HintSquare) => {
    const { col, row } = toColRow(sq);
    return { x: col, y: row, w: 1, h: 1 };
  };

  const squareCenter = (sq: HintSquare) => {
    const r = squareRect(sq);
    return { cx: r.x + 0.5, cy: r.y + 0.5 };
  };

  return (
    <div
      ref={wrapperRef}
      data-testid="board-hints-overlay"
      className={[
        // ★ boardPxSize による固定 px を廃止し、親 (containerRef, relative) に 100% 追従
        "pointer-events-none absolute inset-0 w-full h-full",
        className ?? "",
      ].join(" ")}
      aria-hidden="true"
    >
      <svg
        data-testid="board-hints-overlay-svg"
        viewBox="0 0 9 9"
        preserveAspectRatio="none"
        width="100%"
        height="100%"
        className="absolute inset-0 w-full h-full"
        overflow="visible"
      >
        {/* 不可視アンカー: viewBox 全域(0,0〜9,9)を確実に確立する */}
        <rect x="0" y="0" width="9" height="9" fill="white" fillOpacity="0.002" />

        <defs>
          <marker
            id={markerId}
            markerUnits="userSpaceOnUse"
            markerWidth={DROP_ARROW_STYLE.markerWidth}
            markerHeight={DROP_ARROW_STYLE.markerHeight}
            refX={DROP_ARROW_STYLE.markerRefX}
            refY={DROP_ARROW_STYLE.markerRefY}
            orient="auto"
            viewBox="0 0 1 1"
          >
            <path d="M0,0 L1,0.5 L0,1 z" fill="currentColor" />
          </marker>

          <style>{`
            @keyframes hintDash {
              to { stroke-dashoffset: -2.0; }
            }
            .hintArrow { animation: hintDash 1.2s linear infinite; }
            @media (prefers-reduced-motion: reduce) {
              .hintSquare, .hintArrow { animation: none; opacity: .5; }
            }
          `}</style>
        </defs>

        {/* ── ヒントマス ── */}
        {hintSquares.map((sq, i) => {
          const r = squareRect(sq);
          return (
            <rect
              data-testid="hint-square"
              key={`sq-${i}-${sq.file}-${sq.rank}`}
              x={r.x}
              y={r.y}
              width={r.w}
              height={r.h}
              rx={0.12}
              className="hintSquare"
              fill="currentColor"
              opacity={0.18}
            />
          );
        })}

        {/* ── ドロップ矢印（from 無し） ── */}
        {hintArrows.map((a, i) => {
          // from がある矢印は ArrowOverlay が担当するのでスキップ
          if (a.from) return null;

          const t = squareCenter(a.to);

          const handStartFromDom = () => {
            void handMeasureTick;
            const wrap = wrapperRef.current;
            if (!wrap) return null;
            const wrapRect = wrap.getBoundingClientRect();
            const who = a.hand ?? "sente";
            const el = document.querySelector(
              `[data-testid="hand-piece-${who}-P"]`,
            ) as HTMLElement | null;
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const cxPx = r.left + r.width / 2;
            const cyPx = r.top + r.height / 2;
            return {
              cx: ((cxPx - wrapRect.left) / wrapRect.width) * 9,
              cy: ((cyPx - wrapRect.top) / wrapRect.height) * 9,
            };
          };

          const computeStart = () => {
            if (a.dir === "hand") {
              const hs = handStartFromDom();
              if (hs) return hs;
              return { cx: t.cx, cy: flipped ? -0.8 : 9.8 };
            }
            switch (a.dir) {
              case "up":    return { cx: t.cx,       cy: t.cy - 1.2 };
              case "down":  return { cx: t.cx,       cy: t.cy + 1.2 };
              case "left":  return { cx: t.cx - 1.2, cy: t.cy };
              case "right": return { cx: t.cx + 1.2, cy: t.cy };
              default:      return { cx: t.cx,       cy: t.cy + 1.2 };
            }
          };

          const s = computeStart();
          if (Math.abs(s.cx - t.cx) < 1e-6 && Math.abs(s.cy - t.cy) < 1e-6) return null;

          return (
            <line
              data-testid="hint-arrow"
              key={`ar-${i}-drop-${a.to.file}-${a.to.rank}`}
              x1={s.cx}
              y1={s.cy}
              x2={t.cx}
              y2={t.cy}
              className="hintArrow"
              stroke="currentColor"
              strokeWidth={DROP_ARROW_STYLE.strokeWidth}
              strokeOpacity={DROP_ARROW_STYLE.strokeOpacity}
              strokeLinecap="round"
              strokeDasharray={DROP_ARROW_STYLE.dashArray}
              markerEnd={`url(#${markerId})`}
              opacity={DROP_ARROW_STYLE.opacity}
            />
          );
        })}
      </svg>
    </div>
  );
}
