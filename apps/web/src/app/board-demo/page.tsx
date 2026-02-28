"use client";

import React, { useState } from "react";
import { Board, MoveEvent, BoardPiece } from "@/components/shogi/Board";

export default function BoardDemoPage() {
  const [lastMove, setLastMove] = useState<string>("-");
  const [moveHistory, setMoveHistory] = useState<string[]>([]);

  const handleMove = (move: MoveEvent) => {
    console.log("Move:", move);
    setLastMove(move.usi);
    setMoveHistory(prev => [...prev, move.usi]);
  };

  const initialPieces: BoardPiece[] = [
    { id: "p1", type: "FU", owner: "black", x: 7, y: 7 },
    { id: "p2", type: "FU", owner: "white", x: 3, y: 3 },
    { id: "p3", type: "HI", owner: "black", x: 2, y: 8 },
    { id: "p4", type: "KA", owner: "white", x: 8, y: 2 },
    { id: "p5", type: "OU", owner: "black", x: 5, y: 9 },
    { id: "p6", type: "OU", owner: "white", x: 5, y: 1 },
    { id: "p7", type: "KI", owner: "black", x: 6, y: 9 },
    { id: "p8", type: "KI", owner: "white", x: 4, y: 1 },
  ];

  return (
    <div className="p-8 flex flex-col items-center gap-8 min-h-screen bg-stone-100">
      <h1 className="text-3xl font-bold text-stone-800">Shogi Board Interaction Demo</h1>
      
      <div className="flex gap-8 items-start">
        <div className="bg-white p-4 rounded-lg shadow-lg">
          <Board initialPieces={initialPieces} onMove={handleMove} />
        </div>

        <div className="w-64 flex flex-col gap-4">
          <div className="bg-white p-4 rounded shadow">
            <h2 className="font-bold mb-2 text-lg border-b pb-1">Status</h2>
            <p className="text-sm text-gray-600 mb-1">Last Move:</p>
            <p className="text-2xl font-mono font-bold text-blue-600">{lastMove}</p>
          </div>

          <div className="bg-white p-4 rounded shadow flex-1">
            <h2 className="font-bold mb-2 text-lg border-b pb-1">History</h2>
            <div className="h-64 overflow-y-auto font-mono text-sm">
              {moveHistory.map((m, i) => (
                <div key={i} className="py-1 border-b border-gray-100">
                  <span className="text-gray-400 mr-2">{i + 1}.</span>
                  {m}
                </div>
              ))}
              {moveHistory.length === 0 && <p className="text-gray-400 italic">No moves yet</p>}
            </div>
          </div>
          
          <div className="bg-blue-50 p-4 rounded text-sm text-blue-800">
            <p className="font-bold mb-1">Instructions:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Click a piece to select (Gold highlight)</li>
              <li>Click an empty square to move</li>
              <li>Click an opponent's piece to capture</li>
              <li>Drag & Drop is also supported</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
