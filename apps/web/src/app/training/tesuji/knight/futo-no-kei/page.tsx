"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { KNIGHT_FUTO_NO_KEI_L1 } from "@/lessons/knight/futo-no-kei";

export default function Tesuji_KNIGHT_FUTO_NO_KEI_Page() {
  return (
    <LessonRunner
      title="歩頭の桂（Lv1）"
      backHref="/learn/roadmap"
      steps={KNIGHT_FUTO_NO_KEI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
