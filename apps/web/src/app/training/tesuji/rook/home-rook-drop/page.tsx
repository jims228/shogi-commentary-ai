"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { ROOK_HOME_ROOK_DROP_L1 } from "@/lessons/rook/home-rook-drop";

export default function Tesuji_ROOK_HOME_ROOK_DROP_Page() {
  return (
    <LessonRunner
      title="自陣への飛車打ち（Lv1）"
      backHref="/learn/roadmap"
      steps={ROOK_HOME_ROOK_DROP_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
