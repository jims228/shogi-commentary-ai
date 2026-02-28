"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { ROOK_JUJI_HISHA_L1 } from "@/lessons/rook/juji-hisha";

export default function Tesuji_ROOK_JUJI_HISHA_Page() {
  return (
    <LessonRunner
      title="十字飛車（Lv1）"
      backHref="/learn/roadmap"
      steps={ROOK_JUJI_HISHA_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
