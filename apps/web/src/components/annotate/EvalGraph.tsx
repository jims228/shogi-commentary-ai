"use client";

import React, { useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

type EvalPoint = {
  ply: number;
  cp: number | null;
};

type EvalGraphProps = {
  data: EvalPoint[];
  currentPly: number;
  onPlyClick?: (ply: number) => void;
};

// 感度調整: 600 -> 1200
const SIGMOID_FACTOR = 1200;

const toWinRate = (cp: number) => {
  return 1 / (1 + Math.exp(-cp / SIGMOID_FACTOR));
};

export default function EvalGraph({ data, currentPly, onPlyClick }: EvalGraphProps) {
  const chartData = useMemo(() => {
    return data.map((d) => {
      if (d.cp === null) return { ply: d.ply, score: 50, rawCp: 0 };

      // 視点補正 (バックエンドで補正済みなのでそのまま使う)
      const senteCp = d.cp;
      
      // 勝率変換 & 極端な値の丸め
      let winRate = toWinRate(senteCp) * 100;
      if (Math.abs(senteCp) > 9000) {
        winRate = senteCp > 0 ? 99.9 : 0.1;
      }

      return {
        ply: d.ply,
        score: winRate,
        rawCp: senteCp,
      };
    });
  }, [data]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataItem = payload[0].payload;
      return (
        <div className="bg-white/95 border border-slate-200 p-2 rounded shadow-lg text-xs font-mono z-50">
          <div className="font-bold text-slate-700">{label}手目</div>
          <div className={`${dataItem.score >= 50 ? "text-emerald-600" : "text-rose-500"}`}>
            先手勝率: {dataItem.score.toFixed(1)}%
          </div>
          <div className="text-slate-500">
            評価値: {dataItem.rawCp > 0 ? "+" : ""}{dataItem.rawCp}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-[200px] min-h-[200px] select-none bg-white rounded-xl p-2 border border-slate-200">
      <div className="text-xs font-bold text-slate-500 mb-1 px-2">AI評価値（勝率推移）</div>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart
          data={chartData}
          margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
          onClick={(e) => {
            if (e && e.activeLabel !== undefined) onPlyClick?.(Number(e.activeLabel));
          }}
        >
          <defs>
            <linearGradient id="splitColor" x1="0" y1="0" x2="0" y2="1">
              <stop offset={0} stopColor="#10b981" stopOpacity={0.6} />
              <stop offset={1} stopColor="#f43f5e" stopOpacity={0.6} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
          <XAxis 
            dataKey="ply" type="number" domain={['dataMin', 'dataMax']} 
            tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} 
            interval="preserveStartEnd"
          />
          <YAxis 
            domain={[0, 100]} ticks={[0, 50, 100]} 
            tick={{ fontSize: 10, fill: '#aaa' }} tickFormatter={(v) => `${v}%`} 
            tickLine={false} axisLine={false} 
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={50} stroke="#cbd5e1" strokeDasharray="3 3" />
          {currentPly >= 0 && <ReferenceLine x={currentPly} stroke="#f59e0b" strokeWidth={2} />}
          <Area type="monotone" dataKey="score" stroke="#059669" strokeWidth={2} fill="url(#splitColor)" animationDuration={500} activeDot={{ r: 4, strokeWidth: 0, fill: "#f59e0b" }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}