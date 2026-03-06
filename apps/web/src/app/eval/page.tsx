"use client";

import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { ShogiBoard } from "@/components/ShogiBoard";
import { buildPositionFromUsi } from "@/lib/board";
import { usiMoveToCoords } from "@/lib/sfen";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Upload,
  Eye,
  EyeOff,
  FolderOpen,
  SkipForward,
  Trash2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EvalRecord = {
  id: string;
  sfen: string;
  ply: number;
  user_move: string | null;
  name: string;
  legacy_explanation: string;
  planner_explanation: string;
  planner_plan_flow: string;
  planner_plan_topic_keyword: string;
  planner_plan_surface_reason: string;
  planner_plan_deep_reason: string;
  auto_legacy_score: number | null;
  auto_planner_score: number | null;
  is_fallback: boolean;
  flow_score: number | null;
  keyword_score: number | null;
  depth_score: number | null;
  readability_score: number | null;
  preference: "legacy" | "planner" | "tie" | null;
  notes: string;
};

type EvalData = {
  version: string;
  created: string;
  total: number;
  scoring_guide: Record<string, string>;
  records: EvalRecord[];
};

type ABOrder = { a: "legacy" | "planner"; b: "legacy" | "planner" };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STORAGE_KEY = "shogi_human_eval_state";

function shuffleAB(seed: string): ABOrder {
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (h * 31 + seed.charCodeAt(i)) | 0;
  }
  return h % 2 === 0
    ? { a: "planner", b: "legacy" }
    : { a: "legacy", b: "planner" };
}

function extractPrevMoves(sfen: string, n = 5): string[] {
  const parts = sfen.split(/\s+/);
  const idx = parts.indexOf("moves");
  if (idx === -1) return [];
  const all = parts.slice(idx + 1);
  return all.slice(Math.max(0, all.length - n));
}

function formatUsiSimple(usi: string): string {
  if (!usi) return "-";
  if (usi.includes("*")) {
    const [p, dst] = usi.split("*");
    const file = dst[0];
    const rank = dst[1];
    const rankNum = rank.charCodeAt(0) - "a".charCodeAt(0) + 1;
    return `${file}${rankNum}${p}打`;
  }
  const sf = usi[0],
    sr = String(usi[1].charCodeAt(0) - "a".charCodeAt(0) + 1);
  const df = usi[2],
    dr = String(usi[3].charCodeAt(0) - "a".charCodeAt(0) + 1);
  const promo = usi.endsWith("+") ? "成" : "";
  return `${sf}${sr}→${df}${dr}${promo}`;
}

// ---------------------------------------------------------------------------
// ScoreRow
// ---------------------------------------------------------------------------

function ScoreRow({
  label,
  guide,
  value,
  onChange,
}: {
  label: string;
  guide: string;
  value: number | null;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-900">{label}</span>
        <span className="text-xs text-slate-500">{guide}</span>
      </div>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => onChange(n)}
            className={`flex-1 h-8 rounded text-sm font-bold transition-colors ${
              value === n
                ? "bg-rose-500 text-white"
                : "bg-stone-200 text-slate-700 hover:bg-stone-300"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function EvalPage() {
  const [evalData, setEvalData] = useState<EvalData | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [results, setResults] = useState<Map<string, Partial<EvalRecord>>>(
    new Map()
  );
  const [revealLabel, setRevealLabel] = useState(false);
  const [loadMessage, setLoadMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.results) {
          setResults(new Map(Object.entries(parsed.results)));
        }
        if (parsed.currentIdx !== undefined) {
          setCurrentIdx(parsed.currentIdx);
        }
        if (parsed.evalData) {
          setEvalData(parsed.evalData);
          setLoadMessage({ type: "ok", text: `保存データから復元 (${parsed.evalData.records?.length ?? 0}件)` });
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Save to localStorage on change
  useEffect(() => {
    if (!evalData) return;
    try {
      const obj: Record<string, unknown> = {};
      results.forEach((v, k) => {
        obj[k] = v;
      });
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ evalData, currentIdx, results: obj })
      );
    } catch {
      // ignore
    }
  }, [evalData, currentIdx, results]);

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const data = JSON.parse(ev.target?.result as string) as EvalData;
          if (!data.records || !Array.isArray(data.records) || data.records.length === 0) {
            setLoadMessage({ type: "err", text: "レコードが見つかりません" });
            return;
          }
          // New file takes priority: clear old state completely
          setEvalData(data);
          setResults(new Map());
          setCurrentIdx(0);
          setRevealLabel(false);
          setLoadMessage({ type: "ok", text: `${file.name} を読み込みました (${data.records.length}件)` });
        } catch {
          setLoadMessage({ type: "err", text: `${file.name} の読み込みに失敗しました (JSON形式エラー)` });
        }
      };
      reader.readAsText(file);
      // Reset input value so the same file can be re-selected
      e.target.value = "";
    },
    []
  );

  const handleOpenNew = useCallback(() => {
    const hasProgress = results.size > 0;
    if (hasProgress && !confirm("現在の評価データを破棄して新しいファイルを開きますか？")) {
      return;
    }
    setEvalData(null);
    setResults(new Map());
    setCurrentIdx(0);
    setRevealLabel(false);
    setLoadMessage(null);
    localStorage.removeItem(STORAGE_KEY);
    // Trigger file picker after state clears
    setTimeout(() => fileInputRef.current?.click(), 50);
  }, [results]);

  const handleClearStorage = useCallback(() => {
    if (confirm("保存データをすべてクリアしますか？ (評価の進捗も消えます)")) {
      localStorage.removeItem(STORAGE_KEY);
      setEvalData(null);
      setResults(new Map());
      setCurrentIdx(0);
      setRevealLabel(false);
      setLoadMessage({ type: "ok", text: "保存データをクリアしました" });
    }
  }, []);

  const record = evalData?.records?.[currentIdx] ?? null;
  const totalRecords = evalData?.records?.length ?? 0;

  const abOrder = useMemo<ABOrder>(
    () => (record ? shuffleAB(record.id) : { a: "legacy", b: "planner" }),
    [record]
  );

  const boardState = useMemo(() => {
    if (!record) return null;
    try {
      return buildPositionFromUsi(record.sfen);
    } catch {
      return null;
    }
  }, [record]);

  const lastMoveCoords = useMemo(() => {
    if (!record?.user_move) return undefined;
    return usiMoveToCoords(record.user_move) ?? undefined;
  }, [record]);

  const prevMoves = useMemo(
    () => (record ? extractPrevMoves(record.sfen) : []),
    [record]
  );

  const currentResult = useMemo(() => {
    if (!record) return {};
    return results.get(record.id) ?? {};
  }, [record, results]);

  const updateField = useCallback(
    (field: string, value: unknown) => {
      if (!record) return;
      setResults((prev) => {
        const next = new Map(prev);
        const existing = next.get(record.id) ?? {};
        next.set(record.id, { ...existing, [field]: value });
        return next;
      });
    },
    [record]
  );

  const isComplete = useCallback(
    (rec: EvalRecord) => {
      const r = results.get(rec.id);
      if (!r) return false;
      return (
        r.flow_score != null &&
        r.keyword_score != null &&
        r.depth_score != null &&
        r.readability_score != null &&
        r.preference != null
      );
    },
    [results]
  );

  const completedCount = useMemo(
    () => evalData?.records.filter((r) => isComplete(r)).length ?? 0,
    [evalData, isComplete]
  );

  const goNext = useCallback(() => {
    setCurrentIdx((i) => Math.min(i + 1, totalRecords - 1));
    setRevealLabel(false);
  }, [totalRecords]);

  const goPrev = useCallback(() => {
    setCurrentIdx((i) => Math.max(i - 1, 0));
    setRevealLabel(false);
  }, []);

  const skipToNextUnanswered = useCallback(() => {
    if (!evalData) return;
    for (let i = currentIdx + 1; i < evalData.records.length; i++) {
      if (!isComplete(evalData.records[i])) {
        setCurrentIdx(i);
        setRevealLabel(false);
        return;
      }
    }
    for (let i = 0; i < currentIdx; i++) {
      if (!isComplete(evalData.records[i])) {
        setCurrentIdx(i);
        setRevealLabel(false);
        return;
      }
    }
  }, [evalData, currentIdx, isComplete]);

  const handleDownload = useCallback(() => {
    if (!evalData) return;
    const output = {
      ...evalData,
      records: evalData.records.map((rec) => {
        const r = results.get(rec.id) ?? {};
        return { ...rec, ...r };
      }),
    };
    const blob = new Blob([JSON.stringify(output, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `human_eval_results_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [evalData, results]);

  const handleReset = useCallback(() => {
    if (confirm("全評価データをリセットしますか？")) {
      setResults(new Map());
      setCurrentIdx(0);
      setRevealLabel(false);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Upload screen
  // -----------------------------------------------------------------------
  if (!evalData) {
    return (
      <div className="eval-plain h-screen flex items-center justify-center bg-stone-50">
        <div className="bg-white border border-stone-300 rounded-2xl shadow-sm p-10 max-w-md w-full text-center">
          <h1 className="text-2xl font-bold text-slate-900 mb-2">
            解説 A/B 評価
          </h1>
          <p className="text-slate-600 mb-6 text-sm leading-relaxed">
            人手評価用JSONファイルを読み込んでください。
            <br />
            <code className="text-xs bg-stone-100 text-slate-800 px-1.5 py-0.5 rounded">
              data/human_eval/eval_set_*.json
            </code>
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileUpload}
            className="hidden"
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            className="gap-2 h-11 px-6 text-base"
          >
            <Upload className="w-4 h-4" />
            JSONファイルを選択
          </Button>

          {loadMessage && (
            <div className={`mt-4 text-sm px-3 py-2 rounded-lg ${
              loadMessage.type === "ok"
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}>
              {loadMessage.text}
            </div>
          )}

          <div className="mt-6 pt-4 border-t border-stone-200">
            <button
              onClick={handleClearStorage}
              className="text-xs text-slate-500 hover:text-red-600 transition-colors inline-flex items-center gap-1"
            >
              <Trash2 className="w-3 h-3" />
              保存データをクリア
            </button>
          </div>
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Main eval UI
  // -----------------------------------------------------------------------
  const explanationA =
    abOrder.a === "legacy"
      ? record?.legacy_explanation
      : record?.planner_explanation;
  const explanationB =
    abOrder.b === "legacy"
      ? record?.legacy_explanation
      : record?.planner_explanation;

  return (
    <div className="eval-plain h-screen flex flex-col bg-stone-50">
      {/* Hidden file input (always in DOM for re-upload) */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        onChange={handleFileUpload}
        className="hidden"
      />

      {/* ── Header ── */}
      <header className="shrink-0 bg-white border-b border-stone-300 px-4 py-2 flex items-center justify-between">
        <h1 className="text-base font-bold text-slate-900">解説 A/B 評価</h1>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-700 font-medium">
            {completedCount}/{totalRecords} 完了
          </span>
          <div className="w-24 h-1.5 bg-stone-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-rose-500 rounded-full transition-all"
              style={{
                width: `${totalRecords > 0 ? (completedCount / totalRecords) * 100 : 0}%`,
              }}
            />
          </div>
          <Button variant="outline" size="sm" onClick={handleOpenNew} className="text-slate-800 border-stone-300">
            <FolderOpen className="w-3.5 h-3.5 mr-1" />
            別ファイル
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload} className="text-slate-800 border-stone-300">
            <Download className="w-3.5 h-3.5 mr-1" />
            結果DL
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="text-slate-500 hover:text-red-600"
          >
            リセット
          </Button>
        </div>
      </header>

      {/* Load message banner */}
      {loadMessage && (
        <div className={`shrink-0 px-4 py-1.5 text-xs text-center ${
          loadMessage.type === "ok"
            ? "bg-emerald-50 text-emerald-800"
            : "bg-red-50 text-red-800"
        }`}>
          {loadMessage.text}
        </div>
      )}

      {/* ── 3-column layout ── */}
      <div className="flex-1 min-h-0 max-w-[1500px] w-full mx-auto px-4 py-4 xl:grid xl:grid-cols-[460px_minmax(0,1fr)_360px] gap-4">

        {/* ══ LEFT: Board + Info + Nav ══ */}
        <div className="flex flex-col gap-3 min-h-0">
          {/* Board card */}
          <div className="bg-white border border-stone-300 rounded-2xl shadow-sm p-3 flex flex-col items-center shrink-0">
            {boardState ? (
              <ShogiBoard
                board={boardState.board}
                hands={boardState.hands}
                mode="view"
                lastMove={lastMoveCoords}
                showCoordinates
                interactionDisabled
              />
            ) : (
              <div className="h-[360px] flex items-center justify-center text-slate-500 text-sm">
                盤面を読み込めません
              </div>
            )}
            <div className="w-full mt-3 space-y-1 text-sm">
              <div className="flex justify-between items-baseline">
                <span className="text-slate-600">局面名</span>
                <span className="font-medium text-slate-900 text-right max-w-[260px] truncate">
                  {record?.name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">手数</span>
                <span className="font-mono text-slate-900">{record?.ply ?? "-"}手目</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">着手</span>
                <span className="font-mono text-slate-900">
                  {record?.user_move ? formatUsiSimple(record.user_move) : "-"}
                </span>
              </div>
              {prevMoves.length > 0 && (
                <div className="pt-1">
                  <span className="text-slate-600 text-xs block mb-1">直前の手順</span>
                  <div className="flex flex-wrap gap-1">
                    {prevMoves.map((m, i) => (
                      <span
                        key={i}
                        className="bg-stone-100 text-slate-800 text-xs px-2 py-0.5 rounded font-mono"
                      >
                        {formatUsiSimple(m)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between gap-2 shrink-0">
            <Button variant="outline" size="sm" onClick={goPrev} disabled={currentIdx === 0} className="text-slate-800 border-stone-300">
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm text-slate-700 font-mono">
              {currentIdx + 1} / {totalRecords}
            </span>
            <Button variant="outline" size="sm" onClick={goNext} disabled={currentIdx === totalRecords - 1} className="text-slate-800 border-stone-300">
              <ChevronRight className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={skipToNextUnanswered} title="次の未回答へ" className="text-slate-600">
              <SkipForward className="w-4 h-4" />
            </Button>
          </div>

          {/* Record list card (internal scroll) */}
          <div className="bg-white border border-stone-300 rounded-2xl shadow-sm p-3 min-h-0 overflow-y-auto flex-1">
            <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2 px-1">
              局面一覧
            </h3>
            {evalData.records.map((rec, i) => (
              <button
                key={rec.id}
                onClick={() => {
                  setCurrentIdx(i);
                  setRevealLabel(false);
                }}
                className={`w-full text-left px-2 py-1 rounded-lg text-xs flex items-center gap-2 transition-colors ${
                  i === currentIdx
                    ? "bg-rose-50 text-rose-900 font-medium"
                    : "text-slate-700 hover:bg-stone-50"
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    isComplete(rec) ? "bg-emerald-500" : "bg-stone-300"
                  }`}
                />
                <span className="truncate">{rec.name || rec.id}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ══ CENTER: Explanations ══ */}
        <div className="flex flex-col gap-3 min-h-0 overflow-y-auto">
          {/* Explanation A */}
          <div className="bg-white border border-stone-300 rounded-2xl shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-stone-200">
              <span className="text-sm font-bold text-slate-900">解説 A</span>
              {revealLabel && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-stone-200 text-slate-800 font-medium">
                  {abOrder.a === "planner" ? "Planner" : "Legacy"}
                </span>
              )}
            </div>
            <div className="px-4 py-3 text-slate-900 text-[15px] leading-relaxed whitespace-pre-wrap min-h-[80px]">
              {explanationA || "(解説なし)"}
            </div>
          </div>

          {/* Explanation B */}
          <div className="bg-white border border-stone-300 rounded-2xl shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-stone-200">
              <span className="text-sm font-bold text-slate-900">解説 B</span>
              {revealLabel && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-stone-200 text-slate-800 font-medium">
                  {abOrder.b === "planner" ? "Planner" : "Legacy"}
                </span>
              )}
            </div>
            <div className="px-4 py-3 text-slate-900 text-[15px] leading-relaxed whitespace-pre-wrap min-h-[80px]">
              {explanationB || "(解説なし)"}
            </div>
          </div>

          {/* Plan details (reveal only) */}
          {revealLabel && record && (
            <div className="bg-stone-100 border border-stone-300 rounded-2xl p-3 text-sm space-y-1">
              <div className="font-bold text-slate-900 mb-1">Plan詳細</div>
              <div className="text-slate-800">
                <span className="text-slate-600 font-medium">flow:</span>{" "}
                {record.planner_plan_flow || "-"}
              </div>
              <div className="text-slate-800">
                <span className="text-slate-600 font-medium">keyword:</span>{" "}
                {record.planner_plan_topic_keyword || "-"}
              </div>
              <div className="text-slate-800">
                <span className="text-slate-600 font-medium">surface_reason:</span>{" "}
                {record.planner_plan_surface_reason || "-"}
              </div>
              <div className="text-slate-800">
                <span className="text-slate-600 font-medium">deep_reason:</span>{" "}
                {record.planner_plan_deep_reason || "-"}
              </div>
            </div>
          )}

          {/* Reveal toggle */}
          <button
            onClick={() => setRevealLabel((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
          >
            {revealLabel ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            {revealLabel ? "ラベルを隠す" : "正解ラベルを見る"}
          </button>
        </div>

        {/* ══ RIGHT: Evaluation form ══ */}
        <div className="flex flex-col gap-3 min-h-0 overflow-y-auto">
          <div className="bg-white border border-stone-300 rounded-2xl shadow-sm p-4 space-y-3">
            <h3 className="text-sm font-bold text-slate-900 border-b border-stone-200 pb-2">
              評価
            </h3>

            <ScoreRow
              label="解説の流れ"
              guide="1=不自然 5=自然"
              value={(currentResult.flow_score as number) ?? null}
              onChange={(v) => updateField("flow_score", v)}
            />
            <ScoreRow
              label="キーワード"
              guide="1=不適切 5=適切"
              value={(currentResult.keyword_score as number) ?? null}
              onChange={(v) => updateField("keyword_score", v)}
            />
            <ScoreRow
              label="深さ"
              guide="1=浅い 5=洞察的"
              value={(currentResult.depth_score as number) ?? null}
              onChange={(v) => updateField("depth_score", v)}
            />
            <ScoreRow
              label="読みやすさ"
              guide="1=難 5=易"
              value={(currentResult.readability_score as number) ?? null}
              onChange={(v) => updateField("readability_score", v)}
            />

            {/* Preference */}
            <div className="space-y-1.5">
              <span className="text-sm font-semibold text-slate-900 block">
                どちらが良い？
              </span>
              <div className="grid grid-cols-3 gap-2">
                {(["A", "B", "tie"] as const).map((opt) => {
                  const prefValue =
                    opt === "A"
                      ? abOrder.a
                      : opt === "B"
                        ? abOrder.b
                        : ("tie" as const);
                  const isSelected = currentResult.preference === prefValue;
                  return (
                    <button
                      key={opt}
                      onClick={() => updateField("preference", prefValue)}
                      className={`h-9 rounded text-sm font-bold transition-colors ${
                        isSelected
                          ? "bg-rose-500 text-white"
                          : "bg-stone-200 text-slate-800 hover:bg-stone-300"
                      }`}
                    >
                      {opt === "tie" ? "同等" : `解説 ${opt}`}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-900 block">
                メモ
              </label>
              <textarea
                className="w-full border border-stone-300 rounded-lg p-2 text-sm text-slate-900 bg-white resize-none focus:ring-2 focus:ring-rose-300 focus:border-rose-300 focus:outline-none"
                rows={3}
                placeholder="気づいた点があれば..."
                value={(currentResult.notes as string) ?? ""}
                onChange={(e) => updateField("notes", e.target.value)}
              />
            </div>
          </div>

          {/* Actions card */}
          <div className="bg-white border border-stone-300 rounded-2xl shadow-sm p-3 space-y-2 shrink-0">
            {record && isComplete(record) && (
              <div className="text-center text-xs font-medium text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg py-1.5">
                この局面の評価は完了しています
              </div>
            )}

            {record && isComplete(record) && currentIdx < totalRecords - 1 && (
              <Button onClick={goNext} className="w-full gap-1 h-9 text-sm">
                次の局面へ
                <ChevronRight className="w-4 h-4" />
              </Button>
            )}

            {record &&
              isComplete(record) &&
              currentIdx === totalRecords - 1 && (
                <Button onClick={handleDownload} className="w-full gap-1 h-9 text-sm">
                  <Download className="w-4 h-4" />
                  全結果をダウンロード
                </Button>
              )}
          </div>
        </div>
      </div>
    </div>
  );
}
