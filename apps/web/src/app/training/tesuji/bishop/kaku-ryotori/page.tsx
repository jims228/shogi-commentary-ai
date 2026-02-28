"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { BISHOP_KAKU_RYOTORI_L1 } from "@/lessons/bishop/kaku-ryotori";

export default function Tesuji_BISHOP_KAKU_RYOTORI_Page() {
  return (
    <LessonRunner
      title="角での両取り（Lv1）"
      backHref="/learn/roadmap"
      steps={BISHOP_KAKU_RYOTORI_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
