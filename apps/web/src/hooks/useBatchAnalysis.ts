import { useState, useCallback, useRef } from "react";
import { type AnalysisCache } from "@/lib/analysisUtils";
import { showToast } from "@/components/ui/toast";
import { fetchWithAuth } from "@/lib/fetchWithAuth";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8787";

type UseBatchAnalysisReturn = {
  batchData: AnalysisCache;
  setBatchData: React.Dispatch<React.SetStateAction<AnalysisCache>>;
  isBatchAnalyzing: boolean;
  setIsBatchAnalyzing: React.Dispatch<React.SetStateAction<boolean>>;
  progress: number; // 0 to 100
  runBatchAnalysis: (usi: string, totalMoves: number, moveSequence: string[]) => Promise<void>;
  cancelBatchAnalysis: () => void;
  resetBatchData: () => void;
};

export const useBatchAnalysis = (): UseBatchAnalysisReturn => {
  const [batchData, setBatchData] = useState<AnalysisCache>({});
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const resetBatchData = useCallback(() => {
    setBatchData({});
    setProgress(0);
  }, []);

  const cancelBatchAnalysis = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsBatchAnalyzing(false);
  }, []);

  const runBatchAnalysis = useCallback(async (usi: string, totalMoves: number, moveSequence: string[]) => {
    if (isBatchAnalyzing) return;

    setIsBatchAnalyzing(true);
    setProgress(0);
    
    // 前回の解析をキャンセル
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetchWithAuth(`${API_BASE}/api/analysis/batch-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          usi,
          moves: moveSequence,
          time_budget_ms: 60000, // 最大60秒
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) throw new Error("Network response was not ok");
      if (!response.body) throw new Error("No body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        
        // 最後の行は不完全な可能性があるためバッファに残す
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            
            if (data.error) {
                console.error("Batch Analysis Error from server:", data.error);
                continue;
            }

            // 解析結果をStateに反映
            if (typeof data.ply === "number" && data.result) {
              setBatchData((prev) => ({
                ...prev,
                [data.ply]: data.result,
              }));
              
              // 進捗更新
              setProgress(Math.round(((data.ply + 1) / (totalMoves + 1)) * 100));
            }
          } catch (e) {
            console.error("Parse error", e);
          }
        }
      }
      
      showToast({ title: "全体解析完了", variant: "default" });

    } catch (error: any) {
      if (error.name !== "AbortError") {
        console.error("Batch analysis failed:", error);
        showToast({ title: "解析中断/失敗", variant: "default" });
      }
    } finally {
      setIsBatchAnalyzing(false);
      abortControllerRef.current = null;
    }
  }, [isBatchAnalyzing]);

  return {
    batchData,
    setBatchData,
    isBatchAnalyzing,
    setIsBatchAnalyzing,
    progress,
    runBatchAnalysis,
    cancelBatchAnalysis,
    resetBatchData,
  };
};