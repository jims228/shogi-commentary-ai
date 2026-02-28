"use client";

import React, { useMemo, useState, useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowLeft, Check, Lock, Star, Play, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { LESSONS } from "@/constants";
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// --- レイアウト定数 ---
const ITEM_WIDTH = 180;  // 各アイテムの幅
const ITEM_HEIGHT = 100; // 各アイテムの高さエリア
const X_GAP = 60;        // 横の間隔
const Y_GAP = 120;       // 縦の間隔
const ITEMS_PER_ROW = 4; // 1行あたりの個数

export default function RoadmapPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(1000);
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);

  // 選択されたレッスンを取得
  const selectedLesson = useMemo(() => 
    LESSONS.find((l) => l.id === selectedLessonId), 
    [selectedLessonId]
  );

  // ウィンドウサイズ監視 (レスポンシブ対応)
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };
    window.addEventListener("resize", updateWidth);
    updateWidth();
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // スマホかどうか判定 (幅が狭いときは縦一列にする)
  const isMobile = containerWidth < 600;

  // --- 座標計算ロジック ---
  const layout = useMemo(() => {
    // モバイル時は計算不要 (単純なリスト表示にするため)
    if (isMobile) return [];

    const items = LESSONS.map((lesson, index) => {
      const row = Math.floor(index / ITEMS_PER_ROW);
      const colIndex = index % ITEMS_PER_ROW;
      
      // 偶数行は左→右、奇数行は右→左 (ジグザグ)
      const isReverseRow = row % 2 !== 0;
      const col = isReverseRow ? (ITEMS_PER_ROW - 1 - colIndex) : colIndex;

      // 全体の中央に寄せるためのオフセット計算
      const totalRowWidth = (ITEMS_PER_ROW * ITEM_WIDTH) + ((ITEMS_PER_ROW - 1) * X_GAP);
      const startX = (containerWidth - totalRowWidth) / 2 + (ITEM_WIDTH / 2);
      
      const x = startX + col * (ITEM_WIDTH + X_GAP);
      const y = 150 + row * (ITEM_HEIGHT + Y_GAP); // 上部に少し余白

      // ステータスのマッピング (available -> current として扱う)
      const visualStatus = lesson.status === "available" ? "current" : lesson.status;

      return { ...lesson, x, y, row, col, isReverseRow, visualStatus };
    });

    return items;
  }, [containerWidth, isMobile]);

  // --- SVGパス生成ロジック ---
  const svgPath = useMemo(() => {
    if (isMobile || layout.length === 0) return "";

    let path = `M ${layout[0].x} ${layout[0].y}`;

    for (let i = 0; i < layout.length - 1; i++) {
      const curr = layout[i];
      const next = layout[i + 1];

      // 同じ行なら直線を引く
      if (curr.row === next.row) {
        path += ` L ${next.x} ${next.y}`;
      } else {
        // 次の行へ移るカーブ (S字フックのような曲線)
        const midY = (curr.y + next.y) / 2;
        const controlX = curr.col === (ITEMS_PER_ROW - 1) 
          ? curr.x + 80 // 右へ膨らむ
          : curr.x - 80; // 左へ膨らむ

        path += ` C ${controlX} ${curr.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
      }
    }
    return path;
  }, [layout, isMobile]);

  // 全体の高さ計算
  const totalHeight = isMobile 
    ? "auto" 
    : (layout.length > 0 ? layout[layout.length - 1].y + 150 : 800);

  return (
    <div className="min-h-screen bg-transparent text-[color:var(--text)] overflow-x-hidden flex flex-col">
      {/* Header - sticky, not fixed */}
      <header 
        className="sticky top-0 left-0 right-0 z-50 bg-transparent border-b border-black/10 shadow-sm backdrop-blur-md"
        style={{ paddingTop: "var(--safe-area-inset-top, 0px)" }}
      >
        <div className="mx-auto max-w-6xl px-4 h-14 flex items-center">
          <Link href="/learn" className="flex items-center text-slate-600 hover:text-slate-900 transition-colors">
            <ArrowLeft className="w-5 h-5 mr-1" />
            <span className="font-bold">メニューに戻る</span>
          </Link>
          <h1 className="ml-6 text-xl font-bold text-slate-800">将棋学習ロードマップ</h1>
        </div>
      </header>

      <main className="flex-1 pb-20 px-4" ref={containerRef}>
        
        {/* === Desktop / Tablet View (蛇行レイアウト) === */}
        {!isMobile && (
          <div className="relative w-full mx-auto max-w-5xl" style={{ height: totalHeight }}>
            {/* SVG Path Background */}
            <svg className="absolute top-0 left-0 w-full h-full pointer-events-none z-0">
              <path 
                d={svgPath} 
                fill="none" 
                stroke="#e2d5c3" 
                strokeWidth="16" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
              />
              <path 
                d={svgPath} 
                fill="none" 
                stroke="#c0a080" 
                strokeWidth="3" 
                strokeDasharray="8 8" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                className="opacity-50"
              />
            </svg>

            {/* Nodes */}
            {layout.map((item, i) => (
              <div
                key={item.id}
                className="absolute z-10 flex flex-col items-center justify-center w-[180px]"
                style={{ 
                  left: item.x, 
                  top: item.y,
                  transform: "translate(-50%, -50%)" 
                }}
              >
                {/* Node Icon Circle */}
                <div 
                  onClick={() => item.status !== "locked" && setSelectedLessonId(item.id)}
                  className={cn(
                    "w-16 h-16 rounded-full border-4 flex items-center justify-center shadow-lg transition-transform hover:scale-110 cursor-pointer bg-white relative",
                    item.visualStatus === "completed" ? "border-emerald-500 text-emerald-600" :
                    item.visualStatus === "current" ? "border-amber-500 text-amber-600 animate-pulse-slow ring-4 ring-amber-200" :
                    "border-slate-300 text-slate-300 bg-slate-50 cursor-not-allowed"
                  )}
                >
                  {item.visualStatus === "completed" && <Check className="w-8 h-8 stroke-[3]" />}
                  {item.visualStatus === "current" && <Star className="w-8 h-8 fill-current" />}
                  {item.visualStatus === "locked" && <Lock className="w-6 h-6" />}
                  
                  {/* ステージ番号バッジ */}
                  <div className={cn(
                    "absolute -top-2 -right-2 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2",
                    item.visualStatus === "completed" ? "bg-emerald-500 text-white border-white" :
                    item.visualStatus === "current" ? "bg-amber-500 text-white border-white" :
                    "bg-slate-300 text-slate-500 border-white"
                  )}>
                    {i + 1}
                  </div>
                </div>

                {/* Text Label */}
                <div className="mt-3 text-center bg-white/80 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-black/5 shadow-sm">
                  <h3 className={cn("font-bold text-sm leading-tight", item.visualStatus === "locked" ? "text-slate-400" : "text-slate-800")}>
                    {item.title}
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}

            {/* Start / Goal Decoration */}
            <div className="absolute font-bold text-slate-400 text-4xl opacity-20 pointer-events-none" style={{ left: layout[0]?.x - 120, top: layout[0]?.y - 20 }}>
              START
            </div>
          </div>
        )}

        {/* === Mobile View (縦一列レイアウト) === */}
        {isMobile && (
          <div className="flex flex-col gap-8 max-w-sm mx-auto relative">
            <div className="absolute left-8 top-8 bottom-8 w-1 bg-slate-200 -z-10"></div>

            {LESSONS.map((item, i) => {
              const visualStatus = item.status === "available" ? "current" : item.status;
              return (
                <div key={item.id} className="flex items-center gap-4">
                  {/* Node */}
                  <div className="relative shrink-0">
                    <div 
                      onClick={() => item.status !== "locked" && setSelectedLessonId(item.id)}
                      className={cn(
                        "w-16 h-16 rounded-full border-4 flex items-center justify-center shadow-md bg-white z-10 relative cursor-pointer",
                        visualStatus === "completed" ? "border-emerald-500 text-emerald-600" :
                        visualStatus === "current" ? "border-amber-500 text-amber-600 ring-4 ring-amber-100" :
                        "border-slate-300 text-slate-300 bg-slate-50 cursor-not-allowed"
                      )}
                    >
                      {visualStatus === "completed" && <Check className="w-8 h-8 stroke-[3]" />}
                      {visualStatus === "current" && <Star className="w-8 h-8 fill-current" />}
                      {visualStatus === "locked" && <Lock className="w-6 h-6" />}
                    </div>
                  </div>

                  {/* Card */}
                  <div 
                    onClick={() => item.status !== "locked" && setSelectedLessonId(item.id)}
                    className={cn(
                      "flex-1 p-4 rounded-xl border shadow-sm bg-white transition-all active:scale-95 cursor-pointer",
                      visualStatus === "current" ? "border-amber-400 shadow-md" : "border-slate-200"
                    )}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full", 
                        visualStatus === "current" ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-500"
                      )}>
                        STAGE {i + 1}
                      </span>
                    </div>
                    <h3 className={cn("font-bold text-lg", visualStatus === "locked" ? "text-slate-400" : "text-slate-800")}>
                      {item.title}
                    </h3>
                    <p className="text-sm text-slate-500">
                      {item.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

      </main>

      {/* Modal (Dialog) */}
      <Dialog open={!!selectedLesson} onOpenChange={(open) => !open && setSelectedLessonId(null)}>
        <DialogContent className="fixed z-[99999] left-1/2 top-1/2 w-[80vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white/85 p-6 shadow-2xl border border-black/20 gap-0 text-[#3a2b17] backdrop-blur-md [&>button]:hidden">
          {selectedLesson && (
            <>
              <div className="flex justify-between items-start mb-4">
                <div>
                  <div className="text-xs font-bold text-[#b67a3c] uppercase tracking-wider mb-1">
                    {selectedLesson.category === "basics" ? "基本" : "詰将棋"}
                  </div>
                  <DialogTitle className="text-2xl font-bold !text-[#3a2b17]">
                    {selectedLesson.title}
                  </DialogTitle>
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSelectedLessonId(null)}
                  className="h-8 w-8 rounded-full hover:bg-black/5 !text-[#3a2b17]"
                >
                  <X className="w-6 h-6" />
                </Button>
              </div>

              {/* 説明文を非表示にしました */}

              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <span className="text-sm !text-[#6b4a2b]">難易度:</span>
                  <div className="flex">
                    {[...Array(3)].map((_, i) => (
                      <Star
                        key={i}
                        className={cn(
                          "w-4 h-4",
                          i < (selectedLesson.stars || 1) ? "text-[#3a2b17]" : "text-[#3a2b17]/30"
                        )}
                      />
                    ))}
                  </div>
                </div>

                {/* ステータス文言は表示しない */}
                <div className="text-sm font-bold !text-emerald-700" aria-hidden>
                  {/* intentionally left blank */}
                </div>
              </div>

              <DialogFooter className="sm:justify-center">
                <Link href={selectedLesson.href ?? `/training/${selectedLesson.category}/${selectedLesson.id}`} className="w-full">
                  {/* Buttonのデフォルト text-primary-foreground に負けないように !text-black を入れる */}
                  <Button className="w-full py-6 bg-emerald-600 hover:bg-emerald-500 !text-black font-bold rounded-xl shadow-lg shadow-emerald-900/20 transition-all active:scale-95 flex items-center justify-center gap-2 text-base [&_svg]:!text-black">
                    <Play className="w-5 h-5" fill="currentColor" />
                    レッスンを始める
                  </Button>
                </Link>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
