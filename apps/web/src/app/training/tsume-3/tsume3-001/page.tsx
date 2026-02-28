"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, CheckCircle, ArrowRight, Lightbulb } from "lucide-react";
import { ShogiBoard } from "@/components/ShogiBoard"; 
import { ManRive } from "@/components/ManRive";
import { TSUME_3_LESSONS } from "@/constants/rulesData"; 
import { showToast } from "@/components/ui/toast";
import { buildPositionFromUsi } from "@/lib/board"; 
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { AutoScaleToFit } from "@/components/training/AutoScaleToFit";
import { WoodBoardFrame } from "@/components/training/WoodBoardFrame";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";
import { useMobileQueryParam } from "@/hooks/useMobileQueryParam";

export default function Tsume3TrainingPage() {
  const router = useRouter();
  const isMobileWebView = useMobileQueryParam();
  
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [board, setBoard] = useState<any[][]>([]); 
  const [hands, setHands] = useState<any>({ b: {}, w: {} });
  const [isCorrect, setIsCorrect] = useState(false);
  const [correctSignal, setCorrectSignal] = useState(0);
  
  const currentLesson = TSUME_3_LESSONS[currentStepIndex];

  // 盤面・持ち駒のセットアップ関数
  const setupBoard = useCallback(() => {
    if (!currentLesson) return;
    try {
      const initial = buildPositionFromUsi(currentLesson.sfen);
      setBoard(initial.board);
      
      const initialHands = { b: {} as any, w: {} as any };
      
      // SFEN文字列を見て、持ち駒を手動セットする
      if (currentLesson.sfen.includes("b G")) {
           initialHands.b = { G: 1 }; // 金を持っている場合
      } else if (currentLesson.sfen.includes("b R")) {
           initialHands.b = { R: 1 }; // 飛車を持っている場合
      }
      
      setHands(initialHands);

    } catch (e) {
      console.error("SFEN Parse Error", e);
    }
  }, [currentLesson]);

  // ステップが変わったら初期化
  useEffect(() => {
    setupBoard();
    setIsCorrect(false);
  }, [setupBoard]);

  const handleMove = useCallback((move: { from?: { x: number; y: number }; to: { x: number; y: number }; piece: string; drop?: boolean }) => {
    const correct = currentLesson.checkMove(move);

    if (correct) {
      setIsCorrect(true);
      setCorrectSignal((v) => v + 1);
      showToast({ title: "正解！", description: currentLesson.successMessage });
    } else {
      showToast({ title: "惜しい！", description: "その手ではありません。" });
      // 1秒後にリセット
      setTimeout(() => {
        setupBoard();
      }, 1000);
    }
  }, [currentLesson, setupBoard]);

  const handleNext = () => {
    if (currentStepIndex < TSUME_3_LESSONS.length - 1) {
      setCurrentStepIndex(prev => prev + 1);
    } else {
      postMobileLessonCompleteOnce();
      router.push("/learn");
    }
  };

  if (!currentLesson) return <div className="p-10">読み込み中...</div>;

  if (isMobileWebView) {
    const boardElementMobile = (
      <div className="w-full h-full min-h-0 flex items-center justify-center">
        <div className="w-full h-full aspect-square -translate-y-2">
          <AutoScaleToFit minScale={0.5} maxScale={2.4} className="w-full h-full">
            <WoodBoardFrame paddingClassName="p-1" className="w-full h-full">
              <div className="relative w-full h-full">
                <ShogiBoard
                  board={board}
                  hands={hands}
                  hintStars={currentLesson.hintStars ?? []}
                  mode="edit"
                  onMove={handleMove}
                  onBoardChange={setBoard}
                  onHandsChange={setHands}
                  orientation="sente"
                  handsPlacement="corners"
                  showCoordinates={false}
                />
              </div>
            </WoodBoardFrame>
          </AutoScaleToFit>
        </div>
      </div>
    );

    return (
      <MobileLessonShell
        mascot={
          <ManRive
            correctSignal={correctSignal}
            className="bg-transparent [&>canvas]:bg-transparent"
            style={{ width: 210, height: 210 }}
          />
        }
        explanation={
          <MobileCoachText
            tag={`TSUME ${currentStepIndex + 1}/${TSUME_3_LESSONS.length}`}
            text={currentLesson.description}
            isCorrect={isCorrect}
            correctText="正解！次へ進もう。"
          />
        }
        actions={isCorrect ? <MobilePrimaryCTA onClick={handleNext} /> : null}
        board={boardElementMobile}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#f6f1e6] text-[#2b2b2b] flex flex-col">
      <div
        style={{
          position: "fixed",
          left: 12,
          top: 12,
          zIndex: 50,
          width: 160,
          height: 160,
          pointerEvents: "none",
        }}
      >
        <ManRive correctSignal={correctSignal} style={{ width: "100%", height: "100%" }} />
      </div>
      <header className="h-16 border-b border-black/10 bg-white/50 flex items-center px-4 justify-between sticky top-0 z-10 backdrop-blur-sm">
        <Link href="/learn" className="flex items-center gap-2 text-slate-600 hover:text-slate-900 font-bold transition-colors">
          <ChevronLeft className="w-5 h-5" />
          <span>学習マップ</span>
        </Link>
        <div className="font-bold text-lg text-[#3a2b17]">1手詰・実戦編</div>
        <div className="w-20" />
      </header>

      <main className="flex-1 flex flex-col lg:flex-row items-start justify-center gap-8 p-4 md:p-8 max-w-6xl mx-auto w-full">
        <div className="flex-1 w-full max-w-md space-y-6">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-400">
            <span>STEP {currentStepIndex + 1}</span>
            <span className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
              <span 
                className="block h-full bg-emerald-500 transition-all duration-500" 
                style={{ width: `${((currentStepIndex + 1) / TSUME_3_LESSONS.length) * 100}%` }}
              />
            </span>
            <span>{TSUME_3_LESSONS.length}</span>
          </div>

          <div className="bg-white p-6 rounded-3xl shadow-sm border border-black/5">
            <h1 className="text-2xl font-bold text-[#3a2b17] mb-4">{currentLesson.title}</h1>
            <div className="flex items-start gap-3 bg-amber-50 p-4 rounded-xl text-amber-900 mb-6">
              <Lightbulb className="w-5 h-5 shrink-0 mt-0.5" />
              <p className="leading-relaxed font-medium">{currentLesson.description}</p>
            </div>

            {isCorrect && (
              <div className="animate-in fade-in zoom-in-95 duration-300">
                <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-6 text-center mb-6">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 mb-3">
                    <CheckCircle className="w-6 h-6" />
                  </div>
                  <h3 className="text-lg font-bold text-emerald-800 mb-1">Excellent!</h3>
                  <p className="text-emerald-700">{currentLesson.successMessage}</p>
                </div>
                <button 
                  onClick={handleNext}
                  className="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 transition-all active:scale-95"
                >
                  {currentStepIndex < TSUME_3_LESSONS.length - 1 ? "次のステップへ" : "レッスン完了！"}
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex-none w-full lg:w-auto flex justify-center">
          <div className="bg-[#f3c882] p-1 rounded-xl shadow-2xl border-4 border-[#5d4037]">
             <ShogiBoard
                board={board}
                hands={hands}
                hintStars={currentLesson.hintStars ?? []}
                mode="edit" 
                onMove={handleMove}
                onBoardChange={setBoard} 
                onHandsChange={setHands}
                orientation="sente"
                // ★修正: 敵陣ハイライトは出すが、自動成りをOFFにする
                showPromotionZone={true} 
                autoPromote={false} 
             />
          </div>
        </div>
      </main>
    </div>
  );
}