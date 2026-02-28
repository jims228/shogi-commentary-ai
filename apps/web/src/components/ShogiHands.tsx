"use client";

import React from "react";
import { PieceSprite, type OrientationMode } from "@/components/PieceSprite";
import type { PieceBase, PieceCode } from "@/lib/sfen";
import type { HandsState } from "@/lib/board";

const HAND_ORDER: PieceBase[] = ["P", "L", "N", "S", "G", "B", "R", "K"];

const HAND_CELL_SIZE = 40;
const HAND_PIECE_SIZE = 39;

type Props = {
  hands: HandsState;
  viewerSide: "sente" | "gote";
  orientationMode?: OrientationMode;
  layout: "stack" | "corners";
  className?: string;
};

export function ShogiHands({
  hands,
  viewerSide,
  orientationMode = "sprite",
  layout,
  className,
}: Props) {
  const topHandSide = viewerSide === "sente" ? "w" : "b";
  const bottomHandSide = viewerSide === "sente" ? "b" : "w";

  if (layout === "stack") {
    return (
      <div className={className}>
        <HandRow
          side={topHandSide}
          hands={hands[topHandSide]}
          viewerSide={viewerSide}
          orientationMode={orientationMode}
        />
        <div className="h-2" />
        <HandRow
          side={bottomHandSide}
          hands={hands[bottomHandSide]}
          viewerSide={viewerSide}
          orientationMode={orientationMode}
        />
      </div>
    );
  }

  // corners: 相手=左上 / 自分=右下
  return (
    <div className={className}>
      <div className="absolute left-0 top-0 pointer-events-none">
        <HandRow
          side={topHandSide}
          hands={hands[topHandSide]}
          viewerSide={viewerSide}
          orientationMode={orientationMode}
          compact
        />
      </div>

      <div className="absolute right-0 bottom-0 pointer-events-none">
        <HandRow
          side={bottomHandSide}
          hands={hands[bottomHandSide]}
          viewerSide={viewerSide}
          orientationMode={orientationMode}
          compact
        />
      </div>
    </div>
  );
}

function HandRow({
  side,
  hands,
  viewerSide,
  orientationMode,
  compact = false,
}: {
  side: "b" | "w";
  hands?: Partial<Record<PieceBase, number>>;
  viewerSide: "sente" | "gote";
  orientationMode: OrientationMode;
  compact?: boolean;
}) {
  const owner = side === "b" ? "sente" : "gote";
  const label = owner === "sente" ? "先手の持ち駒" : "後手の持ち駒";

  const items = HAND_ORDER.map((base) => {
    const count = hands?.[base];
    if (!count) return null;

    const piece = (side === "b" ? base : base.toLowerCase()) as PieceCode;

    return (
      <div
        key={`${side}-${base}`}
        className="relative"
        style={{ width: HAND_CELL_SIZE, height: HAND_CELL_SIZE }}
        data-testid={base === "P" ? `hand-piece-${owner}-P` : undefined}
      >
        <PieceSprite
          piece={piece}
          x={0}
          y={0}
          size={HAND_PIECE_SIZE}
          cellSize={HAND_CELL_SIZE}
          orientationMode={orientationMode}
          owner={owner}
          viewerSide={viewerSide}
        />
        {count > 1 && (
          <span className="absolute -top-1 -right-1 rounded-full bg-[#fef1d6] px-1 text-xs font-semibold text-[#2b2b2b] border border-black/10">
            {count}
          </span>
        )}
      </div>
    );
  }).filter(Boolean) as React.ReactNode[];

  return (
    <div className="flex flex-col items-start gap-1">
      {!compact && <span className="text-xs font-semibold text-[#5d4037]">{label}</span>}
      <div className="flex items-center gap-2">
        {items.length ? items : <span className="text-xs text-slate-500">--</span>}
      </div>
    </div>
  );
}
