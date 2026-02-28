"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { SILVER_WARIUCHI_L1 } from "@/lessons/silver/warigin";

export default function TesujiSilverWariuchiPage() {
  return (
    <LessonRunner
      title="割打ちの銀（Lv1）"
      backHref="/learn/roadmap"
      steps={SILVER_WARIUCHI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


