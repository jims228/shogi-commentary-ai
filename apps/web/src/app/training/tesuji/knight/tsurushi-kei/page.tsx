"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { KNIGHT_TSURUSHI_KEI_L1 } from "@/lessons/knight/tsurushi-kei";

export default function Tesuji_KNIGHT_TSURUSHI_KEI_Page() {
  return (
    <LessonRunner
      title="つるし桂（Lv1）"
      backHref="/learn/roadmap"
      steps={KNIGHT_TSURUSHI_KEI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
