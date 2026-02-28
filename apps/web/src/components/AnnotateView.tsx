"use client";

import React from "react";
import { useAnnotate } from "@/lib/annotateHook";
import type { OrientationMode } from "@/components/PieceSprite";
import AnalysisTab from "@/components/annotate/AnalysisTab";

// 棋神アナリティクス風レイアウト
// 検討モードのみ表示

export default function AnnotateView() {
  const { usi, setUsi } = useAnnotate();
  const orientationMode: OrientationMode = "sprite";

  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 min-h-0 overflow-hidden">
        <AnalysisTab usi={usi} setUsi={setUsi} orientationMode={orientationMode} />
      </div>
    </div>
  );
}
