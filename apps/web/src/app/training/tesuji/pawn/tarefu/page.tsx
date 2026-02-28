"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_TAREFU_L1 } from "@/lessons/pawn/tarefu";

export default function TesujiPawnTarefuPage() {
  return (
    <LessonRunner
      title="垂れ歩（Lv1）"
      backHref="/learn/roadmap"
      steps={PAWN_TAREFU_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


