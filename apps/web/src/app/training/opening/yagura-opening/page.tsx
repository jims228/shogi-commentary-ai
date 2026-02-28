"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { OPENING_YAGURA_OPENING_L1 } from "@/lessons/opening/yagura-opening";

export default function Opening_YAGURA_OPENING_Page() {
  return (
    <LessonRunner
      title="矢倉（戦法）（Lv1）"
      backHref="/learn/roadmap"
      steps={OPENING_YAGURA_OPENING_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
