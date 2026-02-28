"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_SOKOBU_L1 } from "@/lessons/pawn/sokobu";

export default function TesujiPawnSokobuPage() {
  return (
    <LessonRunner
      title="底歩（Lv1）"
      backHref="/learn/roadmap"
      steps={PAWN_SOKOBU_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


