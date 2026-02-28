"use client";
import React from "react";

export default function XPBar({ value, max = 1000 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  return (
    <div className="w-48">
      <div className="text-xs mb-1 font-bold text-shogi-gold">XP {value}/{max}</div>
      <div className="w-full h-3 bg-black/30 rounded-full overflow-hidden border border-white/10">
        <div className="h-3 bg-shogi-gold shadow-[0_0_10px_rgba(212,175,55,0.5)]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
