"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { PAWN_HIKAE_L1 } from "@/lessons/pawn/hikae";

export default function TesujiPawnHikaePage() {
  return (
    <LessonRunner
      title="控えの歩（Lv1）"
      backHref="/learn/roadmap"
      steps={PAWN_HIKAE_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}


