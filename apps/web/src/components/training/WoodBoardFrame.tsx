"use client";

import React from "react";
import { cn } from "@/lib/utils";

type Props = {
  children: React.ReactNode;
  className?: string;
  innerClassName?: string;
  paddingClassName?: string; // 余白調整用
};

export function WoodBoardFrame({
  children,
  className,
  innerClassName,
  paddingClassName = "p-2",
}: Props) {
  return (
    <div
      className={cn(
        "rounded-2xl shadow-2xl border-4 border-[#5d4037] bg-[#f3c882]",
        paddingClassName,
        className,
      )}
    >
      <div className={cn("rounded-xl", innerClassName)}>{children}</div>
    </div>
  );
}
