"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { OPENING_AIGAKARI_L1 } from "@/lessons/opening/aigakari";

export default function Opening_AIGAKARI_Page() {
  return (
    <LessonRunner
      title="相掛かり（Lv1）"
      backHref="/learn/roadmap"
      steps={OPENING_AIGAKARI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
