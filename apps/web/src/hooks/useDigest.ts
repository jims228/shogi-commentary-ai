import { useState, useCallback, useEffect, useRef } from "react";
import { showToast } from "@/components/ui/toast";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { type AnalysisCache, getPrimaryEvalScore } from "@/lib/analysisUtils";
import type { BioshogiData } from "@/components/annotate/BioshogiPanel";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8787";

export type SkillScore = {
  score: number;
  grade: string;
  details: {
    best: number;
    second: number;
    blunder: number;
    evaluated: number;
  };
};

export type TensionData = {
  timeline: number[];
  avg: number;
  label: string;
};

export type UseDigestParams = {
  batchData: AnalysisCache;
  isBatchAnalyzing: boolean;
  totalMoves: number;
  moveSequence: string[];
  moveImpacts: Record<number, { diff: number | null }>;
  initialTurn: string;
  usi: string;
};

export type UseDigestReturn = {
  gameDigest: string;
  digestMetaSource: string;
  bioshogiData: BioshogiData | null;
  skillScore: SkillScore | null;
  tensionData: TensionData | null;
  isDigesting: boolean;
  digestCooldownLeft: number;
  isReportModalOpen: boolean;
  setIsReportModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  handleGenerateGameDigest: (forceLlm?: boolean) => Promise<void>;
  resetDigest: () => void;
};

export const useDigest = ({
  batchData,
  isBatchAnalyzing,
  totalMoves,
  moveSequence,
  moveImpacts,
  initialTurn,
  usi,
}: UseDigestParams): UseDigestReturn => {
  const [gameDigest, setGameDigest] = useState("");
  const [digestMetaSource, setDigestMetaSource] = useState("");
  const [bioshogiData, setBioshogiData] = useState<BioshogiData | null>(null);
  const [isDigesting, setIsDigesting] = useState(false);
  const [digestCooldownUntil, setDigestCooldownUntil] = useState(0);
  const [digestCooldownLeft, setDigestCooldownLeft] = useState(0);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [skillScore, setSkillScore] = useState<SkillScore | null>(null);
  const [tensionData, setTensionData] = useState<TensionData | null>(null);

  const isDigestingRef = useRef(false);
  const digestCooldownRef = useRef(0);

  // クールダウンタイマー
  useEffect(() => {
    if (!digestCooldownUntil) {
      setDigestCooldownLeft(0);
      return;
    }
    const timer = setInterval(() => {
      const left = Math.max(0, Math.ceil((digestCooldownUntil - Date.now()) / 1000));
      setDigestCooldownLeft(left);
      if (left <= 0) setDigestCooldownUntil(0);
    }, 500);
    return () => clearInterval(timer);
  }, [digestCooldownUntil]);

  // バッチ解析完了時にbioshogi情報を自動取得
  useEffect(() => {
    if (isBatchAnalyzing) return;
    if (Object.keys(batchData).length < 5) return;
    if (!usi) return;
    fetch(`${API_BASE}/api/analysis/report?usi=${encodeURIComponent(usi)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.bioshogi) setBioshogiData(data.bioshogi as BioshogiData);
      })
      .catch(() => {
        /* bioshogiなしで続行 */
      });
  }, [isBatchAnalyzing, usi]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerateGameDigest = useCallback(
    async (forceLlm = false) => {
      if (isDigestingRef.current) return;
      if (digestCooldownRef.current && Date.now() < digestCooldownRef.current) return;
      const hasData = Object.keys(batchData).length > 0;
      if (!hasData) {
        showToast({ title: "先に全体解析を行ってください", variant: "default" });
        return;
      }
      isDigestingRef.current = true;
      setIsDigesting(true);
      setIsReportModalOpen(true);
      setGameDigest("");
      setDigestMetaSource("");
      setSkillScore(null);
      setTensionData(null);
      const evalList = [];
      for (let i = 0; i <= totalMoves; i++) {
        const score = getPrimaryEvalScore(batchData[i]);
        evalList.push(score || 0);
      }
      try {
        const notesForDigest = moveSequence
          .map((move, index) => {
            const ply = index + 1;
            const delta_cp = moveImpacts[ply]?.diff ?? null;
            return { ply, move, delta_cp };
          })
          .filter((n) => n.delta_cp !== null);

        const url = forceLlm
          ? `${API_BASE}/api/explain/digest?force_llm=1`
          : `${API_BASE}/api/explain/digest`;
        const res = await fetchWithAuth(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            total_moves: totalMoves,
            eval_history: evalList,
            winner: null,
            notes: notesForDigest,
            bioshogi: bioshogiData ?? null,
            initial_turn: initialTurn,
          }),
        });
        if (!res.ok) {
          let detail = "";
          try {
            const data = await res.json();
            detail = data?.detail || "";
          } catch {
            try {
              detail = await res.text();
            } catch {
              detail = "";
            }
          }
          if (res.status === 429) {
            const ra = Number(res.headers.get("retry-after") ?? "30");
            const waitSec = Number.isFinite(ra) && ra > 0 ? Math.ceil(ra) : 30;
            console.log("[digest] retry-after:", waitSec);
            const cooldownTime = Date.now() + waitSec * 1000;
            digestCooldownRef.current = cooldownTime;
            setDigestCooldownUntil(cooldownTime);
            const base =
              detail || "レポート生成の利用制限に達しました。しばらく待ってから再度お試しください。";
            setGameDigest(`${base}\n\nあと ${waitSec} 秒待ってください。`);
          } else {
            setGameDigest(detail || `レポート生成に失敗しました。(status=${res.status})`);
          }
          return;
        }
        const data = await res.json();
        setGameDigest(data.explanation);
        setDigestMetaSource(data?.meta?.source || "");
        if (data.skill_score) setSkillScore(data.skill_score as SkillScore);
        if (data.tension) setTensionData(data.tension as TensionData);
      } catch {
        setGameDigest("レポート生成に失敗しました。");
      } finally {
        isDigestingRef.current = false;
        setIsDigesting(false);
      }
    },
    [batchData, totalMoves, bioshogiData, moveSequence, moveImpacts, initialTurn],
  );

  const resetDigest = useCallback(() => {
    setGameDigest("");
    setDigestMetaSource("");
    setSkillScore(null);
    setTensionData(null);
  }, []);

  return {
    gameDigest,
    digestMetaSource,
    bioshogiData,
    skillScore,
    tensionData,
    isDigesting,
    digestCooldownLeft,
    isReportModalOpen,
    setIsReportModalOpen,
    handleGenerateGameDigest,
    resetDigest,
  };
};
