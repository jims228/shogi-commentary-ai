import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_TATAKI_L1 } from "@/lessons/pawn/tataki";

export default function TesujiPawnTatakiPage() {
  return (
    <LessonRunner
      title="叩きの歩（Lv1）"
      backHref="/learn/roadmap"
      steps={PAWN_TATAKI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


