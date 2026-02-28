"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { ROOK_IKKEN_RYU_L1 } from "@/lessons/rook/ikken-ryu";

export default function Tesuji_ROOK_IKKEN_RYU_Page() {
  return (
    <LessonRunner
      title="一間龍（Lv1）"
      backHref="/learn/roadmap"
      steps={ROOK_IKKEN_RYU_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
