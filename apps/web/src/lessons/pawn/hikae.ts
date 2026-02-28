import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 控えの歩 Lv1
 * - いきなり突かずに、1つ後ろに歩を置いて“土台”を作る
 * - 盤面・文章は自作
 */
export const PAWN_HIKAE_L1: LessonStep[] = [
  {
    type: "guided",
    title: "控えの歩（Lv1）: ガイド",
    // 5筋を攻めたいが、まず5六に歩を“控えて”置く（次に5五へ進める土台）。
    sfen: "position sfen 4k4/9/9/9/9/9/9/4R4/4K4 b P 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "攻めたい筋に“控え”を作ろう。5六に歩を打ってね。",
        arrows: [{ to: sq(5, 6), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 6)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 6) }],
        after: "auto",
        wrongHint: "控えの歩は、狙いの1つ後ろに歩を置く手筋だよ。",
      },
      {
        prompt: "（準備完了。次に突ける形）",
        sfen: "position sfen 4k4/9/9/9/9/4P4/9/4R4/4K4 b - 1",
        expectedMoves: [],
        autoAdvanceMs: 220,
      },
      {
        prompt: "次は土台から前へ。5六の歩を5五へ進めよう。",
        sfen: "position sfen 4k4/9/9/9/9/4P4/9/4R4/4K4 b - 1",
        arrows: [{ from: sq(5, 6), to: sq(5, 5), kind: "move" }],
        highlights: [sq(5, 5)],
        expectedMoves: [{ kind: "move", from: sq(5, 6), to: sq(5, 5) }],
        after: "auto",
        wrongHint: "5六→5五。控えの歩は“次に突ける土台”になる。",
      },
      {
        prompt: "OK！控えの歩は“準備してから突く”。次は練習！",
        sfen: "position sfen 4k4/9/9/9/4P4/9/9/4R4/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "控えの歩（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "5筋を攻めたい。まず控えの歩を置くなら？",
        sfen: "position sfen 4k4/9/9/9/9/9/9/4R4/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 6) }],
        hints: { arrows: [{ to: sq(5, 6), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 6)] },
        explanation: "狙いの1つ後ろに歩を置いて、次の突きを安定させる。",
      },
      {
        question: "控えの歩ができた。次に突くなら？",
        sfen: "position sfen 4k4/9/9/9/9/4P4/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 6), to: sq(5, 5) }],
        hints: { arrows: [{ from: sq(5, 6), to: sq(5, 5), kind: "move" }], highlights: [sq(5, 5)] },
        explanation: "控えの歩は“次に突ける形”を作るための一手。",
      },
      {
        question: "3筋を攻めたい。控えの歩は？",
        sfen: "position sfen 4k4/9/9/9/9/9/9/2R6/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 6) }],
        hints: { arrows: [{ to: sq(3, 6), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 6)] },
        explanation: "“狙いの後ろ”に歩を置く感覚を筋違いでも再現。",
      },
      {
        question: "控えの歩（3六）から次の一歩は？",
        sfen: "position sfen 4k4/9/9/9/9/2P6/9/2R6/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(3, 6), to: sq(3, 5) }],
        hints: { arrows: [{ from: sq(3, 6), to: sq(3, 5), kind: "move" }], highlights: [sq(3, 5)] },
        explanation: "土台から前へ。準備してから突く。",
      },
      {
        question: "7筋を攻めたい。控えの歩は？",
        sfen: "position sfen 4k4/9/9/9/9/9/9/6R2/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 6) }],
        hints: { arrows: [{ to: sq(7, 6), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 6)] },
        explanation: "狙う筋に、まず控えを作る。",
      },
      {
        question: "控えの歩（7六）から前へ出るなら？",
        sfen: "position sfen 4k4/9/9/9/9/6P2/9/6R2/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(7, 6), to: sq(7, 5) }],
        hints: { arrows: [{ from: sq(7, 6), to: sq(7, 5), kind: "move" }], highlights: [sq(7, 5)] },
        explanation: "控え→前進、の2手で形を覚える。",
      },
      {
        question: "相手の歩が前にいるときも、まず控えるなら？（5筋）",
        sfen: "position sfen 4k4/9/9/4p4/9/9/9/4R4/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 6) }],
        hints: { arrows: [{ to: sq(5, 6), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 6)] },
        explanation: "いきなりぶつけず、土台を作ってから戦う発想。",
      },
      {
        question: "控えの歩がある状態で、次にぶつける一歩は？（5六→5五）",
        sfen: "position sfen 4k4/9/9/4p4/9/4P4/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 6), to: sq(5, 5) }],
        hints: { arrows: [{ from: sq(5, 6), to: sq(5, 5), kind: "move" }], highlights: [sq(5, 5)] },
        explanation: "控えがあると、ぶつけた後の展開が作りやすい。",
      },
    ],
  },
  {
    type: "review",
    title: "控えの歩（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


