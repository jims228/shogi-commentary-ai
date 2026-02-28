"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { BISHOP_KAKU_KEI_L1 } from "@/lessons/bishop/kaku-kei";

export default function Tesuji_BISHOP_KAKU_KEI_Page() {
  return (
    <LessonRunner
      title="角桂連携（Lv1）"
      backHref="/learn/roadmap"
      steps={BISHOP_KAKU_KEI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
