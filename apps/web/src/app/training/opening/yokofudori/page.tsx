"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { OPENING_YOKOFUDORI_L1 } from "@/lessons/opening/yokofudori";

export default function Opening_YOKOFUDORI_Page() {
  return (
    <LessonRunner
      title="横歩取り（Lv1）"
      backHref="/learn/roadmap"
      steps={OPENING_YOKOFUDORI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
