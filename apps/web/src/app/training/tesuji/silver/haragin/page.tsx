"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { SILVER_HARAGIN_L1 } from "@/lessons/silver/haragin";

export default function TesujiSilverHaraginPage() {
  return (
    <LessonRunner
      title="腹銀（Lv1）"
      backHref="/learn/roadmap"
      steps={SILVER_HARAGIN_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


