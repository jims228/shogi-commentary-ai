"use client";
import React, { useState, useRef, useCallback } from "react";
import { Piece } from "./Piece";
import { type PieceType, type Owner, PIECE_WIDTH, PIECE_HEIGHT } from "@/lib/shogi/PieceSprite";
import { type Square, squareToUSI } from "@/lib/shogi/shogiMoveUtils";

// 盤面の定義 (9x9)
const COLS = 9;
const ROWS = 9;

export type MoveEvent = {
  from: Square;
  to: Square;
  piece: PieceType;
  owner: Owner;
  promotedBefore: boolean;
  promotedAfter: boolean;
  usi: string;
};

export interface BoardPiece {
  id: string;
  type: PieceType;
  owner: Owner;
  promoted?: boolean;
  x: number; // 9-1 (筋)
  y: number; // 1-9 (段)
}

interface BoardProps {
  initialPieces?: BoardPiece[];
  onMove?: (move: MoveEvent) => void;
}

export const Board: React.FC<BoardProps> = ({ initialPieces = [], onMove }) => {
  const [pieces, setPieces] = useState<BoardPiece[]>(initialPieces);
  const [selectedPieceId, setSelectedPieceId] = useState<string | null>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const scale = "var(--piece-scale, 1)";

  // 座標変換: 筋・段 -> ピクセル座標 (left, top)
  const squareToPixel = (file: number, rank: number) => {
    // x=9 -> colIndex=0, x=1 -> colIndex=8
    const colIndex = 9 - file;
    const rowIndex = rank - 1;
    return {
      x: `calc(${colIndex * PIECE_WIDTH}px * ${scale})`,
      y: `calc(${rowIndex * PIECE_HEIGHT}px * ${scale})`,
    };
  };

  // 座標変換: クライアント座標 -> 筋・段
  const pixelToSquare = (clientX: number, clientY: number): Square | null => {
    if (!boardRef.current) return null;
    const rect = boardRef.current.getBoundingClientRect();
    
    const relX = clientX - rect.left;
    const relY = clientY - rect.top;
    
    const cellWidth = rect.width / COLS;
    const cellHeight = rect.height / ROWS;

    const colIndex = Math.floor(relX / cellWidth);
    const rowIndex = Math.floor(relY / cellHeight);

    if (colIndex < 0 || colIndex >= COLS || rowIndex < 0 || rowIndex >= ROWS) {
      return null;
    }

    return {
      file: 9 - colIndex,
      rank: rowIndex + 1,
    };
  };

  // 駒の移動処理共通ロジック
  const movePiece = (pieceId: string, toFile: number, toRank: number) => {
    const targetPiece = pieces.find(p => p.id === pieceId);
    if (!targetPiece) return;

    // 移動元と同じなら何もしない
    if (targetPiece.x === toFile && targetPiece.y === toRank) {
      setSelectedPieceId(null);
      return;
    }

    // 移動先に自分の駒がある場合は移動不可（選択切り替えは別途ハンドリング）
    const existingPiece = pieces.find(p => p.x === toFile && p.y === toRank);
    if (existingPiece && existingPiece.owner === targetPiece.owner) {
      return;
    }

    // 移動実行
    setPieces(prev => prev.map(p => {
      if (p.id === pieceId) {
        return { ...p, x: toFile, y: toRank };
      }
      // 相手の駒がある場合は取る（簡易実装：盤上から消す）
      // 本来は持ち駒に移動する処理が必要
      if (p.x === toFile && p.y === toRank) {
        // Reactのリストレンダリングで消えるように、ここでは除外せず
        // 実際のアプリでは持ち駒Stateに移す
        // 今回は「取る」動作として盤上から消すために filter するのが正しいが、
        // map の中なので null を返して後で filter するか、
        // setPieces のロジックを変える必要がある。
        // 簡易的に「盤外に飛ばす」ことで消えたことにする（デモ用）
        return { ...p, x: -1, y: -1 }; 
      }
      return p;
    }).filter(p => p.x !== -1));

    // onMove コールバック
    if (onMove) {
      const from: Square = { file: targetPiece.x, rank: targetPiece.y };
      const to: Square = { file: toFile, rank: toRank };
      const usi = `${squareToUSI(from)}${squareToUSI(to)}`; // 成りは未考慮
      
      onMove({
        from,
        to,
        piece: targetPiece.type,
        owner: targetPiece.owner,
        promotedBefore: !!targetPiece.promoted,
        promotedAfter: false, // 成り判定は未実装
        usi,
      });
    }

    setSelectedPieceId(null);
  };

  const handlePieceDrop = useCallback((pieceId: string, clientX: number, clientY: number) => {
    const square = pixelToSquare(clientX, clientY);
    if (!square) return;
    movePiece(pieceId, square.file, square.rank);
  }, [pieces, onMove]); // pieces 依存を追加

  const handlePieceClick = (pieceId: string) => {
    const piece = pieces.find(p => p.id === pieceId);
    if (!piece) return;

    // 自分の駒をクリックした場合
    // (簡易的に owner チェックは省略、全駒操作可能とするならこれでもOK)
    // 本来は `if (piece.owner === mySide)` のようなチェックが必要
    
    if (selectedPieceId === pieceId) {
      // 選択解除
      setSelectedPieceId(null);
    } else if (selectedPieceId) {
      // 既に他の駒を選択中に、別の駒をクリック
      const selectedPiece = pieces.find(p => p.id === selectedPieceId);
      if (selectedPiece && selectedPiece.owner === piece.owner) {
        // 自分の駒なら選択切り替え
        setSelectedPieceId(pieceId);
      } else {
        // 相手の駒なら「取る」移動
        movePiece(selectedPieceId, piece.x, piece.y);
      }
    } else {
      // 新規選択
      setSelectedPieceId(pieceId);
    }
  };

  const handleSquareClick = (e: React.MouseEvent) => {
    if (!selectedPieceId) return;

    // クリック位置の座標を取得
    const square = pixelToSquare(e.clientX, e.clientY);
    if (!square) return;

    // 空きマスをクリックした場合は移動
    // (駒があるマスのクリックは handlePieceClick で処理されるため、ここは空きマスのみ)
    // ただし、DOM構造上、駒がマスの div の上にあるとは限らない（絶対配置）
    // 駒には pointer-events: auto があるので、駒をクリックしたら handlePieceClick が呼ばれ、
    // ここ（handleSquareClick）にはバブルアップしてくる可能性がある。
    // e.stopPropagation() を Piece 側でするか、ここで判定するか。
    // 今回は Piece 側で stopPropagation していないので、ここで駒があるかチェックする。
    
    const pieceOnSquare = pieces.find(p => p.x === square.file && p.y === square.rank);
    if (!pieceOnSquare) {
      movePiece(selectedPieceId, square.file, square.rank);
    }
  };

  // 盤面のセルを生成
  const renderCells = () => {
    const cells = [];
    for (let y = 1; y <= ROWS; y++) {
      for (let x = 9; x >= 1; x--) {
        const isSelectedTarget = selectedPieceId && 
          pieces.find(p => p.id === selectedPieceId)?.x === x && 
          pieces.find(p => p.id === selectedPieceId)?.y === y;

        cells.push(
          <div
            key={`${x}-${y}`}
            className="board-cell"
            onClick={handleSquareClick}
            style={{
              width: "100%",
              height: "100%",
              border: "1px solid #000",
              backgroundColor: isSelectedTarget ? "#ffd700" : "#f0d9b5", // 選択中は金色
              boxSizing: "border-box",
              position: "relative",
            }}
          >
            {/* 座標表示（デバッグ用） */}
            <span style={{ position: "absolute", bottom: 0, right: 0, fontSize: "8px", opacity: 0.5 }}>
              {x}{y}
            </span>
          </div>
        );
      }
    }
    return cells;
  };

  return (
    <div 
      ref={boardRef}
      data-shogi-board-root="1"
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${COLS}, calc(${PIECE_WIDTH}px * ${scale}))`,
        gridTemplateRows: `repeat(${ROWS}, calc(${PIECE_HEIGHT}px * ${scale}))`,
        width: `calc(${COLS * PIECE_WIDTH}px * ${scale})`,
        height: `calc(${ROWS * PIECE_HEIGHT}px * ${scale})`,
        border: "2px solid #5d4037",
        position: "relative",
        userSelect: "none",
      }}
    >
      {/* 背景のマス目 */}
      {renderCells()}

      {/* 駒の描画 (絶対配置で重ねる) */}
      {pieces.map(piece => {
        const { x, y } = squareToPixel(piece.x, piece.y);
        const isSelected = piece.id === selectedPieceId;

        return (
          <div
            key={piece.id}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              transform: `translate(${x}, ${y})`,
              width: `calc(${PIECE_WIDTH}px * ${scale})`,
              height: `calc(${PIECE_HEIGHT}px * ${scale})`,
              zIndex: isSelected ? 20 : 10,
              pointerEvents: "none", // コンテナはイベントを通す
              transition: "transform 0.2s cubic-bezier(0.25, 0.1, 0.25, 1)",
            }}
          >
            <div style={{ pointerEvents: "auto" }}> {/* 駒自体はイベントを受け取る */}
              <Piece
                type={piece.type}
                owner={piece.owner}
                promoted={piece.promoted}
                onDrop={(dropX, dropY) => handlePieceDrop(piece.id, dropX, dropY)}
                onClick={() => handlePieceClick(piece.id)}
                selected={isSelected}
                enableAnimation={true}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};
