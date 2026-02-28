"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, ArrowRight, Lightbulb } from "lucide-react";
import { ShogiBoard } from "@/components/ShogiBoard"; 
import { ManRive } from "@/components/ManRive";
import { AutoScaleToFit } from "@/components/training/AutoScaleToFit";
import { WoodBoardFrame } from "@/components/training/WoodBoardFrame";
import { LessonScaffold } from "@/components/training/lesson/LessonScaffold";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { SILVER_LESSONS } from "@/constants/rulesData";
import { showToast } from "@/components/ui/toast";
import { buildPositionFromUsi } from "@/lib/board"; 
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";
import { useMobileQueryParam } from "@/hooks/useMobileQueryParam";

export default function SilverTrainingPage() {
  const router = useRouter();
  
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [board, setBoard] = useState<any[][]>([]); 
  const [hands, setHands] = useState<any>({ b: {}, w: {} });
  const [isCorrect, setIsCorrect] = useState(false);
  const [correctSignal, setCorrectSignal] = useState(0);
  
  const currentLesson = SILVER_LESSONS[currentStepIndex];
  const isDesktop = useMediaQuery("(min-width: 820px)");
  const isMobileWebView = useMobileQueryParam();

  useEffect(() => {
    if (currentLesson) {
      try {
        const initial = buildPositionFromUsi(currentLesson.sfen);
        setBoard(initial.board);
        setHands({ b: {}, w: {} });
      } catch (e) {
        console.error("SFEN Parse Error", e);
      }
      setIsCorrect(false);
    }
  }, [currentLesson]);

  const handleMove = useCallback((move: { from?: { x: number; y: number }; to: { x: number; y: number }; piece: string; drop?: boolean }) => {
    const correct = currentLesson.checkMove(move);

    if (correct) {
      setIsCorrect(true);
      setCorrectSignal((v) => v + 1);
      showToast({ title: "正解！", description: currentLesson.successMessage });
    } else {
      showToast({ title: "惜しい！", description: "その手ではありません。もう一度考えてみましょう。" });
      
      setTimeout(() => {
        const initial = buildPositionFromUsi(currentLesson.sfen);
        setBoard(initial.board);
        setHands({ b: {}, w: {} });
      }, 1000);
    }
  }, [currentLesson]);

  const handleNext = () => {
    if (currentStepIndex < SILVER_LESSONS.length - 1) {
      setCurrentStepIndex(prev => prev + 1);
    } else {
      postMobileLessonCompleteOnce();
      router.push("/learn");
    }
  };

  if (!currentLesson) return <div className="p-10">読み込み中...</div>;

  const nextButton = isCorrect ? (
    <button
      onClick={handleNext}
      className="mt-3 w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 transition-all active:scale-95"
    >
      {currentStepIndex < SILVER_LESSONS.length - 1 ? "次のステップへ" : "レッスン完了！"}
      <ArrowRight className="w-5 h-5" />
    </button>
  ) : null;

  const boardElement = (
    <div className="w-full h-full flex items-center justify-center">
      <div
        className="w-full"
        style={{
          maxWidth: 760,
          aspectRatio: "1 / 1",
          minHeight: isDesktop ? 560 : 360,
        }}
      >
        <AutoScaleToFit minScale={0.7} maxScale={1.45} className="w-full h-full">
          <WoodBoardFrame paddingClassName="p-3" className="inline-block">
            <ShogiBoard
              board={board}
              hands={hands}
              hintStars={currentLesson.hintStars ?? []}
              mode="edit"
              onMove={handleMove}
              onBoardChange={setBoard}
              onHandsChange={setHands}
              orientation="sente"
            />
          </WoodBoardFrame>
        </AutoScaleToFit>
      </div>
    </div>
  );

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

  const explanationElement = (
    <div className="bg-white/80 backdrop-blur rounded-2xl shadow border border-black/10 p-4">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
        <span>STEP {currentStepIndex + 1}</span>
        <span className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
          <span
            className="block h-full bg-emerald-500 transition-all duration-500"
            style={{ width: `${((currentStepIndex + 1) / SILVER_LESSONS.length) * 100}%` }}
          />
        </span>
        <span>{SILVER_LESSONS.length}</span>
      </div>

      <div className="mt-3">
        <h1 className="text-xl font-bold text-[#3a2b17]">{currentLesson.title}</h1>

        <div className="mt-3 flex items-start gap-3 bg-amber-50/80 p-3 rounded-2xl text-amber-900 border border-amber-200/50">
          <Lightbulb className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="leading-relaxed font-medium text-sm">{currentLesson.description}</p>
        </div>

        {isCorrect && (
          <div className="animate-in fade-in zoom-in-95 duration-300 mt-4">
            <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 text-center">
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 mb-2">
                <CheckCircle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-emerald-800 mb-1">Excellent!</h3>
              <p className="text-emerald-700 text-sm">{currentLesson.successMessage}</p>
            </div>
          </div>
        )}

        {isDesktop && nextButton}
      </div>
    </div>
  );

  const mascotElement = (
    <div style={{ transform: "translateY(-12px)" }}>
      <ManRive
        correctSignal={correctSignal}
        className="bg-transparent [&>canvas]:bg-transparent"
        style={{
          width: isDesktop ? 380 : 260,
          height: isDesktop ? 380 : 260,
        }}
      />
    </div>
  );

  if (isMobileWebView) {
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
            tag={`STEP ${currentStepIndex + 1}/${SILVER_LESSONS.length}`}
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
    <LessonScaffold
      title="基本の駒：銀"
      backHref="/learn/roadmap"
      board={boardElement}
      explanation={explanationElement}
      mascot={mascotElement}
      topLabel="NEW CONCEPT"
      progress01={(currentStepIndex + 1) / SILVER_LESSONS.length}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      mobileAction={!isDesktop ? nextButton : null}
    />
  );
}