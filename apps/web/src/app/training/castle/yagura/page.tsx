"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_YAGURA_L1 } from "@/lessons/castle/yagura";

export default function Castle_YAGURA_Page() {
  return (
    <LessonRunner
      title="矢倉（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_YAGURA_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
