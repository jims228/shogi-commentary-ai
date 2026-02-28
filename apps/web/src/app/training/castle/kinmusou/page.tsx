"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { CASTLE_KINMUSOU_L1 } from "@/lessons/castle/kinmusou";

export default function Castle_KINMUSOU_Page() {
  return (
    <LessonRunner
      title="金無双（Lv1）"
      backHref="/learn/roadmap"
      steps={CASTLE_KINMUSOU_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
