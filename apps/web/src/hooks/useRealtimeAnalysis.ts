import { useState, useCallback, useEffect, useRef } from "react";
import { getSupabaseAccessToken } from "@/lib/fetchWithAuth";
import type { AnalysisCache } from "@/lib/analysisUtils";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8787";

/** 指定手数でUSI文字列をカットする */
const getSubsetUSI = (originalUsi: string, ply: number): string => {
  const parts = originalUsi.trim().split(" moves ");
  const header = parts[0];
  const moveStr = parts[1];
  if (!moveStr) return header;
  const moves = moveStr.trim().split(" ");
  if (ply === 0) return header;
  const neededMoves = moves.slice(0, ply);
  if (neededMoves.length === 0) return header;
  return `${header} moves ${neededMoves.join(" ")}`;
};

export type UseRealtimeAnalysisParams = {
  safeCurrentPly: number;
  isEditMode: boolean;
  usi: string;
};

export type UseRealtimeAnalysisReturn = {
  realtimeAnalysis: AnalysisCache;
  setRealtimeAnalysis: React.Dispatch<React.SetStateAction<AnalysisCache>>;
  isAnalyzing: boolean;
  setIsAnalyzing: React.Dispatch<React.SetStateAction<boolean>>;
  stopEngineAnalysis: () => void;
  startEngineAnalysis: (command: string, ply: number) => Promise<void>;
  requestAnalysisForPly: (ply: number, options?: { force?: boolean }) => void;
  /** EventSource 通信だけを切断する（isAnalyzing は変えない） */
  disconnectStream: () => void;
  /** コンポーネントアンマウント時のクリーンアップ */
  cleanup: () => void;
};

export const useRealtimeAnalysis = ({
  safeCurrentPly,
  isEditMode,
  usi,
}: UseRealtimeAnalysisParams): UseRealtimeAnalysisReturn => {
  const [realtimeAnalysis, setRealtimeAnalysis] = useState<AnalysisCache>({});
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const activeStreamPlyRef = useRef<number | null>(null);
  const requestedPlyRef = useRef<number | null>(null);
  const realtimeAnalysisRef = useRef<AnalysisCache>({});
  const requestIdRef = useRef<string | null>(null);

  // realtimeAnalysisRef を最新に保つ
  useEffect(() => {
    realtimeAnalysisRef.current = realtimeAnalysis;
  }, [realtimeAnalysis]);

  // ★重要: これは「停止ボタン」用。UIの状態もFalseにする。
  const stopEngineAnalysis = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    activeStreamPlyRef.current = null;
    requestedPlyRef.current = null;
    requestIdRef.current = null;
    setIsAnalyzing(false);
  }, []);

  /** EventSource 通信だけを切断する（isAnalyzing は変えない） */
  const disconnectStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    activeStreamPlyRef.current = null;
    requestedPlyRef.current = null;
    requestIdRef.current = null;
  }, []);

  /** コンポーネントアンマウント時のクリーンアップ */
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    activeStreamPlyRef.current = null;
    requestedPlyRef.current = null;
    requestIdRef.current = null;
  }, []);

  const startEngineAnalysis = useCallback(async (command: string, ply: number) => {
    if (!command) return;

    if (activeStreamPlyRef.current === ply && eventSourceRef.current) {
      return;
    }

    let requestId: string | null = null;

    try {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      setRealtimeAnalysis((prev) => {
        const next = { ...prev };
        delete next[ply];
        return next;
      });

      const token = await getSupabaseAccessToken();
      const url = new URL(`${API_BASE}/api/analysis/stream`);
      requestId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      requestIdRef.current = requestId;
      url.searchParams.set("position", command);
      url.searchParams.set("request_id", requestId);
      if (token) {
        url.searchParams.set("access_token", token);
      }
      const es = new EventSource(url.toString());
      eventSourceRef.current = es;
      activeStreamPlyRef.current = ply;

      es.onopen = () => {
        console.log("[Analysis] connect", { requestId, ply });
      };

      es.onmessage = (event) => {
        if (eventSourceRef.current !== es) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.multipv_update) {
            setRealtimeAnalysis((prev) => {
              const previousEntry = prev[ply] || { ok: true, multipv: [] };
              const currentList = previousEntry.multipv ? [...previousEntry.multipv] : [];
              const newItem = payload.multipv_update;
              if (!newItem.multipv) return prev;
              const index = currentList.findIndex(
                (item) => item.multipv === newItem.multipv,
              );
              if (index !== -1) {
                currentList[index] = newItem;
              } else {
                currentList.push(newItem);
              }
              currentList.sort((a, b) => (a.multipv || 0) - (b.multipv || 0));
              return {
                ...prev,
                [ply]: {
                  ...previousEntry,
                  multipv: currentList,
                },
              };
            });
          }
          if (payload.bestmove) {
            setRealtimeAnalysis((prev) => {
              const previousEntry = prev[ply] || { ok: true };
              return {
                ...prev,
                [ply]: {
                  ...previousEntry,
                  bestmove: payload.bestmove,
                  multipv: previousEntry.multipv,
                },
              };
            });
            es.close();
            if (eventSourceRef.current === es) {
              eventSourceRef.current = null;
              activeStreamPlyRef.current = null;
              requestedPlyRef.current = null;
              requestIdRef.current = null;
            }
            console.log("[Analysis] disconnect", { requestId, ply, reason: "bestmove" });
          }
        } catch (e) {
          console.error("[Analysis] Parse error:", e);
        }
      };
      es.onerror = () => {
        console.debug("[Analysis] Stream closed/ended (onerror)");
        es.close();
        if (eventSourceRef.current === es) {
          eventSourceRef.current = null;
          activeStreamPlyRef.current = null;
          requestedPlyRef.current = null;
          requestIdRef.current = null;
        }
        console.log("[Analysis] disconnect", { requestId, ply, reason: "error" });
      };
    } catch (e) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (activeStreamPlyRef.current === ply) {
        activeStreamPlyRef.current = null;
      }
      if (requestIdRef.current === requestId) {
        requestIdRef.current = null;
      }
      if (requestedPlyRef.current === ply) {
        requestedPlyRef.current = null;
      }
      console.error("[Analysis] start failed:", e);
    }
  }, []);

  const requestAnalysisForPly = useCallback(
    (ply: number, options?: { force?: boolean }) => {
      if (options?.force) {
        setRealtimeAnalysis((prev) => {
          const next = { ...prev };
          delete next[ply];
          return next;
        });
        requestedPlyRef.current = null;
      }
      if (requestedPlyRef.current === ply) return;
      const command = getSubsetUSI(usi, ply);
      if (!command) return;
      requestedPlyRef.current = ply;
      void startEngineAnalysis(command, ply);
    },
    [startEngineAnalysis, usi],
  );

  // ★連続検討のキモ: 局面が変わっても isAnalyzing が true なら新しい局面を解析しに行く
  useEffect(() => {
    if (isAnalyzing && !isEditMode) {
      const hasRealtimeResult = !!realtimeAnalysisRef.current[safeCurrentPly]?.bestmove;
      const isCurrentlyStreamingThis = activeStreamPlyRef.current === safeCurrentPly;

      // 解析済み(キャッシュあり)でなく、現在ストリーミング中でもない場合のみリクエスト
      if (!isCurrentlyStreamingThis && !hasRealtimeResult) {
        requestAnalysisForPly(safeCurrentPly);
      }
    }
  }, [safeCurrentPly, isAnalyzing, isEditMode, requestAnalysisForPly, usi]);

  return {
    realtimeAnalysis,
    setRealtimeAnalysis,
    isAnalyzing,
    setIsAnalyzing,
    stopEngineAnalysis,
    startEngineAnalysis,
    requestAnalysisForPly,
    disconnectStream,
    cleanup,
  };
};
