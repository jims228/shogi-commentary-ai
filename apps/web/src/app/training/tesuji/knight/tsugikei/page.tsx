"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { KNIGHT_TSUGIKEI_L1 } from "@/lessons/knight/tsugikei";

export default function Tesuji_KNIGHT_TSUGIKEI_Page() {
  return (
    <LessonRunner
      title="継ぎ桂（Lv1）"
      backHref="/learn/roadmap"
      steps={KNIGHT_TSUGIKEI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
