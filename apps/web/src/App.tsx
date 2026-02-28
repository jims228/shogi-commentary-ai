'use client';

import React, { useState } from 'react';
import { ManRive } from './components/ManRive';

export default function App() {
  const [correctSignal, setCorrectSignal] = useState(0);

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        gap: 16,
      }}
    >
      <h1 style={{ fontSize: 20, fontWeight: 700 }}>Rive Trigger テスト</h1>

      <ManRive correctSignal={correctSignal} />

      <button
        type="button"
        onClick={() => setCorrectSignal((v) => v + 1)}
        style={{
          padding: '10px 14px',
          borderRadius: 8,
          border: '1px solid currentColor',
          background: 'transparent',
          cursor: 'pointer',
        }}
      >
        正解（驚き発火）
      </button>

      <div style={{ fontSize: 12, opacity: 0.7 }}>correctSignal: {correctSignal}</div>
    </main>
  );
}
