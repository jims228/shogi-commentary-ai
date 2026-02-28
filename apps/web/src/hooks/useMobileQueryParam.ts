"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { getMobileParamsFromUrl } from "@/lib/mobileBridge";

/**
 * SSR では useLayoutEffect が実行されないため useEffect を使い、
 * クライアントでは useLayoutEffect（ブラウザ描画前に同期実行）を使う。
 * これによりハイドレーション不一致を起こさずに、初回ペイントから
 * 正しいレイアウトを適用できる。
 */
const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

/** Returns just the `mobile` flag (legacy compat). */
export function useMobileQueryParam(): boolean {
  const [mobile, setMobile] = useState<boolean>(() => {
    try {
      if (typeof window !== "undefined") {
        return new URLSearchParams(window.location.search).get("mobile") === "1";
      }
    } catch {}
    return false;
  });

  useIsomorphicLayoutEffect(() => {
    try {
      const sp = new URLSearchParams(window.location.search);
      setMobile(sp.get("mobile") === "1");
    } catch {
      setMobile(false);
    }
  }, []);

  return mobile;
}

/**
 * Returns { mobile, embed, noai, lid } を一括取得。
 *
 * ★ SSR: 初期値 false → ハイドレーション不一致なし
 * ★ クライアント: useLayoutEffect がブラウザ描画前に同期実行 →
 *    ユーザーには最初から正しいレイアウト（embed / mobile）が見える。
 *    「一瞬だけ別レイアウトが表示されて矢印が消える」問題を解消。
 */
export function useMobileParams() {
  const [params, setParams] = useState(() => getMobileParamsFromUrl());

  useIsomorphicLayoutEffect(() => {
    try {
      const p = getMobileParamsFromUrl();
      setParams({ mobile: p.mobile, embed: p.embed, noai: p.noai, lid: p.lid });
    } catch {
      /* ignore */
    }
  }, []);

  return params;
}

