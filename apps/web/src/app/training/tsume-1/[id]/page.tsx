"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Board } from "@/components/Board";
import { ManRive } from "@/components/ManRive";
import { Placed } from "@/lib/sfen";
import { ArrowLeft, CheckCircle, XCircle, ChevronRight, RefreshCw } from "lucide-react";
import { postMobileLessonCompleteOnce } from "@/lib/mobileBridge";
import { MobileLessonShell } from "@/components/mobile/MobileLessonShell";
import { MobilePrimaryCTA } from "@/components/mobile/MobilePrimaryCTA";
import { MobileCoachText } from "@/components/mobile/MobileCoachText";
import { useMobileQueryParam } from "@/hooks/useMobileQueryParam";

// Simple Tsume data
const TSUME_DATA: Record<string, {
  initialPieces: Placed[];
  correctMove: { from: { x: number, y: number } | "hand", to: { x: number, y: number }, piece: string };
  opponentKing: { x: number, y: number };
  description: string;
}> = {
  "tsume_1_001": {
    initialPieces: [
      { piece: "k", x: 0, y: 0 }, // 1一 玉 (Opponent)
      { piece: "G", x: 1, y: 2 }, // 2三 金 (Player)
      { piece: "K", x: 8, y: 8 }, // 9九 玉 (Player King - just for presence)
    ],
    opponentKing: { x: 0, y: 0 },
    correctMove: { from: { x: 1, y: 2 }, to: { x: 1, y: 1 }, piece: "G" }, // 2三金 -> 2二金
    description: "頭金（あたまきん）の基本です。玉の頭に金を打つか、移動して詰ませましょう。"
  }
};

export default function TsumeLessonPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;
  const isMobileWebView = useMobileQueryParam();
  
  const lesson = TSUME_DATA[id];
  
  const [pieces, setPieces] = useState<Placed[]>([]);
  const [selectedSquare, setSelectedSquare] = useState<{x: number, y: number} | null>(null);
  const [status, setStatus] = useState<"playing" | "correct" | "incorrect">("playing");
  const [message, setMessage] = useState("");
  const [correctSignal, setCorrectSignal] = useState(0);

  useEffect(() => {
    if (lesson) {
      setPieces(lesson.initialPieces);
      setMessage(lesson.description);
      setStatus("playing");
      setSelectedSquare(null);
    }
  }, [lesson]);

  if (!lesson) {
    return <div className="min-h-screen bg-[#f6f1e6] text-[#2b2b2b] p-8">Lesson not found</div>;
  }

  const handleSquareClick = (x: number, y: number) => {
    if (status !== "playing") return;

    // If nothing selected, try to select a piece
    if (!selectedSquare) {
      const piece = pieces.find(p => p.x === x && p.y === y);
      // Only select player's pieces (uppercase)
      if (piece && piece.piece === piece.piece.toUpperCase()) {
        setSelectedSquare({ x, y });
      }
      return;
    }

    // If selected, try to move
    // Check if it's the correct move
    const isCorrect = 
      selectedSquare.x === (lesson.correctMove.from as any).x &&
      selectedSquare.y === (lesson.correctMove.from as any).y &&
      x === lesson.correctMove.to.x &&
      y === lesson.correctMove.to.y;

    if (isCorrect) {
      // Execute move
      const newPieces = pieces.map(p => {
        if (p.x === selectedSquare.x && p.y === selectedSquare.y) {
          return { ...p, x, y };
        }
        return p;
      });
      setPieces(newPieces);
      setStatus("correct");
      setMessage("正解！詰みです。");
      setCorrectSignal((v) => v + 1);
    } else {
      // Wrong move
      setStatus("incorrect");
      setMessage("不正解です。もう一度考えてみましょう。");
    }
    setSelectedSquare(null);
  };

  const handleRetry = () => {
    setPieces(lesson.initialPieces);
    setStatus("playing");
    setMessage(lesson.description);
    setSelectedSquare(null);
  };

  const handleFinish = () => {
    postMobileLessonCompleteOnce();
    router.push("/learn");
  };

  if (isMobileWebView) {
    const boardElementMobile = (
      <div className="w-full h-full min-h-0 flex items-center justify-center">
        <div
          className="inline-block"
        >
          <Board pieces={pieces} highlightSquares={selectedSquare ? [selectedSquare] : []} onSquareClick={handleSquareClick} />
        </div>
      </div>
    );

    const correct = status === "correct";
    const text =
      status === "playing"
        ? lesson.description
        : status === "correct"
          ? "正解！詰みです。"
          : "不正解です。もう一度考えてみましょう。";

    return (
      <MobileLessonShell
        mascot={<ManRive correctSignal={correctSignal} style={{ width: 210, height: 210 }} />}
        explanation={
          <MobileCoachText tag="TSUME" text={text} isCorrect={correct} correctText="正解！完了して戻ろう。" />
        }
        actions={
          correct ? <MobilePrimaryCTA label="完了" onClick={handleFinish} /> : status === "incorrect" ? (
            <MobilePrimaryCTA label="もう一度" onClick={handleRetry} />
          ) : null
        }
        board={boardElementMobile}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#f6f1e6] text-[#2b2b2b] font-sans flex flex-col">
      <div
        style={{
          position: "fixed",
          left: 12,
          top: 12,
          zIndex: 50,
          width: 160,
          height: 160,
          pointerEvents: "none",
        }}
      >
        <ManRive correctSignal={correctSignal} style={{ width: "100%", height: "100%" }} />
      </div>
      {/* Header */}
      <header className="h-16 border-b border-black/10 flex items-center px-4 bg-[#f9f3e5]/95">
        <Link href="/learn" className="flex items-center text-[#555] hover:text-[#2b2b2b] transition-colors">
          <ArrowLeft className="w-5 h-5 mr-2 text-[#555]" />
          マップに戻る
        </Link>
        <h1 className="ml-4 font-bold text-lg">1手詰レッスン</h1>
      </header>

      <div className="flex-1 flex flex-col md:flex-row max-w-6xl mx-auto w-full p-4 gap-8">
        {/* Left: Board */}
        <div className="flex-1 flex items-center justify-center bg-[#fef8e6] rounded-2xl border border-black/10 p-4 relative shadow-[0_10px_25px_rgba(0,0,0,0.08)]">
          <Board 
            pieces={pieces} 
            highlightSquares={selectedSquare ? [selectedSquare] : []}
            onSquareClick={handleSquareClick}
          />
          
          {/* Overlay for Incorrect */}
          {status === "incorrect" && (
            <div className="absolute inset-0 bg-black/30 flex items-center justify-center rounded-2xl backdrop-blur-sm">
              <div className="bg-[#fdf3de] p-6 rounded-xl border border-rose-200 shadow-2xl text-center text-[#2b2b2b]">
                <XCircle className="w-16 h-16 text-[#555] mx-auto mb-4" />
                <h3 className="text-xl font-bold text-[#2b2b2b] mb-2">不正解...</h3>
                <button 
                  onClick={handleRetry}
                  className="mt-4 px-6 py-2 bg-white text-[#2b2b2b] font-bold rounded-lg border border-black/10 hover:bg-amber-50 transition-colors flex items-center mx-auto gap-2"
                >
                  <RefreshCw className="w-4 h-4 text-[#555]" />
                  もう一度
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Instructions */}
        <div className="w-full md:w-96 flex flex-col gap-6">
          <div className={`bg-[#fdf3de] border rounded-2xl p-6 shadow-[0_10px_25px_rgba(0,0,0,0.08)] transition-colors ${
            status === "correct" ? "border-emerald-300" : "border-black/10"
          }`}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-xl ${
                status === "correct" ? "bg-[#e3f6d4]" : "bg-[#fef1d6]"
              }`}>
                {status === "correct" ? <CheckCircle className="w-6 h-6 text-[#555]" /> : <span className="text-[#2b2b2b]">?</span>}
              </div>
              <h2 className="font-bold text-xl">
                {status === "correct" ? "クリア！" : "問題"}
              </h2>
            </div>
            
            <p className="text-lg text-[#444] leading-relaxed mb-6">
              {message}
            </p>

            {status === "correct" && (
              <button
                onClick={handleFinish}
                className="w-full py-3 bg-[#e3f6d4] hover:bg-[#d1ecbc] text-[#2b2b2b] font-bold rounded-xl shadow-lg transition-all active:scale-95 flex items-center justify-center gap-2 border border-black/10"
              >
                マップに戻る
                <ChevronRight className="w-5 h-5 text-[#555]" />
              </button>
            )}
            
            {status === "playing" && (
               <div className="text-sm text-slate-600 bg-white/80 border border-black/10 p-4 rounded-lg">
                 ヒント: 自分の駒（下側）をクリックして選択し、移動先をクリックしてください。
               </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
