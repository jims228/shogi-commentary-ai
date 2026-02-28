"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { OPENING_SANKENBISHA_L1 } from "@/lessons/opening/sankenbisha";

export default function Opening_SANKENBISHA_Page() {
  return (
    <LessonRunner
      title="三間飛車（Lv1）"
      backHref="/learn/roadmap"
      steps={OPENING_SANKENBISHA_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
