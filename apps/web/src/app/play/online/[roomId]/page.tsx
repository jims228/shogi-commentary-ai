"use client";

import React, { useState, useCallback, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { ShogiBoard } from '@/components/ShogiBoard';
import { useSocket } from '@/hooks/useSocket';
import { buildBoardTimeline, getStartBoard } from '@/lib/board';
import type { BoardMatrix, HandsState } from '@/lib/board';
import { PieceCode } from '@/lib/sfen';

const fileMap = ['9', '8', '7', '6', '5', '4', '3', '2', '1'];
const rankMap = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'];

export default function OnlineGamePage() {
  const params = useParams();
  const roomId = params.roomId as string;
  
  // Game State
  const [board, setBoard] = useState<BoardMatrix>(getStartBoard());
  const [hands, setHands] = useState<HandsState>({ b: {}, w: {} });
  const [moves, setMoves] = useState<string[]>([]);
  const [turn, setTurn] = useState<"sente" | "gote">("sente");
  const [myRole, setMyRole] = useState<"b" | "w" | "spectator" | null>(null);

  // Sync state with moves history
  useEffect(() => {
    // 指し手がない場合は初期盤面
    if (moves.length === 0) {
        setBoard(getStartBoard());
        setHands({ b: {}, w: {} });
        setTurn("sente");
        return;
    }

    const usi = "startpos moves " + moves.join(" ");
    try {
        const timeline = buildBoardTimeline(usi);
        const currentBoard = timeline.boards[timeline.boards.length - 1];
        const currentHands = timeline.hands[timeline.hands.length - 1];
        // 次の手番は、指し手の数で決まる (偶数なら先手番)
        const nextTurn = moves.length % 2 === 0 ? "sente" : "gote";
        
        setBoard(currentBoard);
        setHands(currentHands);
        setTurn(nextTurn);
    } catch (e) {
        console.error("Board sync error:", e);
    }
  }, [moves]);

  // Socket connection
  const handleSocketMessage = useCallback((data: any) => {
    try {
        const json = JSON.parse(data);
        if (json.type === "init") {
            console.log("Assigned role:", json.role);
            setMyRole(json.role);
            return;
        }
    } catch (e) {
        // Not JSON
    }

    console.log("Received move:", data);
    if (typeof data === 'string') {
        setMoves(prev => [...prev, data]);
    }
  }, []);

  const { sendMessage } = useSocket(roomId, handleSocketMessage);

  // Handle local move
  const handleMove = useCallback((move: { from?: { x: number; y: number }; to: { x: number; y: number }; piece: PieceCode; drop?: boolean }) => {
    
    // ★修正: turn ステートを使って判定
    const currentTurnCode = turn === "sente" ? "b" : "w";
    
    if (myRole !== currentTurnCode) {
        console.log("Not your turn. MyRole:", myRole, "Turn:", currentTurnCode);
        return;
    }

    let usiMove = "";
    
    if (move.drop) {
        const pieceChar = move.piece.replace("+", "").toUpperCase();
        const to = `${fileMap[move.to.x]}${rankMap[move.to.y]}`;
        usiMove = `${pieceChar}*${to}`;
    } else if (move.from) {
        const from = `${fileMap[move.from.x]}${rankMap[move.from.y]}`;
        const to = `${fileMap[move.to.x]}${rankMap[move.to.y]}`;
        
        // 成りの判定 (move.piece は移動後の駒の状態)
        // 移動前の盤面から駒情報を取得して比較
        const pieceAtSource = board[move.from.y][move.from.x];
        const isPromotedNow = move.piece.startsWith("+");
        const wasPromoted = pieceAtSource?.startsWith("+");
        
        const isPromotionAction = isPromotedNow && !wasPromoted;
        
        usiMove = `${from}${to}${isPromotionAction ? "+" : ""}`;
    }

    if (usiMove) {
        sendMessage(usiMove);
        // ★重要: 送信した瞬間に自分の画面にも反映させる
        setMoves(prev => [...prev, usiMove]);
    }
  }, [board, sendMessage, turn, myRole]); // moves は依存配列に入れなくても setMoves(prev => ...) でOK

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-stone-100 gap-8 p-4">
      <div className="flex flex-col items-center gap-2">
        <h1 className="text-2xl font-bold text-stone-800">Online Room: {roomId}</h1>
        <p className="text-stone-600">Share this URL to play with a friend.</p>
        <div className="text-sm font-mono bg-white px-3 py-1 rounded border border-stone-300 flex gap-4">
            <span>Turn: {turn === "sente" ? "Black (Sente)" : "White (Gote)"}</span>
            <span className="font-bold text-blue-600 border-l pl-4 border-stone-300">
                You: {myRole === "b" ? "Black (Sente)" : myRole === "w" ? "White (Gote)" : "Spectator"}
            </span>
        </div>
      </div>
      
      <ShogiBoard 
        board={board}
        hands={hands}
        onBoardChange={setBoard}
        onHandsChange={setHands}
        onMove={handleMove}
        mode="edit"
        autoPromote={false}
        showPromotionZone={true}
        orientation={myRole === "w" ? "gote" : "sente"}
      />
      
      <div className="w-full max-w-md bg-white p-4 rounded-lg shadow border border-stone-200">
          <h3 className="font-bold mb-2 text-stone-700">Move History</h3>
          <div className="h-32 overflow-y-auto text-sm font-mono bg-stone-50 p-2 rounded">
              {moves.map((m, i) => (
                  <span key={i} className="mr-2 inline-block">
                      {i + 1}. {m}
                  </span>
              ))}
              {moves.length === 0 && <span className="text-stone-400">No moves yet.</span>}
          </div>
      </div>
    </div>
  );
}