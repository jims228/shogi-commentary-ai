"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_NAKAZUMAI_L1 } from "@/lessons/castle/nakazumai";

export default function Castle_NAKAZUMAI_Page() {
  return (
    <LessonRunner
      title="中住まい（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_NAKAZUMAI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
