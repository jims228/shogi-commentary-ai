"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, ArrowRight, Lightbulb } from "lucide-react";

import { ShogiBoard } from "@/components/ShogiBoard";
import { ManRive } from "@/components/ManRive";
import { AutoScaleToFit } from "@/components/training/AutoScaleToFit";
import { WoodBoardFrame } from "@/components/training/WoodBoardFrame";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { LessonScaffold } from "@/components/training/lesson/LessonScaffold";

import { PAWN_LESSON_1_ROLE_STEPS } from "@/constants/rulesData";
import { showToast } from "@/components/ui/toast";
import { buildPositionFromUsi } from "@/lib/board";
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { useMobileParams } from "@/hooks/useMobileQueryParam";
import { createEmptyBoard } from "@/lib/board";

const normalizeUsiPosition = (s: string) => {
  const t = (s ?? "").trim();
  if (!t) return "position startpos";
  if (t.startsWith("position ")) return t;
  if (t.startsWith("startpos")) return `position ${t}`;
  if (t.startsWith("sfen ")) return `position ${t}`;
  return `position sfen ${t}`;
};

function postToRn(msg: { type: string; [k: string]: unknown }) {
  try {
    const w = typeof window !== "undefined" ? (window as any) : null;
    if (w?.ReactNativeWebView?.postMessage) w.ReactNativeWebView.postMessage(JSON.stringify(msg));
  } catch { /* ignore */ }
}

export default function PawnRolePage() {
  const router = useRouter();
  const { mobile: isMobileWebView, embed: isEmbed } = useMobileParams();

  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [board, setBoard] = useState<any[][]>(() => createEmptyBoard());
  const [hands, setHands] = useState<any>({ b: {}, w: {} });
  const [isCorrect, setIsCorrect] = useState(false);
  const [correctSignal, setCorrectSignal] = useState(0);

  const currentLesson = PAWN_LESSON_1_ROLE_STEPS[currentStepIndex];
  // レイアウト判定（Scaffoldと揃える）
  const isDesktop = useMediaQuery("(min-width: 820px)");

  useEffect(() => {
    if (!currentLesson) return;
    try {
      const initial = buildPositionFromUsi(normalizeUsiPosition(currentLesson.sfen));
      setBoard(initial.board);
      setHands((initial as any).hands ?? { b: {}, w: {} });
    } catch (e) {
      console.error("SFEN Parse Error", e);
    }
    setIsCorrect(false);
    if (isEmbed) postToRn({ type: "stepChanged", stepIndex: currentStepIndex, totalSteps: PAWN_LESSON_1_ROLE_STEPS.length, title: currentLesson.title, description: currentLesson.description });
  }, [currentLesson, currentStepIndex, isEmbed]);

  const handleMove = useCallback(
    (move: { from?: { x: number; y: number }; to: { x: number; y: number }; piece: string; drop?: boolean }) => {
      const correct = currentLesson.checkMove(move as any);

      if (correct) {
        setIsCorrect(true);
        setCorrectSignal((v) => v + 1);
        if (isEmbed) postToRn({ type: "lessonCorrect" });
        else showToast({ title: "正解！", description: currentLesson.successMessage });
      } else {
        if (isEmbed) postToRn({ type: "lessonWrong" });
        else showToast({ title: "惜しい！", description: "その手ではありません。もう一度考えてみましょう。" });

        setTimeout(() => {
          const initial = buildPositionFromUsi(normalizeUsiPosition(currentLesson.sfen));
          setBoard(initial.board);
          setHands((initial as any).hands ?? { b: {}, w: {} });
        }, 900);
      }
    },
    [currentLesson, isEmbed],
  );

  const handleNext = () => {
    if (currentStepIndex < PAWN_LESSON_1_ROLE_STEPS.length - 1) setCurrentStepIndex((p) => p + 1);
    else {
      postMobileLessonCompleteOnce();
      router.push("/learn/roadmap");
    }
  };

  const handleNextRef = useRef(handleNext);
  handleNextRef.current = handleNext;
  useEffect(() => {
    if (!isEmbed || typeof window === "undefined") return;
    (window as any).__rnLessonNext = () => handleNextRef.current();
    return () => { delete (window as any).__rnLessonNext; };
  }, [isEmbed]);

  if (!currentLesson) return <div className="p-10">読み込み中...</div>;

  const isBoardReady = Array.isArray(board) && board.length === 9;

  if (isEmbed) {
    return (
      <>
        <style jsx global>{`
          html, body, #__next {
            background: transparent !important;
            background-image: none !important;
          }
          body::before,
          body::after {
            content: none !important;
            display: none !important;
            background-image: none !important;
          }
        `}</style>
        <div className="w-full h-full flex items-center justify-center p-2 bg-transparent">
        <AutoScaleToFit minScale={0.25} maxScale={2.4} fitMode="width-only" className="w-full h-full" overflowHidden={true}>
          <WoodBoardFrame paddingClassName="p-1">
            <ShogiBoard
              key={currentStepIndex}
              board={isBoardReady ? board : createEmptyBoard()}
              hands={hands}
              hintStars={currentLesson.hintStars ?? []}
              mode="edit"
              onMove={handleMove}
              onBoardChange={setBoard}
              onHandsChange={setHands}
              orientation="sente"
              showCoordinates={false}
              showHands={true}
              handsPlacement="default"
              compactHands={true}
            />
          </WoodBoardFrame>
        </AutoScaleToFit>
        </div>
      </>
    );
  }

  const nextButton = isCorrect ? (
    <button
      onClick={handleNext}
      className="mt-3 w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 transition-all active:scale-95"
    >
      {currentStepIndex < PAWN_LESSON_1_ROLE_STEPS.length - 1 ? "次のステップへ" : "レッスン完了！"}
      <ArrowRight className="w-5 h-5" />
    </button>
  ) : null;

  // ===== 盤面（左側に常に出す）=====
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
            style={{ width: `${((currentStepIndex + 1) / PAWN_LESSON_1_ROLE_STEPS.length) * 100}%` }}
          />
        </span>
        <span>{PAWN_LESSON_1_ROLE_STEPS.length}</span>
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

  const mascotOverlay = isCorrect ? (
    <div className="bg-white/95 border border-emerald-100 rounded-2xl p-3 shadow-md w-56">
      <h3 className="text-sm font-bold text-emerald-800">正解！</h3>
      <p className="text-sm text-emerald-700 mt-1">{currentLesson.successMessage}</p>
    </div>
  ) : null;

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
          // Long descriptions can exist for this lesson; MobileLessonShell clamps via its scroll area.
          <MobileCoachText
            tag={`STEP ${currentStepIndex + 1}/${PAWN_LESSON_1_ROLE_STEPS.length}`}
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
      title="歩の役割（壁・道を開ける・捨て駒・と金）"
      backHref="/learn/roadmap"
      board={boardElement}
      explanation={explanationElement}
      mascot={mascotElement}
      mascotOverlay={mascotOverlay}
      topLabel="CONCEPT"
      progress01={(currentStepIndex + 1) / PAWN_LESSON_1_ROLE_STEPS.length}
      headerRight={<span>❤ 4</span>}
      desktopMinWidthPx={820}
      mobileAction={!isDesktop ? nextButton : null}
    />
  );
}
