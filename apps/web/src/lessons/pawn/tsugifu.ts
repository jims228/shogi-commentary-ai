import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 継ぎ歩（V2）
 * - Guided: 矢印誘導つきで一連の流れを体験
 * - Practice: 類題を数問（ヒントで矢印）
 * - Review: このレッスン内で間違えた問題を再出題（MVP）
 */
export const PAWN_TSUGIFU_LESSON_V2: LessonStep[] = [
  {
    type: "guided",
    title: "継ぎ歩：まずはガイドで体験",
    sfen: "position sfen 7kl/6gb1/7pp/5pp2/7P1/9/9/7R1/4K4 b P 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは突き捨て。2五の歩を2四へ。",
        sfen: "position sfen 7kl/6gb1/7pp/5pp2/7P1/9/9/7R1/4K4 b P 1",
        arrows: [{ from: sq(2, 5), to: sq(2, 4), kind: "move" }],
        highlights: [sq(2, 4)],
        expectedMoves: [{ kind: "move", from: sq(2, 5), to: sq(2, 4) }],
        after: "auto",
        wrongHint: "まずは 2五→2四 を指してみよう。",
      },
      {
        prompt: "（相手の応手）",
        sfen: "position sfen 7kl/6gb1/7pp/5ppP1/9/9/9/7R1/4K4 w P 1",
        expectedMoves: [],
        autoAdvanceMs: 180,
      },
      {
        prompt: "継ぎ歩！持ち歩を2五に打ってね。",
        sfen: "position sfen 7kl/6gb1/8p/5ppp1/9/9/9/7R1/4K4 b 2P 1",
        arrows: [{ to: sq(2, 5), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(2, 5)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(2, 5) }],
        after: "auto",
        wrongHint: "ここは 2五 に歩を打つのが継ぎ歩。",
      },
      {
        prompt: "（相手の応手）",
        sfen: "position sfen 7kl/6gb1/8p/5ppp1/7P1/9/9/7R1/4K4 w P 1",
        expectedMoves: [],
        autoAdvanceMs: 180,
      },
      {
        prompt: "最後にもう一枚。2四に歩を打って圧力を継続！",
        sfen: "position sfen 7kl/6gb1/8p/5pp2/7p1/9/9/7R1/4K4 b Pp 1",
        arrows: [{ to: sq(2, 4), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(2, 4)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(2, 4) }],
        after: "auto",
        wrongHint: "“取らせた歩の地点”に持ち歩を打つのが継ぎ歩。",
      },
      {
        prompt: "これで継ぎ歩の形ができたね。次は練習問題！",
        sfen: "position sfen 7kl/6gb1/8p/5ppP1/7p1/9/9/7R1/4K4 w p 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "練習：継ぎ歩を当てよう",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "この局面。継ぎ歩はどこに打つ？",
        sfen: "position sfen 7kl/6gb1/8p/5ppp1/9/9/9/7R1/4K4 b 2P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(2, 5) }],
        hints: {
          arrows: [{ to: sq(2, 5), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(2, 5)],
        },
        explanation: "歩を取らせたあと、同じ筋に持ち歩を“継いで”攻めを続ける手筋。",
      },
      {
        question: "さらにもう一枚。どこに歩を打って継ぐ？",
        sfen: "position sfen 7kl/6gb1/8p/5pp2/7p1/9/9/7R1/4K4 b Pp 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(2, 4) }],
        hints: {
          arrows: [{ to: sq(2, 4), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(2, 4)],
        },
        explanation: "ポイントは“取らせた地点”に持ち歩を打つこと。",
      },
      {
        question: "まずはこの一手から。突き捨ての歩は？",
        sfen: "position sfen 7kl/6gb1/7pp/5pp2/7P1/9/9/7R1/4K4 b P 1",
        expectedMoves: [{ kind: "move", from: sq(2, 5), to: sq(2, 4) }],
        hints: {
          arrows: [{ from: sq(2, 5), to: sq(2, 4), kind: "move" }],
          highlights: [sq(2, 4)],
        },
        explanation: "継ぎ歩は、まず歩交換（突き捨て）から始まることが多い。",
      },
    ],
  },
  {
    type: "review",
    title: "復習：間違えた問題をもう一度",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 3,
  },
];


