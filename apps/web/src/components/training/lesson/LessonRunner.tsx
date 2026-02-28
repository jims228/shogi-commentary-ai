"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle, Lightbulb, RotateCcw } from "lucide-react";

import { LessonScaffold } from "@/components/training/lesson/LessonScaffold";
import { ManRive } from "@/components/ManRive";
import { AutoScaleToFit } from "@/components/training/AutoScaleToFit";
import { WoodBoardFrame } from "@/components/training/WoodBoardFrame";
import { ShogiBoard } from "@/components/ShogiBoard";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { showToast } from "@/components/ui/toast";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";

import type { LessonStep, PracticeProblem } from "@/lib/training/lessonTypes";
import { isExpectedMove, type BoardMove } from "@/lib/training/moveJudge";
import { buildPositionFromUsi } from "@/lib/board";
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { useMobileParams } from "@/hooks/useMobileQueryParam";
import { createEmptyBoard } from "@/lib/board";

const normalizeUsiPosition = (s: string) => {
  const t = (s ?? "").trim();
  if (!t) return "position startpos";
  if (t.startsWith("position ")) return t;
  if (t.startsWith("startpos")) return `position ${t}`;
  if (t.startsWith("sfen ")) return `position ${t}`;
  // 盤面部分だけが来た場合もあるので sfen 扱い
  return `position sfen ${t}`;
};

type Props = {
  title: string;
  backHref: string;
  steps: LessonStep[];
  topLabel?: string;
  headerRight?: React.ReactNode;
  desktopMinWidthPx?: number;
  /** 完了時の遷移先。未指定なら backHref へ */
  onFinishHref?: string;
  /** mobile=1 from server searchParams (avoid window-based branching to prevent hydration mismatch) */
  mobile?: boolean;
  /** Reserve space for mobile CTA to avoid layout shift */
  reserveMobileCtaSpace?: boolean;
  /** Fix mobile explanation height to avoid layout shift */
  mobileExplanationHeightPx?: number;
};

type PracticeRef = { stepIndex: number; problemIndex: number };

export function LessonRunner({
  title,
  backHref,
  steps,
  topLabel = "DRILL",
  headerRight,
  desktopMinWidthPx = 820,
  onFinishHref,
  mobile,
  reserveMobileCtaSpace = false,
  mobileExplanationHeightPx,
}: Props) {
  const router = useRouter();
  const isDesktop = useMediaQuery(`(min-width: ${desktopMinWidthPx}px)`);
  const { mobile: mobileFromUrl, embed: isEmbed } = useMobileParams();
  const isMobileWebView = mobile ?? mobileFromUrl;

  const postToRn = useCallback((msg: { type: string; [k: string]: unknown }) => {
    try {
      const w = typeof window !== "undefined" ? (window as any) : null;
      if (w?.ReactNativeWebView?.postMessage) w.ReactNativeWebView.postMessage(JSON.stringify(msg));
    } catch { /* ignore */ }
  }, []);

  const [stepIndex, setStepIndex] = useState(0);
  const [guidedSubIndex, setGuidedSubIndex] = useState(0);
  const [practiceIndex, setPracticeIndex] = useState(0);
  const [reviewIndex, setReviewIndex] = useState(0);

  const [board, setBoard] = useState<any[][]>([]);
  const [hands, setHands] = useState<any>({ b: {}, w: {} });

  const [isCorrect, setIsCorrect] = useState(false);
  const [correctSignal, setCorrectSignal] = useState(0);
  const [hintEnabled, setHintEnabled] = useState(false);

  // mistakes: practice problems only (MVP)
  const [mistakes, setMistakes] = useState<PracticeRef[]>([]);
  const mistakesSet = useMemo(() => new Set(mistakes.map((m) => `${m.stepIndex}:${m.problemIndex}`)), [mistakes]);

  const step = steps[stepIndex];

  const practiceProblemsByStep = useMemo(() => {
    const map = new Map<number, PracticeProblem[]>();
    steps.forEach((s, idx) => {
      if (s.type === "practice") map.set(idx, s.problems);
    });
    return map;
  }, [steps]);

  const reviewQueue: PracticeRef[] = useMemo(() => {
    if (!step || step.type !== "review") return [];
    if (step.source !== "mistakesInThisLesson") return [];
    const all = mistakes.slice(0, step.count);
    return all;
  }, [mistakes, step]);

  const currentPrompt = useMemo(() => {
    if (!step) return "";
    if (step.type === "guided") {
      return step.substeps[guidedSubIndex]?.prompt ?? "";
    }
    if (step.type === "practice") {
      return step.problems[practiceIndex]?.question ?? "";
    }
    if (step.type === "review") {
      const ref = reviewQueue[reviewIndex];
      if (!ref) return "復習問題はありません。";
      const p = practiceProblemsByStep.get(ref.stepIndex)?.[ref.problemIndex];
      return p ? `復習：${p.question}` : "復習問題を読み込み中…";
    }
    return "";
  }, [guidedSubIndex, practiceIndex, practiceProblemsByStep, reviewIndex, reviewQueue, step]);

  const effectiveSfen = useMemo(() => {
    if (!step) return "position startpos";
    if (step.type === "guided") {
      const sub = step.substeps[guidedSubIndex];
      return sub?.sfen ?? step.sfen;
    }
    if (step.type === "practice") {
      return step.problems[practiceIndex]?.sfen ?? step.sfen;
    }
    if (step.type === "review") {
      const ref = reviewQueue[reviewIndex];
      const p = ref ? practiceProblemsByStep.get(ref.stepIndex)?.[ref.problemIndex] : null;
      return p?.sfen ?? step.sfen;
    }
    // union is exhaustive; this is unreachable but keeps TS happy
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _exhaustive: never = step;
    return "position startpos";
  }, [guidedSubIndex, practiceIndex, practiceProblemsByStep, reviewIndex, reviewQueue, step]);

  const orientation: "sente" | "gote" = useMemo(() => {
    if (!step) return "sente";
    if (step.type === "guided") return step.orientation ?? "sente";
    if (step.type === "practice") return step.orientation ?? "sente";
    return step.orientation ?? "sente";
  }, [step]);

  const hintSquares = useMemo(() => {
    if (!step) return [];
    if (step.type === "guided") return step.substeps[guidedSubIndex]?.highlights ?? [];
    if (step.type === "practice") {
      if (!hintEnabled) return [];
      return step.problems[practiceIndex]?.hints?.highlights ?? [];
    }
    if (step.type === "review") {
      if (!hintEnabled) return [];
      const ref = reviewQueue[reviewIndex];
      const p = ref ? practiceProblemsByStep.get(ref.stepIndex)?.[ref.problemIndex] : null;
      return p?.hints?.highlights ?? [];
    }
    return [];
  }, [guidedSubIndex, hintEnabled, practiceIndex, practiceProblemsByStep, reviewIndex, reviewQueue, step]);

  const hintArrows = useMemo(() => {
    if (!step) return [];
    if (step.type === "guided") return step.substeps[guidedSubIndex]?.arrows ?? [];
    if (step.type === "practice") {
      if (!hintEnabled) return [];
      return step.problems[practiceIndex]?.hints?.arrows ?? [];
    }
    if (step.type === "review") {
      if (!hintEnabled) return [];
      const ref = reviewQueue[reviewIndex];
      const p = ref ? practiceProblemsByStep.get(ref.stepIndex)?.[ref.problemIndex] : null;
      return p?.hints?.arrows ?? [];
    }
    return [];
  }, [guidedSubIndex, hintEnabled, practiceIndex, practiceProblemsByStep, reviewIndex, reviewQueue, step]);

  const visibleHintArrows = useMemo(() => {
    if (isCorrect) return [];
    return hintArrows;
  }, [hintArrows, isCorrect]);

  const expectedMoves = useMemo(() => {
    if (!step) return [];
    if (step.type === "guided") return step.substeps[guidedSubIndex]?.expectedMoves ?? [];
    if (step.type === "practice") return step.problems[practiceIndex]?.expectedMoves ?? [];
    if (step.type === "review") {
      const ref = reviewQueue[reviewIndex];
      const p = ref ? practiceProblemsByStep.get(ref.stepIndex)?.[ref.problemIndex] : null;
      return p?.expectedMoves ?? [];
    }
    return [];
  }, [guidedSubIndex, practiceIndex, practiceProblemsByStep, reviewIndex, reviewQueue, step]);

  // step/substep/prob changes reset state
  useEffect(() => {
    setIsCorrect(false);
    setHintEnabled(false);
  }, [stepIndex, guidedSubIndex, practiceIndex, reviewIndex]);

  // Load SFEN when effectiveSfen changes
  useEffect(() => {
    if (!step) return;
    try {
      const initial = buildPositionFromUsi(normalizeUsiPosition(effectiveSfen));
      setBoard(initial.board);
      setHands((initial as any).hands ?? { b: {}, w: {} });
    } catch (e) {
      console.error("SFEN Parse Error", e);
    }
  }, [effectiveSfen, step]);

  // Guided: auto-advance for "empty expectedMoves" substeps
  useEffect(() => {
    if (!step || step.type !== "guided") return;
    const sub = step.substeps[guidedSubIndex];
    if (!sub) return;
    if (sub.expectedMoves.length > 0) return;
    const ms = sub.autoAdvanceMs ?? 250;
    const t = window.setTimeout(() => {
      const last = step.substeps.length - 1;
      if (guidedSubIndex < last) setGuidedSubIndex((p) => p + 1);
      else setStepIndex((p) => Math.min(p + 1, steps.length - 1));
    }, ms);
    return () => window.clearTimeout(t);
  }, [guidedSubIndex, step, steps.length]);

  const resetCurrentPosition = useCallback(() => {
    try {
      const initial = buildPositionFromUsi(normalizeUsiPosition(effectiveSfen));
      setBoard(initial.board);
      setHands((initial as any).hands ?? { b: {}, w: {} });
    } catch (e) {
      console.error("SFEN Parse Error", e);
    }
  }, [effectiveSfen]);

  const markMistakeIfNeeded = useCallback(() => {
    if (!step || step.type !== "practice") return;
    const key = `${stepIndex}:${practiceIndex}`;
    if (mistakesSet.has(key)) return;
    setMistakes((prev) => [...prev, { stepIndex, problemIndex: practiceIndex }]);
  }, [mistakesSet, practiceIndex, step, stepIndex]);

  const goNext = () => {
    if (!step) return;

    const finishLesson = () => {
      // Guarantee: mobile completion should fire regardless of whether a "review" step exists.
      // postMobileLessonCompleteOnce is single-shot and no-ops outside mobile WebView.
      postMobileLessonCompleteOnce();
      router.push(onFinishHref ?? backHref);
    };

    if (step.type === "guided") {
      const lastSub = step.substeps.length - 1;
      if (guidedSubIndex < lastSub) {
        setGuidedSubIndex((p) => p + 1);
        return;
      }
      // guided step finished
      if (stepIndex >= steps.length - 1) {
        finishLesson();
        return;
      }
      setGuidedSubIndex(0);
      setStepIndex((p) => Math.min(p + 1, steps.length - 1));
      return;
    }

    if (step.type === "practice") {
      const last = step.problems.length - 1;
      if (practiceIndex < last) {
        setPracticeIndex((p) => p + 1);
        return;
      }
      if (stepIndex >= steps.length - 1) {
        finishLesson();
        return;
      }
      setPracticeIndex(0);
      setStepIndex((p) => Math.min(p + 1, steps.length - 1));
      return;
    }

    if (step.type === "review") {
      const last = reviewQueue.length - 1;
      if (reviewIndex < last) {
        setReviewIndex((p) => p + 1);
        return;
      }
      // lesson finished
      finishLesson();
      return;
    }
  };

  const handleMove = (move: BoardMove) => {
    if (!step) return;
    if (isCorrect) return; // prevent double input during success state

    const ok = isExpectedMove(move, expectedMoves);

    if (ok) {
      setIsCorrect(true);
      setCorrectSignal((v) => v + 1);

      const after: "auto" | "nextButton" = (() => {
        if (step.type === "guided") return step.substeps[guidedSubIndex]?.after ?? "auto";
        return "nextButton";
      })();

      if (after === "auto") {
        window.setTimeout(() => {
          goNext();
        }, 200);
      } else {
        if (isEmbed) {
          postToRn({ type: "lessonCorrect" });
        } else if (!isMobileWebView) {
          showToast({ title: "正解！", description: "次へ進もう。" });
        }
      }
      return;
    }

    // wrong
    if (step.type === "practice") markMistakeIfNeeded();

    if (isEmbed) {
      postToRn({ type: "lessonWrong" });
    } else {
      const wrongHint =
        step.type === "guided"
          ? step.substeps[guidedSubIndex]?.wrongHint
          : "その手ではありません。もう一度考えてみましょう。";
      showToast({ title: "惜しい！", description: wrongHint ?? "その手ではありません。もう一度考えてみましょう。" });
    }
    window.setTimeout(() => resetCurrentPosition(), 650);
  };

  const canShowNextButton = useMemo(() => {
    if (!step) return false;
    if (!isCorrect) return false;
    if (step.type === "guided") return (step.substeps[guidedSubIndex]?.after ?? "auto") === "nextButton";
    return true;
  }, [guidedSubIndex, isCorrect, step]);

  const nextButton = canShowNextButton ? (
    <button
      onClick={goNext}
      className="mt-3 w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 transition-all active:scale-95"
    >
      次へ
      <ArrowRight className="w-5 h-5" />
    </button>
  ) : null;

  const hintButton =
    step && (step.type === "practice" || step.type === "review") ? (
      <button
        onClick={() => setHintEnabled((v) => !v)}
        className="mt-3 w-full py-3 bg-amber-200 hover:bg-amber-300 text-amber-900 rounded-xl font-bold flex items-center justify-center gap-2 border border-amber-300 transition-all active:scale-95"
      >
        {hintEnabled ? "ヒントを隠す" : "ヒント（矢印）"}
        <Lightbulb className="w-5 h-5" />
      </button>
    ) : null;

  const resetButton =
    step && (step.type === "practice" || step.type === "review") ? (
      <button
        onClick={resetCurrentPosition}
        className="mt-2 w-full py-2 bg-white/80 hover:bg-white text-slate-700 rounded-xl font-bold flex items-center justify-center gap-2 border border-black/10 transition-all active:scale-95"
      >
        <RotateCcw className="w-4 h-4" />
        局面を戻す
      </button>
    ) : null;

  const progress01 = useMemo(() => {
    // rough: each step counts as 1 unit; guided/practice/review internal progress adds small detail
    if (!step) return 0;
    const base = stepIndex / Math.max(1, steps.length);
    const perStep = 1 / Math.max(1, steps.length);
    if (step.type === "guided") {
      const inner = guidedSubIndex / Math.max(1, step.substeps.length);
      return base + perStep * inner;
    }
    if (step.type === "practice") {
      const inner = practiceIndex / Math.max(1, step.problems.length);
      return base + perStep * inner;
    }
    if (step.type === "review") {
      const inner = reviewIndex / Math.max(1, Math.max(1, reviewQueue.length));
      return base + perStep * inner;
    }
    return base;
  }, [guidedSubIndex, practiceIndex, reviewIndex, reviewQueue.length, step, stepIndex, steps.length]);

  // embed: stepChanged 通知 & __rnLessonNext 公開
  const goNextRef = useRef(goNext);
  goNextRef.current = goNext;
  useEffect(() => {
    if (!isEmbed || typeof window === "undefined") return;
    (window as any).__rnLessonNext = () => goNextRef.current();
    return () => { delete (window as any).__rnLessonNext; };
  }, [isEmbed]);

  useEffect(() => {
    if (!isEmbed || !step) return;
    postToRn({
      type: "stepChanged",
      stepIndex,
      totalSteps: steps.length,
      title: step.title ?? title,
      description: currentPrompt,
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEmbed, stepIndex, guidedSubIndex, practiceIndex, reviewIndex]);

  if (!step) return <div className="p-10">読み込み中...</div>;

  const isBoardReady = Array.isArray(board) && board.length === 9;
  // embed mode: board only
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
              key={`${stepIndex}-${guidedSubIndex}-${practiceIndex}-${reviewIndex}`}
              board={isBoardReady ? board : createEmptyBoard()}
              hands={hands}
              mode="edit"
              onMove={handleMove}
              onBoardChange={setBoard}
              onHandsChange={setHands}
              orientation={orientation}
              showCoordinates={false}
              showHands={true}
              handsPlacement="default"
              compactHands={true}
              hintSquares={hintSquares}
              hintArrows={visibleHintArrows as any}
            />
          </WoodBoardFrame>
        </AutoScaleToFit>
        </div>
      </>
    );
  }

  const boardElementDesktop = (
    <div className="w-full h-full flex items-start justify-center overflow-auto">
      <div
        className="w-full pb-10"
        style={{
          maxWidth: 760,
          aspectRatio: "1 / 1",
          minHeight: isDesktop ? 560 : 360,
        }}
      >
        <AutoScaleToFit minScale={0.7} maxScale={1.45} className="w-full h-full">
          <WoodBoardFrame paddingClassName="p-3" className="inline-block">
            <div className="relative inline-block">
              <ShogiBoard
                board={board}
                hands={hands}
                mode="edit"
                onMove={handleMove}
                onBoardChange={setBoard}
                onHandsChange={setHands}
                orientation={orientation}
                handsPlacement="corners"
                hintSquares={hintSquares}
                hintArrows={visibleHintArrows as any}
              />
            </div>
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
                mode="edit"
                onMove={handleMove}
                onBoardChange={setBoard}
                onHandsChange={setHands}
                orientation={orientation}
                handsPlacement="corners"
                showCoordinates={false}
                hintSquares={hintSquares}
                hintArrows={visibleHintArrows as any}
              />
            </div>
          </WoodBoardFrame>
        </AutoScaleToFit>
      </div>
    </div>
  );

  const stepLabel = (() => {
    if (step.type === "guided") return "GUIDE";
    if (step.type === "practice") return "PRACTICE";
    return "REVIEW";
  })();

  if (isMobileWebView) {
    const canHint = step.type === "practice" || step.type === "review";
    const canReset = step.type === "practice" || step.type === "review";
    const mascot = (
      <ManRive
        correctSignal={correctSignal}
        className="bg-transparent [&>canvas]:bg-transparent"
        style={{ width: 210, height: 210 }}
      />
    );

    const explanation = (
      <MobileCoachText tag={stepLabel} text={currentPrompt} isCorrect={isCorrect} correctText="正解！次へ進もう。" />
    );

    const nextCta = canShowNextButton ? (
      <MobilePrimaryCTA onClick={goNext} />
    ) : reserveMobileCtaSpace ? (
      <div className="w-full h-[56px]" aria-hidden />
    ) : null;

    const actions = (
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          {canHint ? (
            <button
              onClick={() => setHintEnabled((v) => !v)}
              className="px-4 py-2 rounded-full bg-rose-50 text-rose-700 font-extrabold text-xs border border-rose-200 active:scale-[0.99]"
            >
              {hintEnabled ? "ヒントOFF" : "ヒント"}
            </button>
          ) : null}

          {canReset ? (
            <button
              onClick={resetCurrentPosition}
              className="px-4 py-2 rounded-full bg-slate-50 text-slate-700 font-extrabold text-xs border border-slate-200 active:scale-[0.99]"
            >
              戻す
            </button>
          ) : null}
        </div>

        {nextCta}
      </div>
    );

    return (
      <MobileLessonShell
        mascot={mascot}
        explanation={explanation}
        actions={actions}
        board={boardElementMobile}
        explanationHeightPx={mobileExplanationHeightPx}
      />
    );
  }

  const explanationElement = (
    <div className="bg-white/80 backdrop-blur rounded-2xl shadow border border-black/10 p-4">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
        <span>{stepLabel}</span>
        <span className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
          <span className="block h-full bg-emerald-500 transition-all duration-500" style={{ width: `${progress01 * 100}%` }} />
        </span>
        <span>{steps.length}</span>
      </div>

      <div className="mt-3">
        <h1 className="text-xl font-bold text-[#3a2b17]">{step.title ?? title}</h1>

        <div className="mt-3 flex items-start gap-3 bg-amber-50/80 p-3 rounded-2xl text-amber-900 border border-amber-200/50">
          <Lightbulb className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="leading-relaxed font-medium text-sm whitespace-pre-wrap">{currentPrompt}</p>
        </div>

        {isCorrect && (
          <div className="animate-in fade-in zoom-in-95 duration-300 mt-4">
            <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 text-center">
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 mb-2">
                <CheckCircle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-emerald-800 mb-1">Excellent!</h3>
            </div>
          </div>
        )}

        {isDesktop && nextButton}
        {isDesktop && hintButton}
        {isDesktop && resetButton}
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

  return (
    <LessonScaffold
      title={title}
      backHref={backHref}
      board={boardElementDesktop}
      explanation={explanationElement}
      mascot={mascotElement}
      mascotOverlay={null}
      topLabel={topLabel}
      progress01={progress01}
      headerRight={headerRight}
      desktopMinWidthPx={desktopMinWidthPx}
      mobileAction={
        !isDesktop ? (
          <div>
            {nextButton}
            {hintButton}
            {resetButton}
          </div>
        ) : null
      }
    />
  );
}


