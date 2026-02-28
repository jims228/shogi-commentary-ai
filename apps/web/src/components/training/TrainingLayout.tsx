"use client";

import React from "react";
import { cn } from "@/lib/utils";

type TrainingLayoutProps = {
  left: React.ReactNode;
  rightTop: React.ReactNode;
  rightBottom: React.ReactNode;
  className?: string;
  leftClassName?: string;
  rightClassName?: string;
  stickyRight?: boolean;
};

export function TrainingLayout({
  left,
  rightTop,
  rightBottom,
  className,
  leftClassName,
  rightClassName,
  stickyRight = true,
}: TrainingLayoutProps) {
  return (
    <div
      className={cn(
        "grid min-h-0 w-full grid-cols-1 items-start gap-6 lg:grid-cols-12",
        className,
      )}
    >
      <div className={cn("min-h-0 lg:col-span-8", leftClassName)}>{left}</div>

      <aside
        className={cn(
          "min-h-0 lg:col-span-4",
          stickyRight && "lg:sticky lg:top-20 lg:self-start",
          rightClassName,
        )}
      >
        <div className="flex min-h-0 flex-col justify-between gap-3">
          <div className="min-h-0">{rightTop}</div>
          <div className="flex justify-end">{rightBottom}</div>
        </div>
      </aside>
    </div>
  );
}
