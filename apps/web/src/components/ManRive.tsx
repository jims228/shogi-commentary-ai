'use client';

import React, { useEffect, useRef } from 'react';
import {
  Alignment,
  Fit,
  Layout,
  useRive,
  useStateMachineInput,
} from '@rive-app/react-canvas';

export type ManRiveProps = {
  /** 正解ごとにインクリメントされる値（値が変わるたびに驚きTriggerを発火） */
  correctSignal: number;
  className?: string;
  style?: React.CSSProperties;
};

export function ManRive({ correctSignal, className, style }: ManRiveProps) {
  const { rive, RiveComponent } = useRive({
    src: '/anime/man.riv',
    stateMachines: 'Main',
    autoplay: true,
    layout: new Layout({
      fit: Fit.Contain,
      alignment: Alignment.BottomCenter,
    }),
  });

  const toSurprise = useStateMachineInput(rive, 'Main', 'toSurprise');

  // 初期値は「ベースライン」として扱い、そこからの変化で必ず発火させる
  // さらに、Triggerが後から準備できた場合でも取りこぼさないようにする
  const baselineRef = useRef<number | null>(null);
  const lastHandledRef = useRef<number | null>(null);

  useEffect(() => {
    if (baselineRef.current === null) baselineRef.current = correctSignal;

    if (!toSurprise) return;

    // 同じsignalは二重に処理しない
    if (lastHandledRef.current === correctSignal) return;

    // 初期値(ベースライン)以外になったら発火
    if (correctSignal !== baselineRef.current) {
      toSurprise.fire();
    }

    lastHandledRef.current = correctSignal;
  }, [correctSignal, toSurprise]);

  return (
    <div
      className={["bg-transparent [&>canvas]:bg-transparent", className].filter(Boolean).join(" ")}
      style={{
        width: 320,
        height: 320,
        ...style,
      }}
      aria-label="Rive character"
    >
      <RiveComponent />
    </div>
  );
}
