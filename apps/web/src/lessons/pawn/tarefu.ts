import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 垂れ歩 Lv1（入門）
 * - “相手駒の1つ手前に歩を打って”、次に突いて成る圧力を作る
 * - 盤面・文章は自作（外部記事の転載はしない）
 */
export const PAWN_TAREFU_L1: LessonStep[] = [
  {
    type: "guided",
    title: "垂れ歩（Lv1）: ガイド",
    // 5三に相手の金。先手は持ち駒に歩1枚（5四に垂れ歩を打つのが狙い）
    sfen: "position sfen 4k4/9/4g4/9/9/9/9/9/4K4 b P 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "相手の駒（5三）の“1つ手前”に歩を打とう。5四に歩を打ってね。",
        arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 4)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 4) }],
        after: "auto",
        wrongHint: "垂れ歩は、相手駒の1つ手前に歩を打つ手筋だよ。",
      },
      {
        prompt: "（次の狙い：突いて成る）",
        // 打った直後のスナップショット
        sfen: "position sfen 4k4/9/4g4/4P4/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 220,
      },
      {
        prompt: "次は“突いて成る”。5四の歩で5三を取って、成ってみよう。",
        // 盤上に歩がある状態（手番は先手）
        sfen: "position sfen 4k4/9/4g4/4P4/9/9/9/9/4K4 b - 1",
        arrows: [{ from: sq(5, 4), to: sq(5, 3), kind: "move" }],
        highlights: [sq(5, 3)],
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(5, 3), promote: true }],
        after: "auto",
        wrongHint: "5四の歩を5三へ。今回は“成る”も選んでね。",
      },
      {
        prompt: "ナイス！垂れ歩→突いて成る、が基本形。次は練習問題！",
        // 参考スナップショット（成っていなくてもOKだが、説明上は成後を置く）
        sfen: "position sfen 4k4/9/4+P4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "垂れ歩（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "この局面。垂れ歩はどこに打つ？（相手の金の1つ手前）",
        sfen: "position sfen 4k4/9/4g4/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 4) }],
        hints: { arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 4)] },
        explanation: "相手駒の1つ手前に歩を打って、次に“突いて成る”圧力を作る。",
      },
      {
        question: "相手の金が3三にいる。垂れ歩は？",
        sfen: "position sfen 4k4/9/2g6/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 4) }],
        hints: { arrows: [{ to: sq(3, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 4)] },
        explanation: "“1つ手前”なので、3四に歩を垂らす。",
      },
      {
        question: "相手の銀が7三にいる。垂れ歩は？",
        sfen: "position sfen 4k4/9/6s2/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 4) }],
        hints: { arrows: [{ to: sq(7, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 4)] },
        explanation: "垂れ歩は“相手の駒の前”に歩を置く発想。",
      },
      {
        question: "相手の角が2二にいる。垂れ歩は？",
        sfen: "position sfen 4k4/1b7/9/9/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(2, 3) }],
        hints: { arrows: [{ to: sq(2, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(2, 3)] },
        explanation: "2二の1つ手前＝2三。",
      },
      {
        question: "相手の飛車が8四にいる。垂れ歩は？",
        sfen: "position sfen 4k4/9/9/7r1/9/9/9/9/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(8, 5) }],
        hints: { arrows: [{ to: sq(8, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(8, 5)] },
        explanation: "8四の1つ手前＝8五。",
      },
      {
        question: "垂れ歩を打った後。次の狙いは“突いて成る”。5四の歩でどこへ？（成る）",
        sfen: "position sfen 4k4/9/4g4/4P4/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(5, 3), promote: true }],
        hints: { arrows: [{ from: sq(5, 4), to: sq(5, 3), kind: "move" }], highlights: [sq(5, 3)] },
        explanation: "垂れ歩の狙いは“突いて成る”の圧力。今回は相手駒も取れて一石二鳥。",
      },
    ],
  },
  {
    type: "review",
    title: "垂れ歩（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


