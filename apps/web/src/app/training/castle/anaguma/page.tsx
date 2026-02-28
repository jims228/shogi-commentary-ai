"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_ANAGUMA_L1 } from "@/lessons/castle/anaguma";

export default function Castle_ANAGUMA_Page() {
  return (
    <LessonRunner
      title="穴熊（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_ANAGUMA_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
