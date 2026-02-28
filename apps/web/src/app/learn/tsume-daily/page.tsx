"use client";
import React, { useEffect, useState } from "react";
import { loadTsumeDaily, Puzzle, normalizeMove } from "@/lib/learn/tsume";
import { ProgressProvider, useProgress } from "@/lib/learn/progress";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function LessonInner() {
  const [puzzles, setPuzzles] = useState<Puzzle[]>([]);
  const [index, setIndex] = useState(0);
  const [input, setInput] = useState("");
  const { addXp, loseHeart, markCleared, nextDayAdjust } = useProgress();

  useEffect(() => {
    loadTsumeDaily(5).then(setPuzzles).catch(() => setPuzzles([]));
  }, []);

  const cur = puzzles[index];
  if (!cur) return <Card className="p-4">Loading...</Card>;

  function check() {
    const solRaw = cur.solution || "";
    let candidates: string[] = [];
    if (solRaw.includes(";")) {
      candidates = solRaw.split(/;+\s*/).map((s) => s.trim()).filter(Boolean);
    } else {
      // default: take first token of the space-separated solution (first move)
      const firstTok = solRaw.split(/\s+/).filter(Boolean)[0];
      if (firstTok) candidates = [firstTok];
    }
    if (candidates.length === 0) return;

  const inNorm = normalizeMove(input);
  const ok = candidates.some((c) => normalizeMove(c) === inNorm);

    if (ok) {
      addXp(10);
      markCleared(cur.id);
      if (index + 1 < puzzles.length) setIndex(index + 1);
      else nextDayAdjust();
    } else {
      loseHeart();
    }
    setInput("");
  }

  return (
    <Card className="p-4">
      <h2 className="font-bold">Puzzle {index + 1} / {puzzles.length}</h2>
      <p className="text-sm text-muted-foreground">Goal: {cur.goal}</p>
      <p className="text-sm">Hint: {cur.hint}</p>
      <div className="mt-3">
        <input className="border p-2 w-full font-mono" value={input} onChange={(e) => setInput(e.target.value)} placeholder="enter first USI move (e.g. 7g7f)" />
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={check}>Submit</Button>
        <Button variant="ghost" onClick={() => { if (index + 1 < puzzles.length) setIndex(index + 1); else nextDayAdjust(); }}>Skip</Button>
      </div>
    </Card>
  );
}

export default function TsumeDailyPage() {
  return (
    <ProgressProvider>
      <main className="p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">Tsume Daily</h1>
        <LessonInner />
      </main>
    </ProgressProvider>
  );
}
