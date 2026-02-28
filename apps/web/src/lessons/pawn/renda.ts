import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 歩の連打 Lv1
 * - 取られても、同じ地点にもう一枚“連打”して圧力を続ける
 * - 盤面・文章は自作
 */
export const PAWN_RENDA_L1: LessonStep[] = [
  {
    type: "guided",
    title: "歩の連打（Lv1）: ガイド",
    // 相手歩(5四)。先手は歩2枚持ち。5五に歩を打って取らせ、もう一度5五に打つ。
    sfen: "position sfen 4k4/9/9/4p4/9/9/9/4R4/4K4 b 2P 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは1枚目。5五に歩を打ってね。",
        arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 5)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        after: "auto",
        wrongHint: "まずは 5五 に歩を打って形を作ろう。",
      },
      {
        prompt: "（相手が取る）",
        // 相手歩が5五で歩を取った形。先手番に戻す。手駒は先手P1・後手p1。
        sfen: "position sfen 4k4/9/9/9/4p4/9/9/4R4/4K4 b Pp 1",
        expectedMoves: [],
        autoAdvanceMs: 220,
      },
      {
        prompt: "ここが“連打”。もう一枚、同じ5五に歩を打って圧力を継続！",
        sfen: "position sfen 4k4/9/9/9/4p4/9/9/4R4/4K4 b P 1",
        arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 5)],
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        after: "auto",
        wrongHint: "取られても同じ地点に“もう一枚”。それが歩の連打。",
      },
      {
        prompt: "OK！歩は軽い。連打で相手の手を縛ろう。次は練習！",
        sfen: "position sfen 4k4/9/9/9/4P4/9/9/4R4/4K4 w p 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "歩の連打（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "この局面。まず1枚目の歩はどこに打つ？",
        sfen: "position sfen 4k4/9/9/4p4/9/9/9/4R4/4K4 b 2P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        hints: { arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 5)] },
        explanation: "まずは歩を叩いて、相手の反応を引き出す。",
      },
      {
        question: "相手が取った。ここから“連打”するなら？",
        sfen: "position sfen 4k4/9/9/9/4p4/9/9/4R4/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        hints: { arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 5)] },
        explanation: "取られた地点にもう一枚。これが“連打”。",
      },
      {
        question: "場所替え：相手歩が3四。歩2枚で連打の1枚目は？",
        sfen: "position sfen 4k4/9/9/2p6/9/9/9/2R6/4K4 b 2P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 5) }],
        hints: { arrows: [{ to: sq(3, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 5)] },
        explanation: "相手歩の前に打って、まずは取らせる。",
      },
      {
        question: "場所替え：相手が取った後。連打するなら？",
        sfen: "position sfen 4k4/9/9/9/2p6/9/9/2R6/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(3, 5) }],
        hints: { arrows: [{ to: sq(3, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 5)] },
        explanation: "取られた地点に、同じ筋へもう一枚。",
      },
      {
        question: "場所替え：相手歩が7四。1枚目は？",
        sfen: "position sfen 4k4/9/9/6p2/9/9/9/6R2/4K4 b 2P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 5) }],
        hints: { arrows: [{ to: sq(7, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 5)] },
        explanation: "同じ形を別の筋でも再現できるようにしよう。",
      },
      {
        question: "相手歩が7四で取った後。連打するなら？",
        sfen: "position sfen 4k4/9/9/9/6p2/9/9/6R2/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(7, 5) }],
        hints: { arrows: [{ to: sq(7, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 5)] },
        explanation: "“取らせた地点にもう一枚”。形で覚える。",
      },
      {
        question: "応用：相手歩が5四。連打した歩を飛車で取るなら？",
        sfen: "position sfen 4k4/9/9/9/4p4/9/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(5, 5) }],
        hints: { arrows: [{ from: sq(5, 8), to: sq(5, 5), kind: "move" }], highlights: [sq(5, 5)] },
        explanation: "連打で前に出した駒を、後ろの大駒で回収することも多い。",
      },
      {
        question: "確認：連打の“2枚目”を打つ場所はどこ？",
        sfen: "position sfen 4k4/9/9/9/4p4/9/9/4R4/4K4 b P 1",
        expectedMoves: [{ kind: "drop", piece: "P", to: sq(5, 5) }],
        hints: { arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 5)] },
        explanation: "取られた地点（同じマス）にもう一枚。",
      },
    ],
  },
  {
    type: "review",
    title: "歩の連打（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];


