"use client";

import React, { useMemo } from "react";
import { usePathname } from "next/navigation";
import { SakuraPetals } from "@/components/ui/SakuraPetals";

function isSakuraRoute(pathname: string | null) {
  if (!pathname) return false;
  return pathname === "/learn/roadmap" || pathname.startsWith("/training");
}

export function SakuraThemeShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const enabled = isSakuraRoute(pathname);
  const isTraining = Boolean(pathname?.startsWith("/training"));

  const outerClass = useMemo(() => {
    const base = "relative h-full min-h-screen";
    if (!enabled) return base;
    // Training screens should be plain white (board focus).
    return isTraining ? `${base} bg-white` : `${base} sakura-theme sakura-surface`;
  }, [enabled, isTraining]);

  const contentClass = useMemo(() => {
    return "relative z-[20] h-full flex flex-col px-4 sm:px-6 lg:px-12 xl:px-[220px] 2xl:px-[260px] py-6 gap-6";
  }, []);

  return (
    <div className={outerClass}>
      {enabled && !isTraining ? <div className="sakura-backdrop-layer" aria-hidden="true" /> : null}
      {/* Do not render petals on training screens (board taps must stay clean). */}
      {enabled && !isTraining ? <SakuraPetals /> : null}
      <div className={contentClass}>
        <main className="flex-1 w-full min-h-0 flex flex-col">{children}</main>
      </div>
    </div>
  );
}


