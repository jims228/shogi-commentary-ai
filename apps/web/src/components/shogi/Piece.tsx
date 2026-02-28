import React from "react";
import { getSpriteStyle, type PieceType, type Owner } from "@/lib/shogi/PieceSprite";
import { useDrag } from "@/hooks/useDrag";
import styles from "./Piece.module.css";

interface PieceProps {
  type: PieceType;
  owner: Owner;
  promoted?: boolean;
  onDrop?: (x: number, y: number) => void;
  onClick?: () => void;
  disabled?: boolean;
  selected?: boolean;
  enableAnimation?: boolean;
}

export const Piece: React.FC<PieceProps> = ({
  type,
  owner,
  promoted = false,
  onDrop,
  onClick,
  disabled = false,
  selected = false,
  enableAnimation = false,
}) => {
  const { isDragging, hasMoved, dragHandlers } = useDrag({ onDrop, disabled });
  
  const spriteStyle = getSpriteStyle(type, promoted);
  
  // 後手（white）の場合は180度回転
  const rotation = owner === "white" ? "rotate(180deg)" : "rotate(0deg)";
  
  // ドラッグ中のスタイルと回転を合成
  const combinedStyle: React.CSSProperties = {
    ...spriteStyle,
    ...dragHandlers.style,
    transform: `${dragHandlers.style.transform} ${rotation}`,
    // ドラッグ中は影をつけるなどの視覚効果
    boxShadow: isDragging ? "0 5px 15px rgba(0,0,0,0.3)" : "none",
    opacity: isDragging ? 0.9 : 1,
    // ドラッグ中は transition を無効化して追従性を確保
    transition: isDragging ? "none" : undefined,
  };

  const handleClick = (e: React.MouseEvent) => {
    // ドラッグ移動が発生した場合はクリックイベントを無視
    if (hasMoved) return;
    if (onClick) onClick();
  };

  return (
    <div
      {...dragHandlers}
      onClick={handleClick}
      style={combinedStyle}
      className={`piece ${enableAnimation && !isDragging ? styles.pieceTransition : ""} ${selected ? styles.selected : ""}`}
      aria-label={`${owner} ${promoted ? "promoted" : ""} ${type}`}
    />
  );
};
