"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { BISHOP_SUJI_CHIGAI_L1 } from "@/lessons/bishop/suji-chigai";

export default function Tesuji_BISHOP_SUJI_CHIGAI_Page() {
  return (
    <LessonRunner
      title="筋違いの角打ち（Lv1）"
      backHref="/learn/roadmap"
      steps={BISHOP_SUJI_CHIGAI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
