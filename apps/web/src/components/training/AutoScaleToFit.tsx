"use client";

import React, { useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type AutoScaleToFitProps = {
  minScale?: number;      // 下限
  maxScale?: number;      // 上限（1より大きくできる）
  fitMode?: "both" | "width-only";  // width だけでフィットするモード
  className?: string;
  /** false にすると overflow-hidden を外す（embed モードで border が切れるのを防ぐ） */
  overflowHidden?: boolean;
  children: React.ReactNode;
};

type Size = { width: number; height: number };

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

export function AutoScaleToFit({
  minScale = 0.6,
  maxScale = 1.35,
  fitMode = "both",  // デフォルトは両方
  className,
  overflowHidden = true,
  children,
}: AutoScaleToFitProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const lastValidScaleRef = useRef<number>(1);

  const [containerSize, setContainerSize] = useState<Size>({ width: 0, height: 0 });
  const [contentSize, setContentSize] = useState<Size>({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const containerEl = containerRef.current;
    const contentEl = contentRef.current;
    if (!containerEl || !contentEl) return;

    const readSizes = () => {
      const cw = containerEl.clientWidth;
      const ch = containerEl.clientHeight;
      const ow = contentEl.offsetWidth;
      const oh = contentEl.offsetHeight;
      setContainerSize({
        width: cw,
        height: ch,
      });

      // transformの影響を受けない"素の"サイズ
      setContentSize({
        width: ow,
        height: oh,
      });
    };

    readSizes();

    const observer = new ResizeObserver(() => readSizes());
    observer.observe(containerEl);
    observer.observe(contentEl);

    window.addEventListener("resize", readSizes);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", readSizes);
    };
  }, []);

  const { scale, scaledSize, bypassScale } = useMemo(() => {
    const availableW = containerSize.width;
    const availableH = containerSize.height;
    const contentW = contentSize.width;
    const contentH = contentSize.height;

    // 親サイズ或いは子サイズが 0 の場合の処理
    const parentSizeZero = availableW <= 0 || availableH <= 0;
    const parentAllZero = availableW <= 0 && availableH <= 0;
    const contentSizeZero = contentW <= 0 || contentH <= 0;

    // 0サイズ対策:
    // - content が 0 → まだ計測できていないのでスケール適用をバイパス（素で描画）
    // - 親が完全に 0 → absolute の shrink-to-fit が 0 に固定されやすいので同様にバイパス
    if (contentSizeZero || parentAllZero) {
      return {
        bypassScale: true,
        scale: 1,
        scaledSize: { width: 0, height: 0 },
      };
    }

    // 親が 0 の場合、fitMode に応じた処理
    if (parentSizeZero) {
      if (fitMode === "width-only" && availableW > 0) {
        // width だけでフィット（height は無視）
        const scaleW = availableW / contentW;
        const nextScale = clamp(scaleW, minScale, maxScale);
        lastValidScaleRef.current = nextScale;

        return {
          scale: nextScale,
          scaledSize: { width: contentW * nextScale, height: contentH * nextScale },
          bypassScale: false,
        };
      } else if (fitMode === "both" || availableW <= 0) {
        // parent が完全に 0 → 前回のスケール値を使う
        return { 
          scale: lastValidScaleRef.current, 
          scaledSize: { 
            width: contentW * lastValidScaleRef.current, 
            height: contentH * lastValidScaleRef.current 
          },
          bypassScale: false,
        };
      }
    }

    // 通常処理：親と子の両方が > 0
    const scaleW = availableW / contentW;
    const scaleH = availableH / contentH;

    const raw = fitMode === "width-only" ? scaleW : Math.min(scaleW, scaleH);
    const nextScale = clamp(raw, minScale, maxScale);
    lastValidScaleRef.current = nextScale;

    return {
      scale: nextScale,
      scaledSize: { width: contentW * nextScale, height: contentH * nextScale },
      bypassScale: false,
    };
  }, [containerSize, contentSize, minScale, maxScale, fitMode]);

  return (
    <div ref={containerRef} className={cn("relative h-full w-full", overflowHidden ? "overflow-hidden" : "overflow-visible", className)}>
      <div className="flex h-full w-full items-center justify-start">
        <div
          className="relative"
          style={{
            width: !bypassScale && scaledSize.width > 0 ? `${scaledSize.width}px` : undefined,
            height: !bypassScale && scaledSize.height > 0 ? `${scaledSize.height}px` : undefined,
          }}
        >
          <div
            className={cn("left-0 top-0", bypassScale ? "relative" : "absolute")}
            style={bypassScale ? undefined : { transform: `scale(${scale})`, transformOrigin: "top left" }}
          >
            <div ref={contentRef} className="inline-block">
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
