"use client";

import React from "react";

export type BioshogiSide = {
  attack: string[];
  defense: string[];
  technique: string[];
};

export type BioshogiData = {
  sente: BioshogiSide;
  gote: BioshogiSide;
};

type Props = {
  data: BioshogiData;
};

function SideInfo({ label, side }: { label: string; side: BioshogiSide }) {
  const attack = side.attack[0] ?? "—";
  const defense = side.defense[0] ?? "—";
  const techniques = side.technique;

  return (
    <div className="flex flex-col gap-1">
      <div className="text-xs font-bold text-slate-500">{label}</div>
      <div className="flex flex-wrap gap-2 text-sm">
        <span className="rounded-full bg-blue-100 px-3 py-0.5 text-blue-800 font-medium">
          {attack}
        </span>
        <span className="rounded-full bg-green-100 px-3 py-0.5 text-green-800 font-medium">
          {defense}
        </span>
        {techniques.map((t) => (
          <span
            key={t}
            className="rounded-full bg-amber-100 px-3 py-0.5 text-amber-800 font-medium"
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function BioshogiPanel({ data }: Props) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-sm font-bold text-slate-700">戦型・囲い情報</div>
      <SideInfo label="先手" side={data.sente} />
      <SideInfo label="後手" side={data.gote} />
      <div className="flex gap-4 text-xs text-slate-400 mt-1">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-blue-400" /> 戦型
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-green-400" /> 囲い
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400" /> 手筋
        </span>
      </div>
    </div>
  );
}
