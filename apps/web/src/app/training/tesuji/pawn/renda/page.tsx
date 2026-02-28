"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_RENDA_L1 } from "@/lessons/pawn/renda";

export default function TesujiPawnRendaPage() {
  return (
    <LessonRunner
      title="歩の連打（Lv1）"
      backHref="/learn/roadmap"
      steps={PAWN_RENDA_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


