import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 尻金 Lv1
 * - 玉の“後ろ（尻）”に金を打って、退路を断つ/王手をかける
 * - 盤面・文章は自作
 */
export const GOLD_SHIRIKIN_L1: LessonStep[] = [
  {
    type: "guided",
    title: "尻金（Lv1）: ガイド",
    // 相手玉(5三)。玉の“尻”(5二)に金を打つ（玉の退路＝上側をふさぐ感覚）。
    sfen: "position sfen 9/9/4k4/9/9/9/9/9/4K4 b G 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "玉の尻を押さえよう。5二に金を打って王手！",
        arrows: [{ to: sq(5, 2), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 2), sq(5, 3)],
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 2) }],
        after: "auto",
        wrongHint: "尻金は、玉の“後ろ側”に金を打つイメージ。5二に金。",
      },
      {
        prompt: "（後ろを押さえると、退路が減る）",
        sfen: "position sfen 9/4G4/4k4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 260,
      },
      {
        prompt: "次は包もう。金を一歩動かしてみよう（5二→4二）。",
        sfen: "position sfen 9/4G4/4k4/9/9/9/9/9/4K4 b - 1",
        arrows: [{ from: sq(5, 2), to: sq(4, 2), kind: "move" }],
        highlights: [sq(4, 2)],
        expectedMoves: [{ kind: "move", from: sq(5, 2), to: sq(4, 2) }],
        after: "auto",
        wrongHint: "尻を押さえた金は、周囲を埋める動きにもつながる。",
      },
      {
        prompt: "OK！尻金は“後ろに金”。次は練習！",
        sfen: "position sfen 9/3G5/4k4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "尻金（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "相手玉(5三)。尻金はどこに打つ？",
        sfen: "position sfen 9/9/4k4/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 2) }],
        hints: { arrows: [{ to: sq(5, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 2)] },
        explanation: "玉の後ろ側（退路側）に金を置いて、逃げ道を減らす。",
      },
      {
        question: "相手玉(4三)。尻金は？",
        sfen: "position sfen 9/9/3k5/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(4, 2) }],
        hints: { arrows: [{ to: sq(4, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 2)] },
        explanation: "4二が“尻”の位置。",
      },
      {
        question: "相手玉(6三)。尻金は？",
        sfen: "position sfen 9/9/5k3/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(6, 2) }],
        hints: { arrows: [{ to: sq(6, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(6, 2)] },
        explanation: "6二に金で、後ろを押さえる。",
      },
      {
        question: "相手玉(5四)。尻金は？",
        sfen: "position sfen 9/9/9/4k4/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 3) }],
        hints: { arrows: [{ to: sq(5, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 3)] },
        explanation: "玉が1段下がっても、尻はその1つ上。",
      },
      {
        question: "相手玉(3三)。尻金は？",
        sfen: "position sfen 9/9/2k6/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(3, 2) }],
        hints: { arrows: [{ to: sq(3, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 2)] },
        explanation: "3二に金。後ろを押さえる形を作る。",
      },
      {
        question: "相手玉(7三)。尻金は？",
        sfen: "position sfen 9/9/6k2/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(7, 2) }],
        hints: { arrows: [{ to: sq(7, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 2)] },
        explanation: "7二に金。端でも同じ考え方。",
      },
      {
        question: "尻金を打った後。金を一歩動かすなら？（5二→4二）",
        sfen: "position sfen 9/4G4/4k4/9/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 2), to: sq(4, 2) }],
        hints: { arrows: [{ from: sq(5, 2), to: sq(4, 2), kind: "move" }], highlights: [sq(4, 2)] },
        explanation: "尻を押さえた金は、周囲を埋める動きにもつながる。",
      },
      {
        question: "確認：相手玉(5三)なら尻金は？",
        sfen: "position sfen 9/9/4k4/9/9/9/9/9/4K4 b G 1",
        expectedMoves: [{ kind: "drop", piece: "G", to: sq(5, 2) }],
        hints: { arrows: [{ to: sq(5, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 2)] },
        explanation: "玉の後ろに金。これが尻金。",
      },
    ],
  },
  {
    type: "review",
    title: "尻金（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


