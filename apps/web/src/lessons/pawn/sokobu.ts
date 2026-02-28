import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 底歩 Lv1
 * - 玉の近く（自陣の奥）に歩を打って、飛車/香の直線攻撃を止める
 * - 盤面・文章は自作
 */
export const PAWN_SOKOBU_L1: LessonStep[] = [
  {
    type: "guided",
    title: "底歩（Lv1）: ガイド",
    // 相手飛車(5二)が5筋で王手。5八に歩を打ってブロックする（“底”で受けるイメージ）。
    sfen: "position sfen 4k4/4r4/9/9/9/9/9/9/4K4 b P 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "王手！飛車の筋を止めよう。5八に歩を打ってブロックしてね。",
        arrows: [{ to: sq(5, 8), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 8)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 8) }],
        after: "auto",
        wrongHint: "飛車の直線は“間に1枚置く”のが基本。5八に歩を打とう。",
      },
      {
        prompt: "（筋が止まった！）",
        sfen: "position sfen 4k4/4r4/9/9/9/9/9/4P4/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 260,
      },
      {
        prompt: "次は安全な場所へ。玉を1マス横に動かしてみよう（4九へ）。",
        // 玉が動けるように簡単な局面（相手の利きは簡略化）
        sfen: "position sfen 4k4/4r4/9/9/9/9/9/4P4/4K4 b - 1",
        arrows: [{ from: sq(5, 9), to: sq(4, 9), kind: "move" }],
        highlights: [sq(4, 9)],
        expectedMoves: [{ kind: "move", from: sq(5, 9), to: sq(4, 9) }],
        after: "auto",
        wrongHint: "底歩で受けたら、玉を逃がす/整える手も覚えよう。",
      },
      {
        prompt: "OK！底歩は“奥で筋を止める”。次は練習！",
        sfen: "position sfen 4k4/4r4/9/9/9/9/9/4P4/3K5 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "底歩（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "王手。飛車の筋を止める底歩は？（5筋）",
        sfen: "position sfen 4k4/4r4/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 8) }],
        hints: { arrows: [{ to: sq(5, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 8)] },
        explanation: "直線攻撃は、間に1枚入れて止める。",
      },
      {
        question: "場所替え：3筋で王手。底歩はどこ？",
        sfen: "position sfen 4k4/2r6/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 8) }],
        hints: { arrows: [{ to: sq(3, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 8)] },
        explanation: "王様の近くで、筋にフタをする歩。",
      },
      {
        question: "場所替え：7筋で王手。底歩はどこ？",
        sfen: "position sfen 4k4/6r2/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 8) }],
        hints: { arrows: [{ to: sq(7, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 8)] },
        explanation: "“奥で受ける”形を筋違いでも再現。",
      },
      {
        question: "香の筋も同じ。5筋で香が通っている。底歩は？",
        sfen: "position sfen 4k4/4l4/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 8) }],
        hints: { arrows: [{ to: sq(5, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 8)] },
        explanation: "飛車でも香でも“筋は間に置いて止める”。",
      },
      {
        question: "3筋で香が通っている。底歩は？",
        sfen: "position sfen 4k4/2l6/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 8) }],
        hints: { arrows: [{ to: sq(3, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 8)] },
        explanation: "王様の前に“受けの壁”を作るイメージ。",
      },
      {
        question: "底歩で受けた後、玉を横に動かすなら？（4九）",
        sfen: "position sfen 4k4/4r4/9/9/9/9/9/4P4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 9), to: sq(4, 9) }],
        hints: { arrows: [{ from: sq(5, 9), to: sq(4, 9), kind: "move" }], highlights: [sq(4, 9)] },
        explanation: "受けたら、玉を落ち着かせる手もセットで覚える。",
      },
      {
        question: "底歩で受ける場所は？（5八）",
        sfen: "position sfen 4k4/4r4/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 8) }],
        hints: { arrows: [{ to: sq(5, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 8)] },
        explanation: "“玉の前の筋”にフタをする。",
      },
      {
        question: "確認：7筋の底歩はどこ？（7八）",
        sfen: "position sfen 4k4/6r2/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 8) }],
        hints: { arrows: [{ to: sq(7, 8), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 8)] },
        explanation: "奥で受ける“底歩”。",
      },
    ],
  },
  {
    type: "review",
    title: "底歩（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


