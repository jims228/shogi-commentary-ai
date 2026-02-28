"use client";

import React from "react";
import { useMobileQueryParam } from "@/hooks/useMobileQueryParam";

export default function PawnBasicsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const isMobile = useMobileQueryParam();

  React.useEffect(() => {
    if (isMobile) {
      // Keep UI minimal for WebView, but log full error for root-cause investigation.
      // eslint-disable-next-line no-console
      console.error("[pawn/mobile] error boundary:", error);
    }
  }, [error, isMobile]);

  if (isMobile) {
    return (
      <div className="h-[100dvh] overflow-hidden flex flex-col items-center justify-center px-5 text-center text-amber-50"
        style={{ background: "linear-gradient(180deg, #3f2a20 0%, #281a12 100%)" }}
      >
        <div className="text-lg font-extrabold">読み込みに失敗しました</div>
        <div className="mt-2 text-sm opacity-90">一度リロードしてもう一度お試しください。</div>
        <button
          className="mt-4 px-4 py-2 rounded-xl bg-emerald-600 text-white font-extrabold active:scale-95"
          onClick={() => reset()}
        >
          リロード
        </button>
        <div className="mt-3 text-[11px] opacity-70 break-all">
          {error?.digest ? `digest: ${error.digest}` : null}
        </div>
      </div>
    );
  }

  return (
    <div className="p-10">
      <h2 className="text-xl font-bold">Something went wrong</h2>
      <pre className="mt-4 text-sm whitespace-pre-wrap">{String(error?.message ?? error)}</pre>
      <button className="mt-6 px-4 py-2 rounded bg-black text-white" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}


