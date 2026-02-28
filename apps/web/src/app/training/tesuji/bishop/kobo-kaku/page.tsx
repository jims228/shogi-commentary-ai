"use client";

import React from "react";
import { LessonRunner } from "@/components/training/lesson/LessonRunner";
import { BISHOP_KOBO_KAKU_L1 } from "@/lessons/bishop/kobo-kaku";

export default function Tesuji_BISHOP_KOBO_KAKU_Page() {
  return (
    <LessonRunner
      title="攻防の角（Lv1）"
      backHref="/learn/roadmap"
      steps={BISHOP_KOBO_KAKU_L1}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      onFinishHref="/learn/roadmap"
    />
  );
}
