import React from "react";

export const Mascot: React.FC = () => {
  return (
    <div className="fixed bottom-8 right-8 hidden lg:flex flex-col items-end z-50 pointer-events-none">
      {/* Speech Bubble */}
      <div className="bg-white text-shogi-dark p-4 rounded-2xl rounded-br-none shadow-xl mb-4 max-w-xs animate-bounce-slow relative">
        <p className="font-bold text-sm">
          「継続は力なり」じゃ！<br/>
          今日も1局、指してみんか？
        </p>
        {/* Triangle for bubble */}
        <div className="absolute -bottom-2 right-4 w-4 h-4 bg-white transform rotate-45"></div>
      </div>

      {/* Character Placeholder (Since we don't have the image file yet) */}
      <div className="w-32 h-32 bg-gradient-to-br from-shogi-gold to-amber-600 rounded-full shadow-2xl border-4 border-white flex items-center justify-center text-4xl relative overflow-hidden">
        <span role="img" aria-label="Master">👴</span>
        {/* Shine effect */}
        <div className="absolute top-0 left-0 w-full h-full bg-white opacity-10 rounded-full"></div>
      </div>
    </div>
  );
};
