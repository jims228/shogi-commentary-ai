"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { LANCE__2DAN_ROCKET_L1 } from "@/lessons/lance/2dan-rocket";

export default function Tesuji_LANCE__2DAN_ROCKET_Page() {
  return (
    <LessonRunner
      title="2段ロケット（Lv1）"
      backHref="/learn/roadmap"
      steps={LANCE__2DAN_ROCKET_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
