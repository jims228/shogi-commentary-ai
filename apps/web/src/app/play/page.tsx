"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Swords } from "lucide-react";
import LocalPlay from "@/components/play/LocalPlay";

export default function PlayPage() {
  return (
    <div className="min-h-screen pb-20 bg-[#f6f1e6] text-[#2b2b2b]">
      <main className="pt-24">
        <div className="mx-auto max-w-6xl px-4 md:px-8 xl:px-[220px]">
          <div className="rounded-3xl bg-[#f9f3e5] border border-black/10 shadow-[0_20px_40px_rgba(0,0,0,0.1)] p-6 md:p-8 space-y-8">
            <header className="flex items-center gap-4">
              <Link
                href="/"
                className="p-2 rounded-full border border-black/10 bg-white/80 text-[#555] hover:bg-white"
              >
                <ArrowLeft size={20} className="text-[#555]" />
              </Link>
              <div>
                <h1 className="text-3xl font-bold text-[#3a2b17] flex items-center gap-2">
                  <Swords className="text-[#555]" size={32} />
                  実践対局
                </h1>
                <p className="text-sm text-slate-700 mt-1">AIやローカル対局で腕を磨きましょう。</p>
              </div>
            </header>

            <LocalPlay />
          </div>
        </div>
      </main>
    </div>
  );
}
