"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { OPENING_NAKABISHA_L1 } from "@/lessons/opening/nakabisha";

export default function Opening_NAKABISHA_Page() {
  return (
    <LessonRunner
      title="中飛車（Lv1）"
      backHref="/learn/roadmap"
      steps={OPENING_NAKABISHA_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
