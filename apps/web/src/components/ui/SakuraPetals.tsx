"use client";

import React, { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

type Petal = {
  leftPct: number;
  sizePx: number;
  opacity: number;
  durationSec: number;
  delaySec: number;
  driftPx: number;
  rotateDeg: number;
  scale: number;
};

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(!!mq.matches);
    onChange();
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);
  return reduced;
}

function isSakuraRoute(pathname: string | null) {
  if (!pathname) return false;
  return pathname === "/learn/roadmap" || pathname.startsWith("/training");
}

export function SakuraPetals() {
  const pathname = usePathname();
  const reducedMotion = usePrefersReducedMotion();

  const enabled = isSakuraRoute(pathname) && !reducedMotion;
  const petals = useMemo<Petal[]>(() => {
    // low density: 16 petals
    // deterministic values (no Math.random) to avoid hydration mismatch
    const base: Petal[] = [];
    const lefts = [4, 8, 13, 18, 24, 30, 36, 42, 50, 58, 66, 74, 82, 89, 94, 97];
    for (let i = 0; i < lefts.length; i++) {
      base.push({
        leftPct: lefts[i],
        // slightly smaller (still clearly visible)
        sizePx: 32 + (i % 6) * 4, // 32..52
        // larger petals need lower opacity to avoid visual blocking
        opacity: 0.18 + (i % 5) * 0.03, // ~0.18..0.30
        durationSec: 10 + (i % 5) * 2, // 10..18
        delaySec: -(i * 1.05), // 0..-16s-ish
        driftPx: (i % 2 === 0 ? 1 : -1) * (34 + (i % 4) * 7), // ~ -60..60
        rotateDeg: (i * 37) % 360,
        // keep subtle size variation on top of big base size
        scale: 0.92 + (i % 4) * 0.06,
      });
    }
    return base;
  }, []);

  if (!enabled) return null;

  return (
    <div className="sakura-petals" aria-hidden="true">
      {petals.map((p, i) => (
        <div
          key={i}
          className="sakura-petal"
          style={{
            ["--petal-left" as any]: `${p.leftPct}%`,
            ["--petal-size" as any]: `${p.sizePx}px`,
            ["--petal-opacity" as any]: `${p.opacity}`,
            ["--petal-duration" as any]: `${p.durationSec}s`,
            ["--petal-delay" as any]: `${p.delaySec}s`,
            ["--petal-drift" as any]: `${p.driftPx}px`,
            ["--petal-rot" as any]: `${p.rotateDeg}deg`,
            ["--petal-scale" as any]: `${p.scale}`,
          }}
        />
      ))}
    </div>
  );
}


