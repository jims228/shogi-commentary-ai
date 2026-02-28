"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_TSUGIFU_LESSON_V2 } from "@/lessons/pawn/tsugifu";

export default function Tesuji_PAWN_TSUGIFU_Page() {
  return (
    <LessonRunner
      title="継ぎ歩（Lv1）"
      backHref="/learn/roadmap"
      steps={PAWN_TSUGIFU_LESSON_V2}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
