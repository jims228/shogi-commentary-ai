"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { LANCE_DENGAKU_SASHI_L1 } from "@/lessons/lance/dengaku-sashi";

export default function Tesuji_LANCE_DENGAKU_SASHI_Page() {
  return (
    <LessonRunner
      title="田楽刺し（Lv1）"
      backHref="/learn/roadmap"
      steps={LANCE_DENGAKU_SASHI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
