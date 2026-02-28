"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_FUNAGAKOI_L1 } from "@/lessons/castle/funagakoi";

export default function Castle_FUNAGAKOI_Page() {
  return (
    <LessonRunner
      title="舟囲い（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_FUNAGAKOI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
