"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { SILVER_KEITOGIN_L1 } from "@/lessons/silver/keitogin";

export default function TesujiSilverKeitoginPage() {
  return (
    <LessonRunner
      title="桂頭の銀（Lv1）"
      backHref="/learn/roadmap"
      steps={SILVER_KEITOGIN_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


