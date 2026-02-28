"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { ROOK_OKURI_L1 } from "@/lessons/rook/okuri";

export default function Tesuji_ROOK_OKURI_Page() {
  return (
    <LessonRunner
      title="送りの手筋（Lv1）"
      backHref="/learn/roadmap"
      steps={ROOK_OKURI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
