"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_TSUGIFU_LESSON_V2 } from "@/lessons/pawn/tsugifu";

export default function TsugifuTrainingPage() {
  return (
    <LessonRunner
      title="継ぎ歩（復習）"
      backHref="/learn/roadmap"
      steps={PAWN_TSUGIFU_LESSON_V2}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
      reserveMobileCtaSpace
      mobileExplanationHeightPx={210}
    />
  );
}
