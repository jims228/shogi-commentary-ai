import { useState, useCallback, useRef } from "react";

interface Position {
  x: number;
  y: number;
}

interface UseDragOptions {
  onDrop?: (x: number, y: number) => void;
  disabled?: boolean;
}

export const useDrag = ({ onDrop, disabled = false }: UseDragOptions = {}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState<Position>({ x: 0, y: 0 });
  const [hasMoved, setHasMoved] = useState(false);
  
  // ドラッグ開始時のポインター位置と要素の初期位置を保持
  const startPosRef = useRef<Position>({ x: 0, y: 0 });
  const currentPosRef = useRef<Position>({ x: 0, y: 0 });

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (disabled) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const element = e.currentTarget as HTMLElement;
    element.setPointerCapture(e.pointerId);
    
    setIsDragging(true);
    setHasMoved(false);
    startPosRef.current = { x: e.clientX, y: e.clientY };
    currentPosRef.current = { x: 0, y: 0 };
    setPosition({ x: 0, y: 0 });
  }, [disabled]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const deltaX = e.clientX - startPosRef.current.x;
    const deltaY = e.clientY - startPosRef.current.y;
    
    // わずかな動きは無視してクリック判定を優先させても良いが、
    // ここでは少しでも動いたら hasMoved とする
    if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
      setHasMoved(true);
    }
    
    currentPosRef.current = { x: deltaX, y: deltaY };
    setPosition({ x: deltaX, y: deltaY });
  }, [isDragging]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const element = e.currentTarget as HTMLElement;
    element.releasePointerCapture(e.pointerId);
    
    setIsDragging(false);
    
    // ドロップ時の絶対座標を通知 (移動があった場合のみ)
    if (onDrop && hasMoved) {
      onDrop(e.clientX, e.clientY);
    }
    
    // 位置をリセット (Reactのレンダリングサイクルに合わせてリセット)
    setPosition({ x: 0, y: 0 });
  }, [isDragging, onDrop, hasMoved]);

  return {
    isDragging,
    hasMoved,
    position,
    dragHandlers: {
      onPointerDown: handlePointerDown,
      onPointerMove: handlePointerMove,
      onPointerUp: handlePointerUp,
      // タッチ操作でのスクロール防止など
      style: {
        touchAction: "none",
        cursor: isDragging ? "grabbing" : "grab",
        transform: `translate(${position.x}px, ${position.y}px)`,
        zIndex: isDragging ? 1000 : "auto",
        position: "relative" as const,
      }
    }
  };
};
