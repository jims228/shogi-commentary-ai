import React from "react";
import { motion } from "framer-motion";
import type { PieceCode } from "@/lib/sfen";

const TILE_SIZE = 130;
const COLS = 8;
const ROWS = 4;
const SPRITE_URL = "/images/pieces.png";

// pieces.png layout (130px tiles, 8 cols × 4 rows)
//   row 0: viewer-side unpromoted   [P, L, N, S, G, B, R, K]
//   row 1: viewer-side promoted     [+P, +L, +N, +S, +B, +R, (col6), (col7)]
//   row 2: opponent-side unpromoted / row 3: opponent-side promoted
// offsetX: タイル内で駒を右にずらす量(px)。正で右。offsetY: タイル内で駒を上にずらす量(px)。正で上。
type SpriteEntry = { row: 0 | 1; col: number; offsetX?: number; offsetY?: number };
const spriteMap: Record<string, SpriteEntry> = {
  P: { row: 0, col: 0, offsetX: -5, offsetY: 0 },
  L: { row: 0, col: 1, offsetX: -3, offsetY: 0 },
  N: { row: 0, col: 2, offsetX: 1, offsetY: 0 },
  S: { row: 0, col: 3, offsetX: -2, offsetY: 0 },
  G: { row: 0, col: 4, offsetX: -4, offsetY: 0 },
  B: { row: 0, col: 5, offsetX: -2, offsetY: 0 },
  R: { row: 0, col: 6, offsetX: -2, offsetY: 0 },
  K: { row: 0, col: 7, offsetX: -1, offsetY: 0 },
  "+P": { row: 1, col: 0, offsetX: -5, offsetY: 0 },
  "+L": { row: 1, col: 1, offsetX: -3, offsetY: 0 },
  "+N": { row: 1, col: 2, offsetX: 1, offsetY: 0 },
  "+S": { row: 1, col: 3, offsetX: -2, offsetY: 0 },
  "+B": { row: 1, col: 5, offsetX: -2, offsetY: 0 },  // 馬 (角成) = col 5
  "+R": { row: 1, col: 6, offsetX: -2, offsetY: 0 },  // 龍 (飛成) = col 6
};

const PLAYER_ROW_OFFSET: Record<"player" | "opponent", 0 | 2> = {
  player: 0,
  opponent: 2,
};

export type OrientationMode = "rotate" | "sprite";

export type PieceMotionConfig = {
  type: "shake-x";
  /** 1サイクルの横ブレ幅(px) */
  amplitudePx?: number;
  /** 1サイクル時間(ms) */
  durationMs?: number;
  /** 開始までの遅延(ms) */
  delayMs?: number;
  /** 繰り返し回数。"infinite" で無限 */
  repeat?: number | "infinite";
};

interface PieceSpriteProps {
  piece: PieceCode;
  x: number;
  y: number;
  size?: number;        // actual sprite size
  cellSize?: number;    // board cell size
  offsetX?: number;     // board left offset
  offsetY?: number;     // board top offset
  /** 縦方向の追加オフセット（px）。自分側・相手側で別々に指定可能 */
  shiftY?: number;
  owner?: "sente" | "gote";
  orientationMode?: OrientationMode;
  viewerSide?: "sente" | "gote";
  className?: string;
  style?: React.CSSProperties;
  /** mobile-only flicker hardening hook (data attribute) */
  dataShogiPiece?: string;
  /** board overlay alignment aid (optional data attributes) */
  dataBoardDisplayX?: number;
  /** board overlay alignment aid (optional data attributes) */
  dataBoardDisplayY?: number;
  /** Extra CSS scale applied on top of the translate (e.g. 1.12 for selected pieces) */
  scaleMultiplier?: number;
  /** Optional motion effect for future reusable piece animations */
  motionConfig?: PieceMotionConfig;
}

export const PieceSprite: React.FC<PieceSpriteProps> = ({
  piece,
  x,
  y,
  size,
  cellSize,
  offsetX = 0,
  offsetY = 0,
  shiftY = 0,
  owner,
  orientationMode: orientationModeProp = "sprite",
  viewerSide = "sente",
  className,
  style,
  dataShogiPiece,
  dataBoardDisplayX,
  dataBoardDisplayY,
  scaleMultiplier,
  motionConfig,
}) => {
  const pieceSize = size ?? 46;
  const cell = cellSize ?? pieceSize;
  const originX = offsetX ?? 0;
  const originY = offsetY ?? 0;

  const isPromoted = piece.startsWith("+");
  const baseChar = isPromoted ? piece[1] : piece[0];
  const resolvedOwner = owner ?? (baseChar === baseChar.toUpperCase() ? "sente" : "gote");
  const isViewerPiece = resolvedOwner === viewerSide;
  const orientationMode = orientationModeProp;

  const norm = isPromoted ? `+${baseChar.toUpperCase()}` : baseChar.toUpperCase();
  const fallbackKey = baseChar.toUpperCase();
  const entry = spriteMap[norm] ?? spriteMap[fallbackKey] ?? spriteMap["P"];
  const { row: baseRow, col, offsetX: tileOffsetX = 0, offsetY: tileOffsetY = 0 } = entry;
  const rowOffsetKey = orientationMode === "sprite" ? (isViewerPiece ? "player" : "opponent") : "player";
  const spriteRow = baseRow + PLAYER_ROW_OFFSET[rowOffsetKey];

  const scale = pieceSize / TILE_SIZE;
  const bgWidth = COLS * TILE_SIZE * scale;
  const bgHeight = ROWS * TILE_SIZE * scale;
  const bgPosX = (-col * TILE_SIZE - tileOffsetX) * scale;
  const bgPosY = (-spriteRow * TILE_SIZE - tileOffsetY) * scale;

  const left = originX + x * cell + (cell - pieceSize) / 2;
  const top = originY + y * cell + (cell - pieceSize) / 2 + shiftY;

  const shouldRotate = orientationMode === "rotate" && !isViewerPiece;
  const baseTransform = shouldRotate ? " rotate(180deg)" : "";
  const scaleStr = scaleMultiplier && scaleMultiplier !== 1 ? ` scale(${scaleMultiplier})` : "";

  const shakeAmplitude = motionConfig?.type === "shake-x" ? (motionConfig.amplitudePx ?? 2.4) : 0;
  const shakeDurationSec = motionConfig?.type === "shake-x" ? ((motionConfig.durationMs ?? 120) / 1000) : 0;
  const shakeDelaySec = motionConfig?.type === "shake-x" ? ((motionConfig.delayMs ?? 0) / 1000) : 0;
  const shakeRepeat = motionConfig?.type === "shake-x"
    ? (motionConfig.repeat === "infinite" || motionConfig.repeat == null ? Infinity : motionConfig.repeat)
    : 0;

  return (
    <div
      data-shogi-piece={dataShogiPiece}
      data-board-display-x={typeof dataBoardDisplayX === "number" ? dataBoardDisplayX : undefined}
      data-board-display-y={typeof dataBoardDisplayY === "number" ? dataBoardDisplayY : undefined}
      className={className}
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        pointerEvents: "none",
        transform: `translate3d(${left}px, ${top}px, 0)`,
        transformOrigin: "50% 50%",
        ...style,
      }}
    >
      <div
        style={{
          width: pieceSize,
          height: pieceSize,
          transform: `${baseTransform}${scaleStr}`,
          transformOrigin: "50% 50%",
        }}
      >
        <motion.div
          // Disable mount animation to prevent brief flicker on Android WebView.
          initial={false}
          animate={
            motionConfig?.type === "shake-x"
              ? { x: [0, -shakeAmplitude, shakeAmplitude, -shakeAmplitude, shakeAmplitude, 0] }
              : { x: 0 }
          }
          transition={
            motionConfig?.type === "shake-x"
              ? {
                  duration: shakeDurationSec,
                  delay: shakeDelaySec,
                  ease: "linear",
                  repeat: shakeRepeat,
                }
              : undefined
          }
          style={{
            width: pieceSize,
            height: pieceSize,
            backgroundImage: `url(${SPRITE_URL})`,
            backgroundRepeat: "no-repeat",
            backgroundSize: `${bgWidth}px ${bgHeight}px`,
            backgroundPosition: `${bgPosX}px ${bgPosY}px`,
          }}
        />
      </div>
    </div>
  );
};
