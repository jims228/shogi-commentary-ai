"use client";

import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { EngineMultipvItem } from "@/lib/annotateHook";

export type MoveListEntry = {
  ply: number;
  label: string;
  diff: number | null | undefined;
  score?: EngineMultipvItem["score"];
};

type MoveListPanelProps = {
  entries: MoveListEntry[];
  activePly: number;
  onSelectPly: (ply: number) => void;
  className?: string;
};

// 評価値フォーマット関数
const formatScore = (score?: EngineMultipvItem["score"]) => {
  if (!score) return "-";
  if (score.type === "mate") {
    const val = score.mate ?? 0;
    return `詰${Math.abs(val)}`;
  }
  return score.cp !== undefined ? `${score.cp > 0 ? "+" : ""}${score.cp}` : "-";
};

// ★修正: 悪手などの判定バッジ（大悪手を廃止し、基準を緩和）
const getQualityBadge = (diff: number | null | undefined) => {
  if (diff === null || diff === undefined) return null;
  
  // 旧基準: -400で大悪手, -200で悪手
  // 新基準: -500で悪手 (大悪手は廃止), -350で疑問手
  
  // if (diff <= -400) return <span className="...">大悪手</span>; // 廃止
  
  if (diff <= -500) {
      // 500点以上悪くなったら「悪手」
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-red-600 text-white font-bold">悪手</span>;
  }
  if (diff <= -350) {
      // 350点以上悪くなったら「疑問」
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-orange-500 text-white font-bold">疑問</span>;
  }
  // -80点程度ならスルー（表示なし）にするか、もっと緩い基準にする
  // if (diff <= -200) ... 

  if (diff >= 400) {
      // 400点以上良くなったら「好手」
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-blue-500 text-white font-bold">好手</span>;
  }
  
  return null;
};

export default function MoveListPanel({
  entries,
  activePly,
  onSelectPly,
  className,
}: MoveListPanelProps) {
  const activeRef = useRef<HTMLButtonElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // アクティブな行が常に表示されるようにスクロール
  useEffect(() => {
    if (activeRef.current && scrollContainerRef.current) {
      const container = scrollContainerRef.current;
      const element = activeRef.current;
      
      const containerTop = container.scrollTop;
      const containerBottom = containerTop + container.clientHeight;
      const elementTop = element.offsetTop;
      const elementBottom = elementTop + element.offsetHeight;

      if (elementTop < containerTop || elementBottom > containerBottom) {
        element.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  }, [activePly]);

  return (
    <div className={cn("flex flex-col h-full bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden", className)}>
      <div className="bg-slate-100 px-3 py-2 text-xs font-bold text-slate-600 border-b border-slate-200 flex justify-between items-center">
        <span>棋譜リスト</span>
        <span className="text-[10px] font-normal text-slate-400">{entries.length}手</span>
      </div>
      
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-slate-50 sticky top-0 z-10 text-[10px] text-slate-500 font-medium shadow-sm">
            <tr>
              <th className="px-2 py-1 w-8 text-center">#</th>
              <th className="px-2 py-1">指し手</th>
              <th className="px-2 py-1 w-16 text-right">評価値</th>
              <th className="px-2 py-1 w-12 text-center">判定</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const isActive = entry.ply === activePly;
              return (
                <tr
                  key={entry.ply}
                  onClick={() => onSelectPly(entry.ply)}
                  className={cn(
                    "cursor-pointer border-b border-slate-50 transition-colors hover:bg-slate-50",
                    isActive ? "bg-amber-100 hover:bg-amber-200" : ""
                  )}
                >
                  <td className="px-1 py-1.5 text-center text-xs text-slate-400 font-mono">
                    {entry.ply}
                  </td>
                  <td className={cn("px-2 py-1.5 text-sm font-medium text-slate-800", isActive && "text-amber-900")}>
                    <button ref={isActive ? activeRef : null} className="w-full text-left focus:outline-none">
                      {entry.label}
                    </button>
                  </td>
                  <td className="px-2 py-1.5 text-right text-xs font-mono text-slate-600">
                    {entry.score ? formatScore(entry.score) : ""}
                  </td>
                  <td className="px-1 py-1.5 text-center align-middle">
                    {getQualityBadge(entry.diff)}
                  </td>
                </tr>
              );
            })}
            {entries.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-xs text-slate-400">
                  棋譜がありません
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}