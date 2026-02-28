"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_HIDARI_MINO_L1 } from "@/lessons/castle/hidari-mino";

export default function Castle_HIDARI_MINO_Page() {
  return (
    <LessonRunner
      title="左美濃（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_HIDARI_MINO_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
