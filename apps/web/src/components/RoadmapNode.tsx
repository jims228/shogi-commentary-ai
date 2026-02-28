import React from "react";
import { Lesson } from "../types";
import { Star, Lock, Play, CheckCircle } from "lucide-react";

interface RoadmapNodeProps {
  lesson: Lesson;
  isSelected: boolean;
  onClick: () => void;
}

export const RoadmapNode: React.FC<RoadmapNodeProps> = ({ lesson, isSelected, onClick }) => {
  const isLocked = lesson.status === "locked";
  const isCompleted = lesson.status === "completed";

  return (
    <div 
      className={`relative flex flex-col items-center cursor-pointer transition-transform hover:scale-105 ${isLocked ? "opacity-50 cursor-not-allowed" : ""}`}
      onClick={onClick}
    >
      <div 
        className={`
          w-16 h-16 rounded-full flex items-center justify-center border-4 shadow-lg z-10
          ${isSelected ? "ring-4 ring-amber-300 ring-offset-2 ring-offset-[#f6f1e6]" : ""}
          ${isCompleted ? "bg-[#fef1d6] border-amber-300" : 
            isLocked ? "bg-slate-200 border-slate-300" : "bg-[#fde7ef] border-rose-200"}
        `}
      >
        {isLocked ? (
          <Lock className="text-[#555] w-8 h-8" />
        ) : isCompleted ? (
          <CheckCircle className="text-[#555] w-8 h-8" />
        ) : (
          <Play className="text-[#555] w-8 h-8 fill-current" />
        )}
      </div>
      
      {/* Stars for completed lessons */}
      {isCompleted && lesson.stars && (
        <div className="flex gap-1 mt-1 absolute -top-4">
          {[...Array(lesson.stars)].map((_, i) => (
            <Star key={i} className="w-4 h-4 text-yellow-400 fill-current" />
          ))}
        </div>
      )}
      <div className="mt-2 bg-white px-3 py-1 rounded-full border border-black/10 shadow-md">
        <span className="text-sm font-bold text-[#2b2b2b]">{lesson.title}</span>
      </div>
    </div>
  );
};
