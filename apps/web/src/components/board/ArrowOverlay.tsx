"use client";

/**
 * ArrowOverlay — 盤面に矢印を重ねて描画する SVG オーバーレイ。
 *
 * ★ 設計方針
 *   - wrapper : position:absolute; inset:0; width:100%; height:100%
 *     → 親 (relative) のサイズに完全追従。固定 px / boardSize 依存なし。
 *   - svg     : viewBox="0 0 9 9", preserveAspectRatio="none"
 *     → 実ピクセルサイズに自動スケール。width/height 属性は置かない。
 *   - 座標     : arrowEndpoints() が返す 0..9 のマス座標をそのまま使用。
 *                px 計算・vectorEffect="non-scaling-stroke" は一切使わない。
 *   - stroke   : style.color を直接指定。CSS の text-* には依存しない。
 *   - marker   : markerUnits="userSpaceOnUse" + headSize (マス単位) で
 *                矢尻が盤サイズと一緒に自然にスケールする。
 */

import React, { useId, useMemo, useRef } from "react";
import {
  type Arrow,
  type ArrowStyle,
  DEFAULT_ARROW_STYLE,
  REF_BOARD_CELLS,
  arrowEndpoints,
  mergeStyle,
} from "@/lib/arrowGeometry";

// re-export for convenience
export type { Arrow, ArrowStyle } from "@/lib/arrowGeometry";

// ─── Props ───────────────────────────────────────────────────────────────────

type Props = {
  /** 表示する矢印の配列 */
  arrows: Arrow[];
  /** 全矢印に適用するデフォルトスタイル（個別 arrow.style で上書き可） */
  defaultStyle?: ArrowStyle;
  /** 追加 CSS クラス（z-index 等の配置調整用） */
  className?: string;
};

// ─── Component ───────────────────────────────────────────────────────────────

export default function ArrowOverlay({
  arrows,
  defaultStyle,
  className,
}: Props) {
  const rid = useId();
  const svgRef = useRef<SVGSVGElement>(null);

  const base = useMemo(
    () => mergeStyle(DEFAULT_ARROW_STYLE, defaultStyle),
    [defaultStyle],
  );

  // フックはすべて無条件に呼び出し済み → ここで早期リターン可
  if (arrows.length === 0) return null;

  return (
    <div
      data-testid="arrow-overlay"
      className={[
        // 固定 px を使わず、親 (relative な wrapper) に 100% 追従
        "pointer-events-none absolute inset-0 w-full h-full",
        className ?? "",
      ]
        .join(" ")
        .trim()}
      aria-hidden="true"
    >
      {/*
       * ★ svg 要件
       *   - viewBox="0 0 9 9" : マス単位座標系
       *   - preserveAspectRatio="none" : 縦横独立にストレッチ
       *   - width/height="100%" + className で w-full h-full : 親 div に追従
       *   - overflow="visible" : 盤端の矢尻がクリップされないよう
       *   - 不可視 anchor rect : ブラウザの viewBox 座標変換を確実に確立
       */}
      <svg
        ref={svgRef}
        data-testid="arrow-overlay-svg"
        viewBox={`0 0 ${REF_BOARD_CELLS} ${REF_BOARD_CELLS}`}
        preserveAspectRatio="none"
        width="100%"
        height="100%"
        className="absolute inset-0 w-full h-full"
        overflow="visible"
      >
        {/* 不可視アンカー: viewBox 全域(0,0〜9,9)を確実に確立する */}
        <rect x="0" y="0" width={REF_BOARD_CELLS} height={REF_BOARD_CELLS} fill="white" fillOpacity="0.002" />

        <defs>
          {/*
           * 矢印ごとに専用 marker（矢尻）を生成。
           * markerUnits="userSpaceOnUse" + headSize（マス単位）のため、
           * SVG がスケールすると矢尻も比例して大きくなる。
           * vectorEffect は使わない。
           */}
          {arrows.map((a) => {
            const s = mergeStyle(base, a.style);
            const mid = mkMarkerId(rid, a.id);
            return (
              <marker
                key={mid}
                id={mid}
                markerUnits="userSpaceOnUse"
                markerWidth={s.headSize}
                markerHeight={s.headSize}
                refX={s.headSize * 0.4}
                refY={s.headSize / 2}
                orient="auto"
              >
                <path
                  d={`M0,0 L${s.headSize},${s.headSize / 2} L0,${s.headSize} z`}
                  fill={s.color}
                />
              </marker>
            );
          })}

          <style>{`
            @keyframes arrowDash {
              to { stroke-dashoffset: -0.72; }
            }
            .arrowLine--animated {
              animation: arrowDash 1.2s linear infinite;
            }
            @media (prefers-reduced-motion: reduce) {
              .arrowLine--animated { animation: none; }
            }
          `}</style>
        </defs>

        {arrows.map((a, idx) => {
          const s = mergeStyle(base, a.style);
          // ep.x1,y1,x2,y2 はすべて 0..9 のマス座標（px 計算なし）
          const ep = arrowEndpoints(a.from, a.to, s);
          const mid = mkMarkerId(rid, a.id);

          // from と to が同一マスなら描画しない
          if (
            Math.abs(ep.x1 - ep.x2) < 1e-3 &&
            Math.abs(ep.y1 - ep.y2) < 1e-3
          ) {
            return null;
          }

          return (
            <line
              key={a.id}
              data-testid="arrow-line"
                x1={ep.x1}
                y1={ep.y1}
                x2={ep.x2}
                y2={ep.y2}
                // stroke/fill は style.color を直接使用（CSS text-* 非依存）
                stroke={s.color}
                strokeWidth={s.strokeWidth}
                opacity={s.opacity}
                strokeLinecap="round"
                strokeDasharray={s.dashArray || undefined}
                markerEnd={`url(#${mid})`}
                className={s.animated ? "arrowLine--animated" : undefined}
            />
          );
        })}
      </svg>
    </div>
  );
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function mkMarkerId(reactId: string, arrowId: string): string {
  // useId が返す ":r0:" 形式の : をエスケープして CSS/SVG セーフな ID に
  return `arrowMk-${reactId.replace(/[:]/g, "")}-${arrowId}`;
}
