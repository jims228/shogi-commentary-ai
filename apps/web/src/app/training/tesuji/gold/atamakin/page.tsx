"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { GOLD_ATAMAKIN_L1 } from "@/lessons/gold/atamakin";

export default function TesujiGoldAtamakinPage() {
  return (
    <LessonRunner
      title="頭金（Lv1）"
      backHref="/learn/roadmap"
      steps={GOLD_ATAMAKIN_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


