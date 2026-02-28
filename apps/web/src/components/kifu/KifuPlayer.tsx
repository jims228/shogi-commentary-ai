"use client";

import React, { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export interface KifuPlayerProps {
  moves: string[];
  currentPly: number;
  onPlyChange: (ply: number) => void;
  renderBoard: (ply: number) => React.ReactNode;
}

export function KifuPlayer({ moves, currentPly, onPlyChange, renderBoard }: KifuPlayerProps) {
  const maxPly = moves.length;

  const clampAndChange = useCallback((nextPly: number) => {
    const clamped = Math.max(0, Math.min(nextPly, maxPly));
    onPlyChange(clamped);
  }, [maxPly, onPlyChange]);

  const goToStart = useCallback(() => clampAndChange(0), [clampAndChange]);
  const goToPrev = useCallback(() => clampAndChange(currentPly - 1), [clampAndChange, currentPly]);
  const goToNext = useCallback(() => clampAndChange(currentPly + 1), [clampAndChange, currentPly]);
  const goToEnd = useCallback(() => clampAndChange(maxPly), [clampAndChange, maxPly]);

  return (
    <Card className="w-full flex flex-col gap-4 p-4">
      <div className="flex justify-center">
        {renderBoard(currentPly)}
      </div>

      <div className="text-center text-sm text-muted-foreground">
        <span className="font-mono">{currentPly} / {maxPly}</span>
        {currentPly > 0 && moves[currentPly - 1] && (
          <span className="ml-2 font-mono text-xs">
            ({moves[currentPly - 1]})
          </span>
        )}
      </div>

      <div className="flex items-center justify-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={goToStart}
          disabled={currentPly === 0}
          aria-label="Go to start"
        >
          {"<<"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={goToPrev}
          disabled={currentPly === 0}
          aria-label="Previous move"
        >
          {"<"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={goToNext}
          disabled={currentPly >= maxPly}
          aria-label="Next move"
        >
          {">"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={goToEnd}
          disabled={currentPly >= maxPly}
          aria-label="Go to end"
        >
          {">>"}
        </Button>
      </div>
    </Card>
  );
}