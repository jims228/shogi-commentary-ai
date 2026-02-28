"use client";

import React from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useMobileQueryParam } from "@/hooks/useMobileQueryParam";

export type LessonScaffoldProps = {
  title: string;
  backHref: string;
  board: React.ReactNode;
  explanation: React.ReactNode;
  mascot: React.ReactNode;

  // 互換 props
  topLabel?: string;
  progress01?: number; // 0..1
  headerRight?: React.ReactNode;
  desktopMinWidthPx?: number; // default 820
  mobileMascotScale?: number;

  // ★追加：モバイル下部の固定アクション（次へボタンをここに出す）
  mobileAction?: React.ReactNode;
  // mascot そばに出す小さなオーバーレイ（正解メッセージ等）
  mascotOverlay?: React.ReactNode;

  // ★追加：デスクトップのレイアウト
  desktopLayout?: "twoCol" | "threeCol"; // default "twoCol"
};

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

export function LessonScaffold({
  title,
  backHref,
  board,
  explanation,
  mascot,
  topLabel,
  progress01,
  headerRight,
  desktopMinWidthPx = 820,
  mobileMascotScale = 0.78,
  mobileAction,
  mascotOverlay,
  desktopLayout = "twoCol",
}: LessonScaffoldProps) {
  const isDesktop = useMediaQuery(`(min-width: ${desktopMinWidthPx}px)`);
  const isMobileWebView = useMobileQueryParam();
  const p = typeof progress01 === "number" ? clamp01(progress01) : null;

  return (
    <div
      className="min-h-[100svh] w-full overflow-auto bg-[#f6f1e7] text-[#3a2b17]"
      suppressHydrationWarning
    >
      {/* Header (hide in mobile WebView) */}
      {!isMobileWebView ? (
        <div className="h-12 px-3 flex items-center gap-2 border-b border-black/10">
          <Link
            href={backHref}
            className="inline-flex items-center justify-center w-9 h-9 rounded-full hover:bg-black/5 active:scale-95 transition"
            aria-label="Back"
          >
            <ChevronLeft className="w-5 h-5" />
          </Link>

          <div className="flex-1 min-w-0">
            {topLabel ? (
              <div className="text-[11px] font-extrabold tracking-wide text-slate-600">{topLabel}</div>
            ) : null}
            <div className="font-bold truncate">{title}</div>
          </div>

          {headerRight ? <div className="shrink-0 text-[#3a2b17]">{headerRight}</div> : null}
        </div>
      ) : null}

      {/* Content */}
      <div className="h-[calc(100svh-3rem)] min-h-0">
        {isDesktop ? (
          <div className="h-full min-h-0 px-5 py-4">
            {desktopLayout === "threeCol" ? (
              <div
                className="h-full min-h-0 grid gap-5"
                style={{
                  gridTemplateColumns: "minmax(0, 1fr) minmax(300px, 420px) minmax(360px, 520px)",
                }}
              >
                {/* Left: Board */}
                <section className="min-h-0 flex items-center justify-center">
                  <div className="w-full h-full min-h-0">{board}</div>
                </section>

                {/* Middle: Mascot */}
                <section className="min-h-0 relative flex items-center justify-center">
                  {mascotOverlay ? <div className="absolute top-2 left-2 z-10">{mascotOverlay}</div> : null}
                  <div className="w-full h-full min-h-0 flex items-end justify-center">{mascot}</div>
                </section>

                {/* Right: Explanation */}
                <section className="min-h-0 flex flex-col">
                  <div className="min-h-0">{explanation}</div>
                </section>
              </div>
            ) : (
              <div
                className="h-full min-h-0 grid gap-5"
                style={{
                  gridTemplateColumns: "minmax(0, 1fr) minmax(360px, 520px)",
                }}
              >
                <section className="min-h-0 flex items-center justify-center">
                  <div className="w-full h-full min-h-0">{board}</div>
                </section>

                <section className="min-h-0 flex flex-col gap-4">
                  <div className="min-h-0">{explanation}</div>

                  <div className="min-h-0 flex-1 relative flex items-end justify-center">
                    {mascotOverlay ? <div className="absolute top-2 left-2 z-10">{mascotOverlay}</div> : null}
                    {mascot}
                  </div>
                </section>
              </div>
            )}
          </div>
        ) : (
          <div className="h-full min-h-0 px-4 py-3 flex flex-col gap-3">
            <div className="flex-1 min-h-0">{board}</div>

            <div className="min-h-0">{explanation}</div>

            <div className="relative flex items-end justify-center" style={{ transform: `scale(${mobileMascotScale})` }}>
              {mascotOverlay ? <div className="absolute top-2 left-2 z-10">{mascotOverlay}</div> : null}
              {mascot}
            </div>

            {mobileAction ? <div className="pt-2">{mobileAction}</div> : null}
          </div>
        )}
      </div>

      {/* Progress bar (optional) */}
      {p !== null ? (
        <div className="h-2 w-full bg-black/10">
          <div className="h-full bg-emerald-600" style={{ width: `${p * 100}%` }} />
        </div>
      ) : null}
    </div>
  );
}
