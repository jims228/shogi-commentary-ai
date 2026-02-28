"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { LANCE_SOKOKYO_L1 } from "@/lessons/lance/sokokyo";

export default function Tesuji_LANCE_SOKOKYO_Page() {
  return (
    <LessonRunner
      title="底香（Lv1）"
      backHref="/learn/roadmap"
      steps={LANCE_SOKOKYO_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
