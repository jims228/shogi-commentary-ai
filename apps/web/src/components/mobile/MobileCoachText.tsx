"use client";

import React from "react";

export function MobileCoachText({
  tag,
  text,
  isCorrect,
  correctText = "正解！次へ進もう。",
}: {
  tag: string;
  text: string;
  isCorrect?: boolean;
  correctText?: string;
}) {
  return (
    <div className="text-[22px] leading-snug font-semibold text-slate-900">
      <div className="text-[13px] font-extrabold tracking-wide text-rose-600/90">{tag}</div>
      <div className="mt-1 whitespace-pre-wrap text-slate-900">{text}</div>
      {isCorrect ? (
        <div className="mt-2 rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-[16px] font-extrabold text-emerald-800">
          {correctText}
        </div>
      ) : null}
    </div>
  );
}

