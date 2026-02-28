"use client";
import React from "react";
import AnnotateView from "@/components/AnnotateView";

export default function AnnotatePage() {
  return (
    <div className="flex flex-col h-full w-full bg-[#f9f3e5] text-slate-900">
      <main className="flex-1 min-h-0 overflow-hidden">
        <div className="w-full h-full px-2 py-2">
          <div className="h-full rounded-xl border border-black/10 bg-white/80 p-2 shadow-sm flex flex-col overflow-hidden">
            <div className="flex-1 min-h-0 overflow-hidden">
              <AnnotateView />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
