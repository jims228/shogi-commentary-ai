"use client";

import React from "react";

export function MobilePrimaryCTA({
  label = "次へ",
  onClick,
  disabled,
}: {
  label?: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={[
        // Duolingo-ish pill CTA
        "w-full h-[56px] rounded-full font-extrabold text-[18px] tracking-wide",
        "bg-emerald-500 text-white shadow-[0_10px_20px_rgba(0,0,0,0.16)]",
        "border-b-4 border-emerald-700",
        "active:translate-y-[1px] active:border-b-2",
        "disabled:opacity-50 disabled:active:translate-y-0 disabled:active:border-b-4",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

