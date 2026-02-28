import React from "react";
import Link from "next/link";
import { LucideIcon, ArrowRight } from "lucide-react";

interface ActionCardProps {
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  color: "blue" | "pink" | "gold";
  progress?: number;
}

export const ActionCard: React.FC<ActionCardProps> = ({ title, description, href, icon: Icon, color, progress }) => {
  const colorStyles = {
    blue: "bg-blue-200 shadow-blue-200/40",
    pink: "bg-rose-200 shadow-rose-200/40",
    gold: "bg-amber-200 shadow-amber-200/40",
  };

  const iconBgStyles = {
    blue: "bg-blue-100",
    pink: "bg-rose-100",
    gold: "bg-amber-100",
  };

  return (
    <Link href={href} className="group block relative">
      <div className={`
        relative overflow-hidden rounded-3xl p-6 h-full transition-all duration-300
        hover:translate-y-[-4px] hover:shadow-xl border border-black/10
        bg-[#fef8e6] text-[#2b2b2b]
      `}>
        {/* Background Gradient Accent */}
        <div className={`absolute top-0 right-0 w-32 h-32 opacity-10 rounded-full blur-3xl -mr-10 -mt-10 ${colorStyles[color]}`} />

        <div className="flex justify-between items-start mb-4">
          <div className={`p-3 rounded-2xl border border-black/10 shadow-sm ${iconBgStyles[color]}`}>
            <Icon size={28} strokeWidth={2.5} className="text-[#555]" />
          </div>
          <div className="bg-white/80 rounded-full p-2 text-[#555] border border-black/10 group-hover:bg-amber-50 transition-colors">
            <ArrowRight size={20} className="text-[#555]" />
          </div>
        </div>

        <h3 className="text-xl font-bold text-[#2b2b2b] mb-2">{title}</h3>
        <p className="text-slate-600 text-sm mb-6 leading-relaxed">{description}</p>

        {progress !== undefined && (
          <div className="w-full bg-white/70 border border-black/10 rounded-full h-2 overflow-hidden">
            <div 
              className={`h-full rounded-full ${iconBgStyles[color]}`} 
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>
    </Link>
  );
};
