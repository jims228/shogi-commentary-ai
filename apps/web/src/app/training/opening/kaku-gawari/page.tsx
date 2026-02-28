"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { OPENING_KAKU_GAWARI_L1 } from "@/lessons/opening/kaku-gawari";

export default function Opening_KAKU_GAWARI_Page() {
  return (
    <LessonRunner
      title="角換わり（Lv1）"
      backHref="/learn/roadmap"
      steps={OPENING_KAKU_GAWARI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
