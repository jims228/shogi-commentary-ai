import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 叩きの歩（焦点の歩も含む） Lv1
 * - まず歩を“叩いて”相手の駒を前に引きずり出し、狙いを通す入口を作る
 * - 盤面・文章は自作
 */
export const PAWN_TATAKI_L1: LessonStep[] = [
  {
    type: "guided",
    title: "叩きの歩（Lv1）: ガイド",
    // 相手銀(5四)を前に引き出すため、5五に歩を叩く。その後、飛車で取り返す。
    sfen: "position sfen 4k4/9/9/4s4/9/9/9/4R4/4K4 b P 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは“叩き”。5五に歩を打って、相手の銀を前に出させよう。",
        arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 5)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        after: "auto",
        wrongHint: "5五に歩を打つのが“叩き”の第一歩。",
      },
      {
        prompt: "（相手は歩を取ることが多い）",
        // 相手銀が5五に出る（歩を取った形）。手番は先手に戻す。
        sfen: "position sfen 4k4/9/9/9/4s4/9/9/4R4/4K4 b p 1",
        expectedMoves: [],
        autoAdvanceMs: 220,
      },
      {
        prompt: "出てきた銀を、飛車で取り返そう。5二の飛車で5五へ。",
        sfen: "position sfen 4k4/9/9/9/4s4/9/9/4R4/4K4 b - 1",
        arrows: [{ from: sq(5, 8), to: sq(5, 5), kind: "move" }],
        highlights: [sq(5, 5)],
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(5, 5) }],
        after: "auto",
        wrongHint: "5二の飛車を5五へ。叩いて出た駒を回収しよう。",
      },
      {
        prompt: "OK！叩きの歩は“出させて、狙う”。次は練習！",
        sfen: "position sfen 4k4/9/9/9/4R4/9/9/9/4K4 w p 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "叩きの歩（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "この局面。まず叩きの歩はどこ？",
        sfen: "position sfen 4k4/9/9/4s4/9/9/9/4R4/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        hints: { arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 5)] },
        explanation: "相手駒の前に歩を打ち、反応を強制するのが“叩き”。",
      },
      {
        question: "銀が出てきた。飛車で取り返すなら？",
        sfen: "position sfen 4k4/9/9/9/4s4/9/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(5, 5) }],
        hints: { arrows: [{ from: sq(5, 8), to: sq(5, 5), kind: "move" }], highlights: [sq(5, 5)] },
        explanation: "叩いて出た駒は、狙いの駒で回収するのが基本。",
      },
      {
        question: "場所を変えて。相手金(3四)に叩く歩は？",
        sfen: "position sfen 4k4/9/9/2g6/9/9/9/2R6/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 5) }],
        hints: { arrows: [{ to: sq(3, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 5)] },
        explanation: "相手駒の“前”に歩を叩く発想を覚えよう。",
      },
      {
        question: "場所を変えて。相手銀(7四)に叩く歩は？",
        sfen: "position sfen 4k4/9/9/6s2/9/9/9/6R2/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 5) }],
        hints: { arrows: [{ to: sq(7, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 5)] },
        explanation: "叩きは“1つ前に打つ”。形で覚える。",
      },
      {
        question: "相手の角(2四)を前に出させたい。叩く歩は？",
        sfen: "position sfen 4k4/9/9/1b7/9/9/9/4R4/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(2, 5) }],
        hints: { arrows: [{ to: sq(2, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(2, 5)] },
        explanation: "相手の大駒にも同じ。前に歩を叩いて反応を見る。",
      },
      {
        question: "焦点の歩：2つの駒(4四・6四)の“間(5五)”に歩を打つなら？",
        sfen: "position sfen 4k4/9/9/3g1g3/9/9/9/4K4/9 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        hints: { arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 5)] },
        explanation: "2枚に関係するマスが“焦点”。そこに歩を打つと揉めやすい。",
      },
      {
        question: "焦点の歩：相手の駒が(3四・5四)。焦点(4五)に歩を打つなら？",
        sfen: "position sfen 4k4/9/9/2s1g4/9/9/9/4K4/9 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(4, 5) }],
        hints: { arrows: [{ to: sq(4, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 5)] },
        explanation: "“2枚が関わるマス”を見つける練習。",
      },
      {
        question: "最後。叩いて出た銀が5五にいる。取り返す一手は？",
        sfen: "position sfen 4k4/9/9/9/4s4/9/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(5, 5) }],
        hints: { arrows: [{ from: sq(5, 8), to: sq(5, 5), kind: "move" }], highlights: [sq(5, 5)] },
        explanation: "叩き→相手が出る→回収、を形で覚えよう。",
      },
    ],
  },
  {
    type: "review",
    title: "叩きの歩（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


