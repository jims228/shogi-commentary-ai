"use client";

import React, { useState } from "react";
import { ShogiBoard } from "@/components/ShogiBoard";
import { getStartBoard, type BoardMatrix } from "@/lib/board";

export default function EditBoardDebugPage() {
  const [board, setBoard] = useState<BoardMatrix>(() => getStartBoard());

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Edit Board Debug</h1>
        <p className="text-sm text-slate-600">Drag pieces to verify edit-mode DnD behavior.</p>
      </div>
      <ShogiBoard
        board={board}
        mode="edit"
        onBoardChange={(next) => {
          console.log("[Debug] onBoardChange called");
          setBoard(next);
        }}
      />
    </div>
  );
}
