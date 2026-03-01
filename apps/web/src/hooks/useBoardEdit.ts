import { useState, useCallback } from "react";
import { cloneBoard, type BoardMatrix, type HandsState } from "@/lib/board";

export type UseBoardEditParams = {
  safeCurrentPly: number;
  isEditMode: boolean;
  isTsumeMode: boolean;
  isAnalyzing: boolean;
  stopEngineAnalysis: () => void;
};

export type UseBoardEditReturn = {
  snapshotOverrides: Record<number, BoardMatrix>;
  handsOverrides: Record<number, HandsState>;
  editHistory: { board: BoardMatrix; hands: HandsState }[];
  handleUndo: () => void;
  handleBoardEdit: (next: BoardMatrix, currentBoard: BoardMatrix, currentHands: HandsState) => void;
  handleHandsEdit: (next: HandsState, currentBoard: BoardMatrix, currentHands: HandsState) => void;
  clearEditHistory: () => void;
  resetBoardEdit: () => void;
};

export const useBoardEdit = ({
  safeCurrentPly,
  isEditMode,
  isTsumeMode,
  isAnalyzing,
  stopEngineAnalysis,
}: UseBoardEditParams): UseBoardEditReturn => {
  const [snapshotOverrides, setSnapshotOverrides] = useState<Record<number, BoardMatrix>>({});
  const [handsOverrides, setHandsOverrides] = useState<Record<number, HandsState>>({});
  const [editHistory, setEditHistory] = useState<{ board: BoardMatrix; hands: HandsState }[]>([]);

  const saveToHistory = useCallback((board: BoardMatrix, hands: HandsState) => {
    setEditHistory((prev) => {
      const newHistory = [...prev, { board: cloneBoard(board), hands: { ...hands } }];
      return newHistory.length > 5 ? newHistory.slice(newHistory.length - 5) : newHistory;
    });
  }, []);

  const handleUndo = useCallback(() => {
    if (editHistory.length === 0) return;
    const prevState = editHistory[editHistory.length - 1];
    setEditHistory((prev) => prev.slice(0, -1));
    setSnapshotOverrides((prev) => ({ ...prev, [safeCurrentPly]: cloneBoard(prevState.board) }));
    setHandsOverrides((prev) => ({ ...prev, [safeCurrentPly]: { ...prevState.hands } }));
    if (isAnalyzing) { stopEngineAnalysis(); }
  }, [editHistory, safeCurrentPly, isAnalyzing, stopEngineAnalysis]);

  const handleBoardEdit = useCallback((next: BoardMatrix, currentBoard: BoardMatrix, currentHands: HandsState) => {
    if (!isEditMode && !isTsumeMode) return;
    saveToHistory(currentBoard, currentHands);
    setSnapshotOverrides((prev) => ({ ...prev, [safeCurrentPly]: cloneBoard(next) }));
    if (isAnalyzing) { stopEngineAnalysis(); }
  }, [isEditMode, isTsumeMode, safeCurrentPly, saveToHistory, isAnalyzing, stopEngineAnalysis]);

  const handleHandsEdit = useCallback((next: HandsState, currentBoard: BoardMatrix, currentHands: HandsState) => {
    if (!isEditMode && !isTsumeMode) return;
    saveToHistory(currentBoard, currentHands);
    setHandsOverrides((prev) => ({ ...prev, [safeCurrentPly]: next }));
    if (isAnalyzing) { stopEngineAnalysis(); }
  }, [isEditMode, isTsumeMode, safeCurrentPly, saveToHistory, isAnalyzing, stopEngineAnalysis]);

  const clearEditHistory = useCallback(() => {
    setEditHistory([]);
  }, []);

  const resetBoardEdit = useCallback(() => {
    setSnapshotOverrides({});
    setHandsOverrides({});
    setEditHistory([]);
  }, []);

  return {
    snapshotOverrides,
    handsOverrides,
    editHistory,
    handleUndo,
    handleBoardEdit,
    handleHandsEdit,
    clearEditHistory,
    resetBoardEdit,
  };
};
