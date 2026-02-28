"use client";

import React from "react";

type Props = {
  mascot: React.ReactNode;
  explanation: React.ReactNode;
  board: React.ReactNode;
  actions?: React.ReactNode;
  explanationHeightPx?: number;
};

/**
 * Mobile-only lesson layout for WebView (Duolingo-ish):
 * - 1 screen (100dvh), no scrolling
 * - top-left: mascot + short explanation
 * - bottom: board maximized
 */
export function MobileLessonShell({ mascot, explanation, board, actions, explanationHeightPx }: Props) {
  const isDev = process.env.NODE_ENV !== "production";

  const debug = (() => {
    if (typeof window === "undefined") return null;
    if (!isDev) return null;
    try {
      const vv = window.visualViewport;
      const html = document.documentElement;
      const body = document.body;
      const htmlFont = window.getComputedStyle(html).fontSize;
      const bodyFont = body ? window.getComputedStyle(body).fontSize : "?";
      return {
        vvScale: vv?.scale ?? null,
        innerW: window.innerWidth,
        htmlClientW: html.clientWidth,
        dpr: window.devicePixelRatio,
        htmlFont,
        bodyFont,
      };
    } catch {
      return null;
    }
  })();

  const showDebug =
    isDev &&
    debug &&
    (() => {
      try {
        const sp = new URLSearchParams(window.location.search);
        return sp.get("debug") === "1";
      } catch {
        return false;
      }
    })();

  return (
    <div
      data-mobile-lesson-shell
      data-mobile="1"
      suppressHydrationWarning
      className="fixed inset-0 h-[100dvh] overflow-hidden flex flex-col bg-white text-slate-900"
      style={{ paddingTop: "calc(env(safe-area-inset-top, 0px) + 4px)" }}
    >
      {showDebug ? (
        <div className="fixed right-2 top-2 z-[99999] pointer-events-none rounded-lg bg-black/70 px-2 py-1 text-[11px] font-mono text-white">
          <div>vv.scale: {String(debug.vvScale)}</div>
          <div>innerW/htmlW: {debug.innerW}/{debug.htmlClientW}</div>
          <div>dpr: {debug.dpr}</div>
          <div>font html/body: {debug.htmlFont}/{debug.bodyFont}</div>
        </div>
      ) : null}

      <div className="shrink-0 px-3 pt-2">
        <div className="flex items-start gap-3">
          <div className="shrink-0 w-[210px] h-[210px] flex items-start justify-start">{mascot}</div>
          <div className="min-w-0 flex-1 pt-1" style={{ marginTop: 120 }}>
            <div
              className="max-h-[210px] overflow-auto pr-1"
              style={{
                width: "calc(100% + 60px)",
                marginLeft: -70,
                height: explanationHeightPx ? `${explanationHeightPx}px` : undefined,
                maxHeight: explanationHeightPx ? `${explanationHeightPx}px` : undefined,
              }}
            >
              {explanation}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 px-1 pb-4 flex flex-col">
        <div className="flex-1 min-h-0 w-full flex items-center justify-center">{board}</div>
        {/* CTA area: pinned with safe area padding for consistent reachability (Duolingo-ish). */}
        {actions ? (
          <div
            className="shrink-0 px-2 pt-2"
            style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 12px)" }}
          >
            {actions}
          </div>
        ) : null}
      </div>
    </div>
  );
}


