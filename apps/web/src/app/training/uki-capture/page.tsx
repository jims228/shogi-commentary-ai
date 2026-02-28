"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Lightbulb } from "lucide-react";

import { LessonScaffold } from "@/components/training/lesson/LessonScaffold";
import { ManRive } from "@/components/ManRive";
import { AutoScaleToFit } from "@/components/training/AutoScaleToFit";
import { WoodBoardFrame } from "@/components/training/WoodBoardFrame";
import { useMediaQuery } from "@/hooks/useMediaQuery";

import { UkiCaptureShogiGame, type UkiCaptureResult } from "@/components/training/minigames/UkiCaptureShogiGame";
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { useMobileParams } from "@/hooks/useMobileQueryParam";

function postToRn(msg: { type: string; [k: string]: unknown }) {
  try {
    const w = typeof window !== "undefined" ? (window as any) : null;
    if (w?.ReactNativeWebView?.postMessage) w.ReactNativeWebView.postMessage(JSON.stringify(msg));
  } catch { /* ignore */ }
}

export default function UkiCapturePage() {
  const isDesktop = useMediaQuery("(min-width: 820px)");
  const { mobile: isMobileWebView, embed: isEmbed } = useMobileParams();

  const [correctSignal, setCorrectSignal] = useState(0);
  const [secLeft, setSecLeft] = useState(60);
  const [score, setScore] = useState<UkiCaptureResult>({ gain: 0, loss: 0, net: 0, captures: 0 });

  const prevCapturesRef = useRef(0);
  const completeSentRef = useRef(false);

  const onTick = useCallback((s: number) => {
    setSecLeft(s);
    if (s <= 0 && isEmbed && !completeSentRef.current) {
      completeSentRef.current = true;
      postMobileLessonCompleteOnce();
      postToRn({ type: "lessonComplete" });
    }
  }, [isEmbed]);
  const onScore = useCallback((r: UkiCaptureResult) => {
    setScore(r);
    if (r.captures > prevCapturesRef.current) {
      setCorrectSignal((v) => v + 1);
      if (isEmbed) postToRn({ type: "lessonCorrect" });
    }
    prevCapturesRef.current = r.captures;
  }, [isEmbed]);

  // embed: 初期stepChanged送信
  useEffect(() => {
    if (!isEmbed) return;
    postToRn({ type: "stepChanged", stepIndex: 0, totalSteps: 1, title: "浮き駒を取る", description: "操作駒は飛車。守られていない浮き駒を素早く取ろう！" });
  }, [isEmbed]);

  // 左カラム（盤）: Scaffoldが与える高さに必ず収める
  const boardElement = (
    <div className="w-full h-full min-h-0 flex items-center justify-center">
      <div className="w-full h-full min-h-0" style={{ maxWidth: 860 }}>
        <AutoScaleToFit minScale={0.42} maxScale={1.2} className="w-full h-full">
          <WoodBoardFrame paddingClassName="p-2" className="inline-block">
            <UkiCaptureShogiGame
              durationSec={60}
              targetCount={4}
              playerPiece="R"
              playerStart={{ x: 4, y: 7 }}
              onTick={onTick}
              onScore={onScore}
            />
          </WoodBoardFrame>
        </AutoScaleToFit>
      </div>
    </div>
  );

  const boardElementMobile = (
    <div className="w-full h-full min-h-0 flex items-center justify-center">
      <div className="w-full h-full aspect-square -translate-y-2">
        <AutoScaleToFit minScale={0.42} maxScale={2.4} className="w-full h-full">
          <WoodBoardFrame paddingClassName="p-1" className="w-full h-full">
            <div className="relative w-full h-full">
              <UkiCaptureShogiGame
                durationSec={60}
                targetCount={4}
                playerPiece="R"
                playerStart={{ x: 4, y: 7 }}
                onTick={onTick}
                onScore={onScore}
              />
            </div>
          </WoodBoardFrame>
        </AutoScaleToFit>
      </div>
    </div>
  );

  const explanationElement = (
    <div className="bg-white/80 backdrop-blur rounded-2xl shadow border border-black/10 p-4">
      <h1 className="text-xl font-bold text-[#3a2b17]">浮き駒を取る（60秒）</h1>

      <div className="mt-3 flex items-start gap-3 bg-amber-50/80 p-3 rounded-2xl text-amber-900 border border-amber-200/50">
        <Lightbulb className="w-5 h-5 shrink-0 mt-0.5" />
        <p className="leading-relaxed font-medium text-sm">
          操作駒は <b>飛車</b> です。遠くの駒も狙えます。<br />
          守られていない「浮き駒」を素早く取ろう。<br />
          取れる浮き駒が0なら救済で相手駒が1枚ワープします。<br />
          相手の利きの中に自分の飛車を置くと「取られる扱い（駒損）」です。
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl border bg-white p-3">
          <div className="text-xs text-slate-500 font-bold">TIME LEFT</div>
          <div className="text-2xl font-extrabold text-[#3a2b17]">{secLeft}s</div>
        </div>

        <div className="rounded-2xl border bg-white p-3">
          <div className="text-xs text-slate-500 font-bold">SCORE</div>
          <div className="text-sm mt-1 text-slate-700">
            駒得 <span className="font-extrabold text-emerald-700">{score.gain}</span> / 駒損{" "}
            <span className="font-extrabold text-rose-700">{score.loss}</span>
          </div>
          <div className="text-2xl font-extrabold text-[#3a2b17] mt-1">Net {score.net}</div>
          <div className="text-xs text-slate-500 mt-1">Capture {score.captures}</div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-white p-3">
        <div className="text-xs text-slate-500 font-bold">POINT TABLE</div>
        <div className="mt-2 text-sm text-slate-700 space-y-1">
          <div>飛 100 / 角 80</div>
          <div>金 60 / 銀 50</div>
          <div>桂・香 30 / 歩 10</div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-white p-3">
        <div className="text-xs text-slate-500 font-bold">ルール</div>
        <ul className="mt-2 list-disc pl-5 text-sm text-slate-700 space-y-1">
          <li>動かせるのは自分の練習駒（飛車）だけ</li>
          <li>利きに沿わない移動は無効（戻されます）</li>
          <li>相手の利きの中に置くと「取られる扱い（駒損）」で減点＆初期位置に戻ります</li>
        </ul>
      </div>

      {/* Mobile MVP: provide an explicit "complete" button when the timer ends */}
      {isMobileWebView && secLeft <= 0 ? (
        <button
          onClick={() => postMobileLessonCompleteOnce()}
          className="mt-4 w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold shadow-lg shadow-emerald-900/20 transition-all active:scale-95"
        >
          完了して戻る
        </button>
      ) : null}
    </div>
  );

  // 中カラム（おじいちゃん）: 高さ内で下に揃える
  const mascotElement = (
    <div className="w-full h-full min-h-0 flex items-end justify-center pb-2">
      <ManRive
        correctSignal={correctSignal}
        className="bg-transparent [&>canvas]:bg-transparent"
        style={{
          width: isDesktop ? 360 : 260,
          height: isDesktop ? 360 : 260,
        }}
      />
    </div>
  );

  const mascotOverlay =
    score.captures > 0 ? (
      <div className="bg-white/95 border border-emerald-100 rounded-2xl p-3 shadow-md w-56">
        <h3 className="text-sm font-bold text-emerald-800">Nice!</h3>
        <p className="text-sm text-emerald-700 mt-1">
          Net {score.net} / 残り {secLeft}s
        </p>
      </div>
    ) : null;

  if (isEmbed) {
    return (
      <div className="w-full h-full flex items-center justify-center p-2">
        <div className="aspect-square" style={{ width: "100%", maxWidth: "100vh", maxHeight: "100%" }}>
          <AutoScaleToFit minScale={0.3} maxScale={2.4} className="w-full h-full" overflowHidden={false}>
            <WoodBoardFrame paddingClassName="p-0" className="overflow-hidden">
              <UkiCaptureShogiGame
                durationSec={60}
                targetCount={4}
                playerPiece="R"
                playerStart={{ x: 4, y: 7 }}
                onTick={onTick}
                onScore={onScore}
              />
            </WoodBoardFrame>
          </AutoScaleToFit>
        </div>
      </div>
    );
  }

  if (isMobileWebView) {
    // NOTE: This is a minigame (not LessonRunner). We still unify the mobile layout (coach + board + CTA),
    // but completion is handled by `postMobileLessonCompleteOnce()` only; the mobile app navigates back.
    const coachText =
      "操作駒は飛車。守られていない「浮き駒」を素早く取ろう。\n相手の利きに入ると駒損（減点）です。";

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
          <div className="flex flex-col gap-3">
            <MobileCoachText tag="UKI CAPTURE" text={coachText} isCorrect={false} />
            <div className="flex items-center gap-3">
              <div className="rounded-xl border bg-white px-3 py-2">
                <div className="text-[11px] font-extrabold text-slate-500">TIME</div>
                <div className="text-[16px] font-extrabold text-slate-900">{secLeft}s</div>
              </div>
              <div className="rounded-xl border bg-white px-3 py-2">
                <div className="text-[11px] font-extrabold text-slate-500">NET</div>
                <div className="text-[16px] font-extrabold text-slate-900">{score.net}</div>
              </div>
            </div>
          </div>
        }
        actions={
          secLeft <= 0 ? (
            <MobilePrimaryCTA label="完了" onClick={() => postMobileLessonCompleteOnce()} />
          ) : null
        }
        board={boardElementMobile}
      />
    );
  }

  return (
    <LessonScaffold
      title="駒の効き：浮き駒を取る"
      backHref="/learn/roadmap"
      board={boardElement}
      explanation={explanationElement}
      mascot={mascotElement}
      mascotOverlay={mascotOverlay}
      topLabel="TIMED PRACTICE"
      progress01={1}
      headerRight={<span className="font-bold">Net {score.net}</span>}
      desktopMinWidthPx={820}
      desktopLayout="threeCol"
      mobileAction={null}
    />
  );
}
