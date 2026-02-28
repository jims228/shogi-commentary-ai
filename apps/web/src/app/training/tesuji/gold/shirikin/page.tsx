"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { GOLD_SHIRIKIN_L1 } from "@/lessons/gold/shirikin";

export default function TesujiGoldShirikinPage() {
  return (
    <LessonRunner
      title="尻金（Lv1）"
      backHref="/learn/roadmap"
      steps={GOLD_SHIRIKIN_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


