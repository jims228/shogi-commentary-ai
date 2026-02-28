"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_MINO_L1 } from "@/lessons/castle/mino";

export default function Castle_MINO_Page() {
  return (
    <LessonRunner
      title="美濃囲い（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_MINO_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
