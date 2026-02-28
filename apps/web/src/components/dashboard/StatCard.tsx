import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: LucideIcon;
  colorClass: string; // e.g. "text-shogi-gold"
}

export const StatCard: React.FC<StatCardProps> = ({ label, value, subtext, icon: Icon, colorClass }) => {
  return (
    <div className="rounded-2xl p-4 flex items-center gap-4 border border-black/10 bg-[#fef8e6] shadow-[0_10px_25px_rgba(0,0,0,0.08)] text-[#2b2b2b]">
      <div className={`p-3 rounded-xl border border-black/10 bg-white ${colorClass}`}>
        <Icon size={24} className="text-[#555]" />
      </div>
      <div>
        <p className="text-slate-600 text-xs font-bold uppercase tracking-wider">{label}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-[#2b2b2b]">{value}</span>
          {subtext && <span className="text-xs text-slate-500">{subtext}</span>}
        </div>
      </div>
    </div>
  );
};
