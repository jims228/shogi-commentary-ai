import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 頭金 Lv1
 * - 玉の“頭（前）”に金を打って、玉を動けなくする
 * - 盤面・文章は自作
 */
export const GOLD_ATAMAKIN_L1: LessonStep[] = [
  {
    type: "guided",
    title: "頭金（Lv1）: ガイド",
    // 相手玉(5一)。先手歩(5三)が5二を支える。5二に金を打つ。
    sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b G 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "玉の頭に金！5二に金を打って王手しよう。",
        arrows: [{ to: sq(5, 2), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 2), sq(5, 1)],
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 2) }],
        after: "auto",
        wrongHint: "頭金は、玉の前のマスに金を打つ手筋だよ。",
      },
      {
        prompt: "（歩が支えていると、玉が金を取りにくい）",
        sfen: "position sfen 4k4/4G4/4P4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 260,
      },
      {
        prompt: "次は逃げ道をふさごう。歩を一歩進めてみよう（5三→5二）。",
        // 5三の歩がある形（説明用）。5二は空にして、歩を進める練習。
        sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b - 1",
        arrows: [{ from: sq(5, 3), to: sq(5, 2), kind: "move" }],
        highlights: [sq(5, 2)],
        expectedMoves: [{ kind: "move", from: sq(5, 3), to: sq(5, 2) }],
        after: "auto",
        wrongHint: "5三→5二。玉の頭まわりは“逃げ道を減らす”意識。",
      },
      {
        prompt: "OK！頭金は“前に金”。次は練習！",
        sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "頭金（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "相手玉(5一)。頭金はどこに打つ？",
        sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 2) }],
        hints: { arrows: [{ to: sq(5, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 2)] },
        explanation: "玉の頭（前）に金を打つのが頭金。",
      },
      {
        question: "相手玉(4一)。頭金は？",
        sfen: "position sfen 3k5/9/3P5/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(4, 2) }],
        hints: { arrows: [{ to: sq(4, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 2)] },
        explanation: "玉の真下（前）に金を置く。",
      },
      {
        question: "相手玉(6一)。頭金は？",
        sfen: "position sfen 5k3/9/5P3/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(6, 2) }],
        hints: { arrows: [{ to: sq(6, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(6, 2)] },
        explanation: "頭＝前。6二に金。",
      },
      {
        question: "相手玉(5二)。頭金は？",
        sfen: "position sfen 9/4k4/4P4/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 3) }],
        hints: { arrows: [{ to: sq(5, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 3)] },
        explanation: "玉が1段下がっても、頭はその前（5三）。",
      },
      {
        question: "相手玉(4二)。頭金は？",
        sfen: "position sfen 9/3k5/3P5/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(4, 3) }],
        hints: { arrows: [{ to: sq(4, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 3)] },
        explanation: "玉の前に金を置く。形で覚える。",
      },
      {
        question: "相手玉(6二)。頭金は？",
        sfen: "position sfen 9/5k3/5P3/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(6, 3) }],
        hints: { arrows: [{ to: sq(6, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(6, 3)] },
        explanation: "頭＝前。6三に金。",
      },
      {
        question: "頭金の場所確認：5一の玉なら、金はどこ？",
        sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 2) }],
        hints: { arrows: [{ to: sq(5, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 2)] },
        explanation: "玉の前に金。これだけは体に入れよう。",
      },
      {
        question: "歩で支える形：5三の歩を5二へ進めるなら？",
        sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 3), to: sq(5, 2) }],
        hints: { arrows: [{ from: sq(5, 3), to: sq(5, 2), kind: "move" }], highlights: [sq(5, 2)] },
        explanation: "頭金は“支え”があるとより強い。支える形も覚えよう。",
      },
    ],
  },
  {
    type: "review",
    title: "頭金（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


