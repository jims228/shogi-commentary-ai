"use client";

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, ArrowRight, Lightbulb } from "lucide-react";

import { ShogiBoard } from "@/components/ShogiBoard";
import type { PieceMotionRule } from "@/components/ShogiBoard";
import { ManRive } from "@/components/ManRive";
import { AutoScaleToFit } from "@/components/training/AutoScaleToFit";
import { WoodBoardFrame } from "@/components/training/WoodBoardFrame";
import { LessonScaffold } from "@/components/training/lesson/LessonScaffold";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";

import {
  DEFAULT_SHOGI_RULES_LESSON_ID,
  SHOGI_RULES_LESSON_STEPS,
} from "@/constants/rulesData";
import { showToast } from "@/components/ui/toast";
import { buildPositionFromUsi, createEmptyBoard } from "@/lib/board";
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { useMobileParams } from "@/hooks/useMobileQueryParam";
import { shogiToDisplay } from "@/lib/arrowGeometry";

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

const normalizeUsiPosition = (s: string) => {
  const t = (s ?? "").trim();
  if (!t) return "position startpos";
  if (t.startsWith("position ")) return t;
  if (t.startsWith("startpos")) return `position ${t}`;
  if (t.startsWith("sfen ")) return `position ${t}`;
  return `position sfen ${t}`;
};

const normalizeHands = (hands: any) => ({
  b: { ...(hands?.b ?? {}) },
  w: { ...(hands?.w ?? {}) },
});

function postToRn(msg: { type: string; [k: string]: unknown }) {
  try {
    const w = typeof window !== "undefined" ? (window as any) : null;
    if (w?.ReactNativeWebView?.postMessage) w.ReactNativeWebView.postMessage(JSON.stringify(msg));
  } catch {
    // ignore
  }
}

const STEP1_GUIDE_IMAGE_STYLE = {
  desktop: { top: 360, gap: 24, height: 234 },
  mobile: { top: 278, gap: 16, height: 156 },
  embed: { top: 252, gap: 14, height: 138 },
} as const;

export default function RulesTrainingPage() {
  const router = useRouter();
  const { mobile: isMobileWebView, embed: isEmbed, lid } = useMobileParams();

  const lessonId =
    lid && SHOGI_RULES_LESSON_STEPS[lid] ? lid : DEFAULT_SHOGI_RULES_LESSON_ID;
  const steps = SHOGI_RULES_LESSON_STEPS[lessonId] ?? SHOGI_RULES_LESSON_STEPS[DEFAULT_SHOGI_RULES_LESSON_ID];

  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [board, setBoard] = useState<any[][]>(() => createEmptyBoard());
  const [hands, setHands] = useState<any>({ b: {}, w: {} });
  const [isCorrect, setIsCorrect] = useState(false);
  const [correctSignal, setCorrectSignal] = useState(0);
  const [coachComment, setCoachComment] = useState<string | null>(null);
  const [activeChoice, setActiveChoice] = useState<{ prompt: string; options: { label: string; correct: boolean }[] } | null>(null);
  const [interactionLocked, setInteractionLocked] = useState(false);
  const [scriptPhaseIndex, setScriptPhaseIndex] = useState(0);
  const postCorrectTimersRef = useRef<number[]>([]);

  // ── ハイドレーションガード ──
  // SSR HTMLに誤レイアウト（web版）を出さない。
  // useLayoutEffectはブラウザ描画前に発火するため、
  // ユーザーにはshell→正しいレイアウトのみ見える。
  const [hydrated, setHydrated] = useState(false);
  useIsomorphicLayoutEffect(() => { setHydrated(true); }, []);

  const currentLesson = steps[currentStepIndex];
  const scriptPhases = currentLesson?.scriptPhases ?? [];
  const activeScriptPhase = scriptPhases.length > 0
    ? scriptPhases[Math.min(scriptPhaseIndex, scriptPhases.length - 1)]
    : null;
  const visibleHintArrows = (isCorrect || !!coachComment)
    ? []
    : (activeScriptPhase?.hintArrows ?? currentLesson?.hintArrows ?? []);
  const visibleHintStars = (isCorrect || !!coachComment)
    ? []
    : (activeScriptPhase?.hintStars ?? currentLesson?.hintStars ?? []);
  const successCoachText = coachComment ?? currentLesson?.successMessage ?? "";
  const coachBubbleText = coachComment ?? currentLesson?.description ?? "";
  const onCorrectPieceMotionRules: PieceMotionRule[] = (() => {
    if (!(isCorrect || !!coachComment)) return [];
    const defs = currentLesson?.onCorrectPieceMotions ?? [];
    return defs.map((d, idx) => {
      const p = shogiToDisplay(d.target.file, d.target.rank, false);
      return {
        match: {
          x: p.x,
          y: p.y,
          owner: d.target.owner,
          piece: d.target.piece,
          pieceBase: d.target.pieceBase,
        },
        motion: {
          type: d.motion.type,
          amplitudePx: d.motion.amplitudePx,
          durationMs: d.motion.durationMs,
          delayMs: d.motion.delayMs,
          repeat: d.motion.repeat,
        },
      } as PieceMotionRule;
    });
  })();
  const showStep1TopImages =
    lessonId === "rules_00_board_pieces_win" &&
    (currentStepIndex === 0 || currentStepIndex === 1 || currentStepIndex === 2);

  const renderStep1GuideImages = (preset: (typeof STEP1_GUIDE_IMAGE_STYLE)[keyof typeof STEP1_GUIDE_IMAGE_STYLE]) => {
    if (!showStep1TopImages) return null;
    return (
      <div
        className="pointer-events-none absolute left-1/2 z-40 -translate-x-1/2 flex items-center justify-center"
        style={{ top: preset.top, gap: preset.gap }}
      >
        <img
          src="/images/lesson/gold-move.png"
          alt="金の動き"
          className="block w-auto shrink-0 object-contain"
          style={{ height: preset.height, width: "auto" }}
        />
        <img
          src="/images/lesson/king-move.png"
          alt="王の動き"
          className="block w-auto shrink-0 object-contain"
          style={{ height: preset.height, width: "auto" }}
        />
      </div>
    );
  };

  useEffect(() => {
    if (!currentLesson) return;
    // step切替時に正解後デモタイマーをクリア
    postCorrectTimersRef.current.forEach((id) => window.clearTimeout(id));
    postCorrectTimersRef.current = [];
    setCoachComment(null);
    setActiveChoice(null);
    setInteractionLocked(false);
    setScriptPhaseIndex(0);

    try {
      const initialSfen = currentLesson.scriptPhases?.[0]?.sfen ?? currentLesson.sfen;
      const initial = buildPositionFromUsi(normalizeUsiPosition(initialSfen));
      setBoard(initial.board);
      setHands(normalizeHands((initial as any).hands));
    } catch (e) {
      console.error("SFEN Parse Error", e);
    }
    setIsCorrect(false);
    if (isEmbed) {
      postToRn({
        type: "stepChanged",
        stepIndex: currentStepIndex,
        totalSteps: steps.length,
        title: currentLesson.title,
        description: currentLesson.description,
      });
    }
  }, [currentLesson, currentStepIndex, isEmbed, steps.length]);

  const handleMove = useCallback(
    (move: { from?: { x: number; y: number }; to: { x: number; y: number }; piece: string; drop?: boolean }) => {
      if (activeChoice || isCorrect || interactionLocked) return;

      const activeCheckMove = activeScriptPhase?.checkMove ?? currentLesson.checkMove;

      const isDemoMove = currentLesson.demoMoveCheck?.(move as any) ?? false;

      if (isDemoMove) {
        setInteractionLocked(true);
        // 正解にはしない。解説演出のみ実行。
        postCorrectTimersRef.current.forEach((id) => window.clearTimeout(id));
        postCorrectTimersRef.current = [];
        const demo = currentLesson.postCorrectDemo ?? [];
        let elapsed = 0;
        demo.forEach((frame) => {
          elapsed += frame.delayMs ?? 0;
          const tid = window.setTimeout(() => {
            if (frame.comment) {
              setCoachComment(frame.comment);
              if (isEmbed) {
                postToRn({
                  type: "stepChanged",
                  stepIndex: currentStepIndex,
                  totalSteps: steps.length,
                  title: currentLesson.title,
                  description: frame.comment,
                });
              }
            }
            if (frame.sfen) {
              try {
                const next = buildPositionFromUsi(normalizeUsiPosition(frame.sfen));
                setBoard(next.board);
                setHands(normalizeHands((next as any).hands));
              } catch {
                // ignore malformed demo sfen
              }
            }
            if (frame.markCorrect) {
              setIsCorrect(true);
              setCorrectSignal((v) => v + 1);
              if (isEmbed) {
                postToRn({
                  type: "stepChanged",
                  stepIndex: currentStepIndex,
                  totalSteps: steps.length,
                  title: currentLesson.title,
                  description: frame.comment ?? currentLesson.successMessage,
                });
              }
              if (isEmbed) postToRn({ type: "lessonCorrect" });
              else if (!isMobileWebView) showToast({ title: "正解！", description: currentLesson.successMessage });
            }
          }, elapsed);
          postCorrectTimersRef.current.push(tid);
        });
        return;
      }

      // 選択問題付きステップ: 指定手を指したら二択を表示（この時点では正解にしない）
      if (currentLesson.choiceQuestion) {
        const trigger = currentLesson.checkMove(move as any);
        if (trigger) {
          setActiveChoice(currentLesson.choiceQuestion);
          setCoachComment(currentLesson.choiceQuestion.prompt);
          setInteractionLocked(true);
          return;
        }
      }

      const correct = activeCheckMove(move as any);

      if (correct) {
        if (activeScriptPhase) {
          if (activeScriptPhase.successMessage) setCoachComment(activeScriptPhase.successMessage);
          const nextPhaseIndex = scriptPhaseIndex + 1;
          if (nextPhaseIndex < scriptPhases.length) {
            const applyNextPhase = () => {
              try {
                const next = buildPositionFromUsi(normalizeUsiPosition(scriptPhases[nextPhaseIndex].sfen));
                setBoard(next.board);
                setHands(normalizeHands((next as any).hands));
              } catch {
                // ignore malformed phase sfen
              }
              setScriptPhaseIndex(nextPhaseIndex);
              setInteractionLocked(false);
            };

            const delayMs = Math.max(0, Number((scriptPhases[nextPhaseIndex] as any)?.delayMs ?? 0));
            if (delayMs > 0) {
              setInteractionLocked(true);
              const tid = window.setTimeout(() => {
                applyNextPhase();
              }, delayMs);
              postCorrectTimersRef.current.push(tid);
            } else {
              applyNextPhase();
            }
            return;
          }
        }

        setCoachComment(currentLesson.successMessage);
        setIsCorrect(true);
        setCorrectSignal((v) => v + 1);
        setInteractionLocked(true);
        if (isEmbed) {
          postToRn({
            type: "stepChanged",
            stepIndex: currentStepIndex,
            totalSteps: steps.length,
            title: currentLesson.title,
            description: currentLesson.successMessage,
          });
        }

        // 正解後デモ（コメント更新/盤面更新）を順次再生
        postCorrectTimersRef.current.forEach((id) => window.clearTimeout(id));
        postCorrectTimersRef.current = [];
        const demo = currentLesson.postCorrectDemo ?? [];
        let elapsed = 0;
        demo.forEach((frame) => {
          elapsed += frame.delayMs ?? 0;
          const tid = window.setTimeout(() => {
            if (frame.comment) {
              setCoachComment(frame.comment);
              if (isEmbed) {
                postToRn({
                  type: "stepChanged",
                  stepIndex: currentStepIndex,
                  totalSteps: steps.length,
                  title: currentLesson.title,
                  description: frame.comment,
                });
              }
            }
            if (frame.sfen) {
              try {
                const next = buildPositionFromUsi(normalizeUsiPosition(frame.sfen));
                setBoard(next.board);
                setHands(normalizeHands((next as any).hands));
              } catch {
                // ignore malformed demo sfen
              }
            }
            if (frame.markCorrect) {
              setIsCorrect(true);
              setCorrectSignal((v) => v + 1);
              if (isEmbed) {
                postToRn({
                  type: "stepChanged",
                  stepIndex: currentStepIndex,
                  totalSteps: steps.length,
                  title: currentLesson.title,
                  description: frame.comment ?? currentLesson.successMessage,
                });
              }
              if (isEmbed) postToRn({ type: "lessonCorrect" });
              else if (!isMobileWebView) showToast({ title: "正解！", description: currentLesson.successMessage });
            }
          }, elapsed);
          postCorrectTimersRef.current.push(tid);
        });

        if (isEmbed) postToRn({ type: "lessonCorrect" });
        else if (!isMobileWebView) showToast({ title: "正解！", description: currentLesson.successMessage });
      } else {
        setCoachComment(null);
        if (isEmbed) postToRn({ type: "lessonWrong" });
        else showToast({ title: "惜しい！", description: "その手ではありません。もう一度考えてみましょう。" });

        setTimeout(() => {
          const initialSfen = activeScriptPhase?.sfen ?? currentLesson.sfen;
          const initial = buildPositionFromUsi(normalizeUsiPosition(initialSfen));
          setBoard(initial.board);
          setHands(normalizeHands((initial as any).hands));
        }, 700);
      }
    },
    [
      activeChoice,
      activeScriptPhase,
      currentLesson,
      interactionLocked,
      isCorrect,
      isEmbed,
      isMobileWebView,
      scriptPhaseIndex,
      scriptPhases,
    ],
  );

  const handleChoiceAnswer = useCallback((correct: boolean) => {
    if (!activeChoice) return;

    if (correct) {
      setCoachComment(currentLesson.successMessage);
      setIsCorrect(true);
      setCorrectSignal((v) => v + 1);
      setActiveChoice(null);
      setInteractionLocked(true);
      if (isEmbed) {
        postToRn({
          type: "stepChanged",
          stepIndex: currentStepIndex,
          totalSteps: steps.length,
          title: currentLesson.title,
          description: currentLesson.successMessage,
        });
      }
      if (isEmbed) postToRn({ type: "lessonCorrect" });
      else if (!isMobileWebView) showToast({ title: "正解！", description: currentLesson.successMessage });
      return;
    }

    if (isEmbed) postToRn({ type: "lessonWrong" });
    else showToast({ title: "惜しい！", description: "もう一度選んでみよう。" });
  }, [activeChoice, currentLesson, isEmbed, isMobileWebView]);

  const boardChoiceDialog = activeChoice && !isCorrect
    ? {
        prompt: activeChoice.prompt,
        options: [
          {
            label: activeChoice.options[0]?.label ?? "",
            onSelect: () => handleChoiceAnswer(Boolean(activeChoice.options[0]?.correct)),
          },
          {
            label: activeChoice.options[1]?.label ?? "",
            onSelect: () => handleChoiceAnswer(Boolean(activeChoice.options[1]?.correct)),
          },
        ] as [
          { label: string; onSelect: () => void },
          { label: string; onSelect: () => void },
        ],
      }
    : null;

  const choicePanel = boardChoiceDialog
    ? (() => {
        const btnSize = "clamp(160px, 43vw, 240px)";
        return (
          <div
            className="mx-auto"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 12,
            }}
          >
            <div
              style={{
                maxWidth: 420,
                background: "rgba(255,247,237,0.96)",
                border: "2px solid #f59e0b",
                borderRadius: 14,
                padding: "10px 14px",
                color: "#7c2d12",
                fontWeight: 800,
                textAlign: "center",
                boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
              }}
            >
              {boardChoiceDialog.prompt}
            </div>

            <div style={{ display: "flex", gap: 12 }}>
              {boardChoiceDialog.options.map((opt) => (
                <button
                  key={opt.label}
                  type="button"
                  style={{
                    width: btnSize,
                    height: btnSize,
                    minWidth: 160,
                    minHeight: 160,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "#fef3c7",
                    border: "3px solid #d97706",
                    borderRadius: 20,
                    cursor: "pointer",
                    userSelect: "none",
                    WebkitUserSelect: "none",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
                    fontWeight: 900,
                    color: "#7c2d12",
                    fontSize: 22,
                    lineHeight: 1.2,
                    textAlign: "center",
                    padding: 10,
                    whiteSpace: "nowrap",
                  }}
                  onClick={opt.onSelect}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        );
      })()
    : null;

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) setCurrentStepIndex((p) => p + 1);
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
    return () => {
      delete (window as any).__rnLessonNext;
    };
  }, [isEmbed]);

  // SSR HTML / ハイドレーション前: ページ背景色のみ表示（誤レイアウトを防止）
  if (!hydrated) return <div className="min-h-[100svh] w-full bg-[#f6f1e7]" />;
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
        <div className="w-full h-full flex flex-col items-center justify-center gap-2 p-2 bg-transparent">
          <div className="relative w-full h-full">
            {renderStep1GuideImages(STEP1_GUIDE_IMAGE_STYLE.embed)}
            <AutoScaleToFit
              minScale={0.25}
              maxScale={2.4}
              fitMode="width-only"
              className="w-full h-full"
              overflowHidden={true}
            >
              <WoodBoardFrame paddingClassName="p-1">
                <ShogiBoard
                  key={`${lessonId}-${currentStepIndex}`}
                  board={isBoardReady ? board : createEmptyBoard()}
                  hands={hands}
                  hintStars={visibleHintStars}
                  hintArrows={visibleHintArrows}
                  pieceMotionRules={onCorrectPieceMotionRules}
                  interactionDisabled={interactionLocked}
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
          {choicePanel ? (
            <div className="fixed inset-x-2 z-[9999]" style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 80px)" }}>
              {choicePanel}
            </div>
          ) : null}
        </div>
      </>
    );
  }

  const nextButton = isCorrect ? (
    <button
      onClick={handleNext}
      className="mt-3 w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 transition-all active:scale-95"
    >
      {currentStepIndex < steps.length - 1 ? "次のステップへ" : "レッスン完了！"}
      <ArrowRight className="w-5 h-5" />
    </button>
  ) : null;

  const boardElement = (
    <div className="w-full h-full flex flex-col items-center justify-center gap-3">
      <div className="relative w-full min-h-[360px] min-[820px]:min-h-[560px]" style={{ maxWidth: 760, aspectRatio: "1 / 1" }}>
        {renderStep1GuideImages(STEP1_GUIDE_IMAGE_STYLE.desktop)}
        <AutoScaleToFit minScale={0.7} maxScale={1.45} className="w-full h-full">
          <WoodBoardFrame paddingClassName="p-3" className="inline-block">
            <ShogiBoard
              board={board}
              hands={hands}
              hintStars={visibleHintStars}
              hintArrows={visibleHintArrows}
              pieceMotionRules={onCorrectPieceMotionRules}
              interactionDisabled={interactionLocked}
              choiceDialog={boardChoiceDialog}
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
    <div className="w-full h-full min-h-0 flex flex-col items-center justify-center gap-2">
      <div className="relative w-full h-full aspect-square -translate-y-2">
        {renderStep1GuideImages(STEP1_GUIDE_IMAGE_STYLE.mobile)}
        <AutoScaleToFit minScale={0.5} maxScale={2.4} className="w-full h-full">
          <WoodBoardFrame paddingClassName="p-1" className="w-full h-full">
            <ShogiBoard
              board={board}
              hands={hands}
              hintStars={visibleHintStars}
              hintArrows={visibleHintArrows}
              pieceMotionRules={onCorrectPieceMotionRules}
              interactionDisabled={interactionLocked}
              mode="edit"
              onMove={handleMove}
              onBoardChange={setBoard}
              onHandsChange={setHands}
              orientation="sente"
              handsPlacement="corners"
              showCoordinates={false}
            />
          </WoodBoardFrame>
        </AutoScaleToFit>
      </div>
    </div>
  );

  const explanationElement = (
    <div className="bg-white/80 backdrop-blur rounded-2xl shadow border border-black/10 p-4">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
        <span>RULES STEP {currentStepIndex + 1}</span>
        <span className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
          <span className="block h-full bg-emerald-500 transition-all duration-500" style={{ width: `${((currentStepIndex + 1) / steps.length) * 100}%` }} />
        </span>
        <span>{steps.length}</span>
      </div>

      <div className="mt-3">
        <h1 className="text-xl font-bold text-[#3a2b17]">{currentLesson.title}</h1>
        <div className="mt-3 flex items-start gap-3 bg-amber-50/80 p-3 rounded-2xl text-amber-900 border border-amber-200/50">
          <Lightbulb className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="leading-relaxed font-medium text-sm">{coachBubbleText}</p>
        </div>

        {isCorrect && (
          <div className="animate-in fade-in zoom-in-95 duration-300 mt-4">
            <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 text-center">
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 mb-2">
                <CheckCircle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-emerald-800 mb-1">Excellent!</h3>
              <p className="text-emerald-700 text-sm">{successCoachText}</p>
            </div>
          </div>
        )}

        {nextButton && <div className="hidden min-[820px]:block">{nextButton}</div>}
      </div>
    </div>
  );

  const mascotElement = (
    <div style={{ transform: "translateY(-12px)" }}>
      <div className="w-[260px] h-[260px] min-[820px]:w-[380px] min-[820px]:h-[380px]">
        <ManRive
          correctSignal={correctSignal}
          className="bg-transparent [&>canvas]:bg-transparent"
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );

  const mascotOverlay = isCorrect ? (
    <div className="bg-white/95 border border-emerald-100 rounded-2xl p-3 shadow-md w-56">
      <h3 className="text-sm font-bold text-emerald-800">正解！</h3>
      <p className="text-sm text-emerald-700 mt-1">{successCoachText}</p>
    </div>
  ) : null;

  if (isMobileWebView) {
    return (
      <>
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
              tag={`RULES ${currentStepIndex + 1}/${steps.length}`}
              text={coachBubbleText}
              isCorrect={isCorrect}
              correctText={successCoachText || "正解！次へ進もう。"}
            />
          }
          actions={isCorrect ? <MobilePrimaryCTA onClick={handleNext} /> : null}
          board={boardElementMobile}
        />
        {choicePanel ? (
          <div className="fixed inset-x-2 z-[9999]" style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 80px)" }}>
            {choicePanel}
          </div>
        ) : null}
      </>
    );
  }

  return (
    <LessonScaffold
      title="将棋のルール"
      backHref="/learn/roadmap"
      board={boardElement}
      explanation={explanationElement}
      mascot={mascotElement}
      mascotOverlay={mascotOverlay}
      topLabel="RULES"
      progress01={(currentStepIndex + 1) / steps.length}
      headerRight={<span>❤ 5</span>}
      desktopMinWidthPx={820}
      mobileAction={nextButton}
    />
  );
}

