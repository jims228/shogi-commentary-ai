"use client";
import React from "react";

export default function StreakBar({ value }: { value: number }) {
  return (
    <div className={`flex items-center gap-2 ${value > 0 ? 'animate-pulse' : ''}`}>
      <span className="text-shogi-gold text-lg drop-shadow-md">🔥</span>
      <span className="text-sm font-bold text-shogi-gold">{value}</span>
    </div>
  );
}
