"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { KNIGHT_HIKAE_KEI_L1 } from "@/lessons/knight/hikae-kei";

export default function Tesuji_KNIGHT_HIKAE_KEI_Page() {
  return (
    <LessonRunner
      title="控えの桂（Lv1）"
      backHref="/learn/roadmap"
      steps={KNIGHT_HIKAE_KEI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
