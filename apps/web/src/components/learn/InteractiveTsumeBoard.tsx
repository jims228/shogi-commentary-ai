"use client";
import React, { useState, useMemo } from "react";
import { Piece } from "@/components/Piece";
import { parseSfen, parseHandFromSfen, type Placed, type PieceCode } from "@/lib/sfen";
import { Button } from "@/components/ui/button";

const FILES = ["９","８","７","６","５","４","３","２","１"];
const RANKS = ["一","二","三","四","五","六","七","八","九"];

type HandPiece = {
  piece: PieceCode;
  count: number;
};

interface InteractiveTsumeBoardProps {
  sfen: string;
  turn: "w" | "b";
  onMoveSubmit: (move: string) => void;
  disabled?: boolean;
}

export const InteractiveTsumeBoard: React.FC<InteractiveTsumeBoardProps> = ({
  sfen,
  turn,
  onMoveSubmit,
  disabled = false,
}) => {
  const initialState = useMemo(() => parseSfen(sfen), [sfen]);
  const initialHand = useMemo(() => {
    const handObj = parseHandFromSfen(sfen, turn);
    return Object.entries(handObj).map(([piece, count]) => ({
      piece: piece as PieceCode,
      count,
    }));
  }, [sfen, turn]);

  const [pieces, setPieces] = useState<Placed[]>(initialState);
  const [selectedSquare, setSelectedSquare] = useState<{x: number; y: number} | null>(null);
  const [selectedHandPiece, setSelectedHandPiece] = useState<PieceCode | null>(null);
  const [hand, setHand] = useState<HandPiece[]>(initialHand);

  const handleSquareClick = (x: number, y: number) => {
    if (disabled) return;

    // 持ち駒を選択中の場合は、その駒を打つ
    if (selectedHandPiece) {
      const existingPiece = pieces.find(p => p.x === x && p.y === y);
      if (existingPiece) {
        // 既に駒がある場合は打てない
        return;
      }

      // 駒を打つ
      const newPieces = [...pieces, { piece: selectedHandPiece, x, y }];
      setPieces(newPieces);

      // 持ち駒を減らす
      setHand(hand.map(h => 
        h.piece === selectedHandPiece && h.count > 0
          ? { ...h, count: h.count - 1 }
          : h
      ).filter(h => h.count > 0));

      // 手を生成して送信
      const move = generateDropMove(selectedHandPiece, x, y);
      setSelectedHandPiece(null);
      onMoveSubmit(move);
      return;
    }

    // 盤上の駒を選択
    const piece = pieces.find(p => p.x === x && p.y === y);
    
    if (selectedSquare) {
      // 移動先をクリック
      const fromPiece = pieces.find(p => p.x === selectedSquare.x && p.y === selectedSquare.y);
      if (!fromPiece) {
        setSelectedSquare(null);
        return;
      }

      // 移動実行
      const targetPiece = pieces.find(p => p.x === x && p.y === y);
      let newPieces = pieces.filter(p => !(p.x === selectedSquare.x && p.y === selectedSquare.y));
      
      if (targetPiece) {
        // 駒を取る
        newPieces = newPieces.filter(p => !(p.x === x && p.y === y));
        // 持ち駒に追加（簡易実装: 成駒は元に戻す）
        const capturedBase = getBasePiece(targetPiece.piece);
        const oppositePiece = turn === "b" ? capturedBase.toUpperCase() : capturedBase.toLowerCase();
        setHand([...hand, { piece: oppositePiece as PieceCode, count: 1 }]);
      }

      newPieces.push({ piece: fromPiece.piece, x, y });
      setPieces(newPieces);

      // 手を生成して送信
      const move = generateMove(selectedSquare.x, selectedSquare.y, x, y);
      setSelectedSquare(null);
      onMoveSubmit(move);
    } else if (piece && isPieceOurs(piece.piece, turn)) {
      // 自分の駒を選択
      setSelectedSquare({ x, y });
    }
  };

  const handleHandPieceClick = (piece: PieceCode) => {
    if (disabled) return;
    setSelectedHandPiece(piece === selectedHandPiece ? null : piece);
    setSelectedSquare(null);
  };

  const handleReset = () => {
    setPieces(initialState);
    setSelectedSquare(null);
    setSelectedHandPiece(null);
    setHand(initialHand);
  };

  return (
    <div className="space-y-4">
      {/* 持ち駒表示 */}
      {hand.length > 0 && (
        <div className="flex gap-2 items-center justify-center">
          <span className="text-sm font-medium">持ち駒:</span>
          {hand.map((h, i) => (
            <button
              key={i}
              onClick={() => handleHandPieceClick(h.piece)}
              className={`px-3 py-2 border rounded-lg transition-colors ${
                selectedHandPiece === h.piece
                  ? "bg-blue-100 border-blue-400"
                  : "bg-white hover:bg-gray-50"
              }`}
              disabled={disabled}
            >
              <span className="font-medium">{getPieceName(h.piece)} × {h.count}</span>
            </button>
          ))}
        </div>
      )}

      {/* 盤面 */}
      <div className="flex justify-center items-center">
        <svg
          viewBox="0 0 470 490"
          className="shadow-lg rounded-2xl border-4 border-amber-800 bg-amber-50"
          width={470}
          height={490}
        >
          {/* 升目 */}
          {[...Array(9)].flatMap((_, y) =>
            [...Array(9)].map((_, x) => {
              const isSelected = selectedSquare?.x === x && selectedSquare?.y === y;
              const isTargetable = selectedSquare !== null || selectedHandPiece !== null;
              
              return (
                <g key={`c-${x}-${y}`}>
                  <rect
                    x={10 + x * 50}
                    y={10 + y * 50}
                    width="50"
                    height="50"
                    fill={isSelected ? "#93c5fd" : "#fef3c7"}
                    stroke={isSelected ? "#3b82f6" : "#92400e"}
                    strokeWidth={isSelected ? "2.5" : "1.5"}
                    rx="2"
                    ry="2"
                    className={isTargetable && !disabled ? "cursor-pointer hover:opacity-80" : ""}
                    onClick={() => handleSquareClick(x, y)}
                  />
                  {/* 選択可能マーカー */}
                  {isTargetable && !disabled && !pieces.find(p => p.x === x && p.y === y) && (
                    <circle
                      cx={10 + x * 50 + 25}
                      cy={10 + y * 50 + 25}
                      r="4"
                      fill="#3b82f6"
                      opacity="0.4"
                      className="pointer-events-none"
                    />
                  )}
                </g>
              );
            })
          )}

          {/* 駒 */}
          <g>
            {pieces.map((p, i) => (
              <g
                key={i}
                onClick={() => !disabled && isPieceOurs(p.piece, turn) && setSelectedSquare({ x: p.x, y: p.y })}
                className={isPieceOurs(p.piece, turn) && !disabled ? "cursor-pointer" : ""}
              >
                <Piece piece={p.piece} x={p.x} y={p.y} />
              </g>
            ))}
          </g>

          {/* 目盛り */}
          {FILES.map((f, i) => (
            <text key={`f${i}`} x={10 + i * 50 + 25} y={480} textAnchor="middle" fontSize="13" fill="#78350f">
              {f}
            </text>
          ))}
          {RANKS.map((r, i) => (
            <text key={`r${i}`} x={2} y={10 + i * 50 + 32} textAnchor="start" fontSize="13" fill="#78350f">
              {r}
            </text>
          ))}
        </svg>
      </div>

      {/* リセットボタン */}
      {!disabled && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={handleReset}>
            盤面をリセット
          </Button>
        </div>
      )}

      {/* 説明 */}
      {!disabled && (
        <div className="text-center text-sm text-muted-foreground">
          {selectedHandPiece
            ? "盤上の空いているマスをクリックして駒を打ってください"
            : selectedSquare
            ? "移動先のマスをクリックしてください"
            : "駒または持ち駒を選択してください"}
        </div>
      )}
    </div>
  );
};

// ヘルパー関数
function isPieceOurs(piece: PieceCode, turn: "w" | "b"): boolean {
  const isUpper = piece === piece.toUpperCase();
  return turn === "b" ? isUpper : !isUpper;
}

function getBasePiece(piece: PieceCode): string {
  const p = piece.replace("+", "");
  return p;
}

function getPieceName(piece: PieceCode): string {
  const base = piece.replace("+", "").toUpperCase();
  const names: Record<string, string> = {
    "K": "玉", "R": "飛", "B": "角", "G": "金",
    "S": "銀", "N": "桂", "L": "香", "P": "歩"
  };
  return names[base] || base;
}

function generateMove(fromX: number, fromY: number, toX: number, toY: number): string {
  // USI形式: 7g7f (列は9から、行はaから)
  const fromFile = 9 - fromX;
  const fromRank = String.fromCharCode(97 + fromY); // a-i
  const toFile = 9 - toX;
  const toRank = String.fromCharCode(97 + toY);
  return `${fromFile}${fromRank}${toFile}${toRank}`;
}

function generateDropMove(piece: PieceCode, x: number, y: number): string {
  // USI駒打ち形式: G*2b (金を2二に打つ)
  const file = 9 - x;
  const rank = String.fromCharCode(97 + y);
  const pieceChar = piece.toUpperCase().replace("+", "");
  return `${pieceChar}*${file}${rank}`;
}
