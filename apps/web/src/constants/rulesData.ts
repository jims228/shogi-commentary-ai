export type TrainingStep = {
  step: number;
  title: string;
  description: string;
  sfen: string;
  checkMove: (move: { 
    from?: { x: number, y: number }; 
    to: { x: number, y: number }; 
    piece: string; 
    drop?: boolean 
  }) => boolean;
  /** 任意: 正解にはしないが、解説演出だけ発火させる手 */
  demoMoveCheck?: (move: {
    from?: { x: number, y: number };
    to: { x: number; y: number };
    piece: string;
    drop?: boolean;
  }) => boolean;
  successMessage: string;
  // 既存：マスを光らせる
  hintSquares?: { file: number; rank: number }[];
  // 追加：盤上マスに星マーカーを表示
  hintStars?: { file: number; rank: number }[];

  // ★追加：成功しても自動で次のStepに進めない（false に設定すると止める）
  advanceOnSuccess?: boolean;

  // ★追加：矢印を表示する（盤上オーバーレイ用）
  hintArrows?: {
    from?: { file: number; rank: number };
    to: { file: number; rank: number };
    kind?: "move" | "drop";
    dir?: "up" | "down" | "left" | "right" | "hand";
    // when dir is "hand", specify which side the hand belongs to
    hand?: "sente" | "gote";
  }[];

  // ★追加：Step 内で自動的に進行するスクリプト（フェーズ）。
  // 各フェーズは独立した表示用 SFEN と正解判定を持ちます。
  scriptPhases?: {
    sfen: string;
    delayMs?: number;
    hintSquares?: { file: number; rank: number }[];
    hintStars?: { file: number; rank: number }[];
    hintArrows?: {
      from?: { file: number; rank: number };
      to: { file: number; rank: number };
      kind?: "move" | "drop";
      dir?: "up" | "down" | "left" | "right" | "hand";
      hand?: "sente" | "gote";
    }[];
    checkMove: TrainingStep["checkMove"];
    // optional per-phase success message
    successMessage?: string;
  }[];

  // ★追加：正解時に駒へモーションを付与（将来拡張しやすい汎用設定）
  onCorrectPieceMotions?: {
    target: {
      /** 将棋座標（1..9） */
      file: number;
      /** 将棋座標（1..9） */
      rank: number;
      /** owner 省略時はどちらでも可 */
      owner?: "sente" | "gote";
      /** exact piece code (optional) */
      piece?: string;
      /** normalized base piece, e.g. K/G/P (optional) */
      pieceBase?: "P" | "L" | "N" | "S" | "G" | "B" | "R" | "K";
    };
    motion: {
      type: "shake-x";
      amplitudePx?: number;
      durationMs?: number;
      delayMs?: number;
      repeat?: number | "infinite";
    };
  }[];

  // ★追加：正解後に段階的な解説（盤面更新/吹き出し文言更新）を行う
  // 将来の「駒を動かしながら解説」用の一般化データ
  postCorrectDemo?: {
    /** このフレーム適用までの待機時間(ms) */
    delayMs?: number;
    /** 任意: この時点で盤面を差し替えるSFEN */
    sfen?: string;
    /** 任意: 吹き出し文言（成功メッセージ領域）を上書き */
    comment?: string;
    /** 任意: このフレーム適用時に正解状態へ遷移する */
    markCorrect?: boolean;
  }[];

  // ★追加：着手後に選択問題へ進むステップ
  // checkMove が true になったら question を表示し、correct=true の選択で正解扱い。
  choiceQuestion?: {
    prompt: string;
    options: {
      label: string;
      correct: boolean;
    }[];
  };
};

// 安全なダミー SFEN（TODO を埋めるときの一時置換用）
const SAFE_SFEN = "position sfen 4k4/9/9/9/9/9/9/9/4K4 b - 1";

// Step2: 取り返し後の盤面（飛車が2四にいて、手駒が歩2枚）
const TSUGIFU_STEP2_SFEN =
  "position sfen 7kl/6gb1/8p/5ppR1/9/9/9/9/4K4 b 2P 1";

// 使いやすいヘルパー
type Square = { file: number; rank: number };
const sq = (file: number, rank: number): Square => ({ file, rank });

const pieceStr = (m: any) => (typeof m?.piece === "string" ? m.piece : "");

const isDropPiece = (m: any, pieceUpper: string) => {
  const p = pieceStr(m).toUpperCase();
  const isDrop = m?.drop === true || m?.from == null;
  return isDrop && p === pieceUpper;
};

// `getXY` / `isMasu` helpers are defined later in this file to handle
// multiple coordinate conventions; dropTo will use those definitions.

const dropTo = (pieceUpper: string, target: Square) => (m: any) => isDropPiece(m, pieceUpper) && isMasu(m.to, target.file, target.rank);

// 1. 歩
export const PAWN_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "歩兵（ふひょう）の動き",
    description: "「歩」は前に1マスだけ進めます。目の前の歩を1つ進めてみましょう。（ドラッグ＆ドロップで操作）",
    sfen: "9/9/9/9/9/9/2P6/9/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.from.x === 2 && move.from.y === 6 && move.to.x === 2 && move.to.y === 5;
    },
    successMessage: "素晴らしい！歩は一歩ずつ着実に進みます。"
  },
  {
    step: 2,
    title: "相手の駒を取る",
    description: "歩は進む先に相手の駒があれば、取ることができます。目の前の「と金」を取ってみましょう。",
    sfen: "9/9/9/9/9/2+p6/2P6/9/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.from.x === 2 && move.from.y === 6 && move.to.x === 2 && move.to.y === 5;
    },
    successMessage: "ナイス！相手の駒を取ると、自分の「持ち駒」になります。"
    ,
    // このステップは成功しても自動で次に進まない
    advanceOnSuccess: false
  }
];

// 2. 香車
export const LANCE_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "香車（きょうしゃ）の動き",
    description: "「香車」は前にどこまでも進めますが、バックはできません。別名「槍（やり）」。一気に敵陣まで進んでみましょう！",
    sfen: "position sfen 9/9/9/9/9/9/9/1L7/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const isForward = move.from.x === 1 && move.from.y === 7 && move.to.x === 1 && move.to.y < 7;
      return isForward;
    },
    successMessage: "ナイス！香車は障害物がない限り、どこまでも直進できます。"
  },
  {
    step: 2,
    title: "香車で取る",
    description: "前にある敵の駒を取ってみましょう。途中に他の駒があると飛び越えられないので注意です。",
    sfen: "position sfen 9/9/1p7/9/9/9/9/1L7/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.from.x === 1 && move.from.y === 7 && move.to.x === 1 && move.to.y === 2;
    },
    successMessage: "お見事！遠くの駒も一瞬で取れるのが香車の強みです。"
  }
];

// 3. 桂馬
export const KNIGHT_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "桂馬（けいま）の動き",
    description: "桂馬は特殊な動きをします。前に2つ、横に1つ、「Yの字」にジャンプします。目の前の歩を飛び越えて進んでみましょう！",
    sfen: "position sfen 9/9/9/9/9/9/9/1P7/1N7 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = move.from.y - move.to.y;
      const dx = Math.abs(move.from.x - move.to.x);
      return dy === 2 && dx === 1;
    },
    successMessage: "素晴らしい！桂馬だけが他の駒を飛び越えることができます。"
  },
  {
    step: 2,
    title: "桂馬の両取り",
    description: "桂馬は同時に2つの場所を狙えます。うまく跳ねて、相手の「金」を取ってみましょう。",
    sfen: "position sfen 9/9/9/9/9/9/g1g6/9/1N7 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = move.from.y - move.to.y;
      const dx = Math.abs(move.from.x - move.to.x);
      return dy === 2 && dx === 1;
    },
    successMessage: "ナイス！「ふんどしの桂」と呼ばれる強力な手筋です。"
  }
];

// 4. 銀
export const SILVER_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "銀（ぎん）の動き",
    description: "銀は「前」と「斜め後ろ」に進めます（横と後ろには行けません）。千鳥足（ちどりあし）のように斜めに進んでみましょう。",
    sfen: "position sfen 9/9/9/9/9/9/4S4/9/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = move.from.y - move.to.y;
      const dx = Math.abs(move.from.x - move.to.x);
      const isForward = dy === 1 && dx === 0;
      const isDiagonalFront = dy === 1 && dx === 1;
      const isDiagonalBack = dy === -1 && dx === 1;
      return isForward || isDiagonalFront || isDiagonalBack;
    },
    successMessage: "その通り！銀は攻めにも守りにも使われる万能選手です。"
  },
  {
    step: 2,
    title: "銀で下がる",
    description: "銀は「斜め後ろ」に下がれるのが特徴です。相手の歩が前から来ました。斜め後ろに逃げてください！",
    sfen: "position sfen 9/9/9/9/4p4/4S4/9/9/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = move.from.y - move.to.y;
      const dx = Math.abs(move.from.x - move.to.x);
      return dy === -1 && dx === 1;
    },
    successMessage: "素晴らしい。引くことも重要な戦術です（銀は「千鳥に使う」と言います）。"
  }
];

// 5. 金
export const GOLD_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "金（きん）の動き",
    description: "金は「斜め後ろ」以外、すべての方向に1マス進めます。守りの要（かなめ）となる駒です。前か横に進んでみましょう。",
    sfen: "position sfen 9/9/9/9/9/9/9/4G4/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = move.from.y - move.to.y;
      const dx = Math.abs(move.from.x - move.to.x);
      const isDiagonalBack = dy === -1 && dx === 1;
      const isOneStep = Math.abs(dy) <= 1 && dx <= 1 && !(dy === 0 && dx === 0);
      return isOneStep && !isDiagonalBack;
    },
    successMessage: "その通り！金は王様を守るガードマンとして優秀です。"
  },
  {
    step: 2,
    title: "頭金（あたまきん）",
    description: "王様は「頭（前）」が弱点です。持ち駒の金を、相手の玉の頭（5二）に打って詰ませてください！5三の歩が支えになっています。",
    sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/9 b G 1",
    checkMove: (move) => {
      return move.drop === true && move.to.x === 4 && move.to.y === 1;
    },
    successMessage: "お見事！これが必殺の「頭金」です。相手は金を取れません（取ると歩に取り返されるため）。"
  }
];

// 6. 角
export const BISHOP_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "角（かく）の動き",
    description: "角は斜めにどこまでも進めます。一気に盤面の反対側まで移動してみましょう。",
    sfen: "position sfen 9/9/9/9/9/9/9/1B7/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = Math.abs(move.from.y - move.to.y);
      const dx = Math.abs(move.from.x - move.to.x);
      return dy === dx && dy >= 2;
    },
    successMessage: "ナイス！角道（かくみち）を通すと、遠くから敵を狙えます。"
  },
  {
    step: 2,
    title: "角が成る（馬）",
    description: "角が敵陣（奥の3段）に入ると「馬（うま）」にパワーアップ（成る）できます。敵陣に入って成ってください。",
    sfen: "position sfen 9/9/9/9/9/9/9/1B7/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.to.y <= 2;
    },
    successMessage: "進化完了！馬は「角の動き＋王様の動き（上下左右1マス）」ができる最強格の駒です。"
  }
];

// 7. 飛車
export const ROOK_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "飛車（ひしゃ）の動き",
    description: "飛車は縦横にどこまでも進めます。将棋で最も攻める力が強い駒です。一気に前に進んでみましょう。",
    sfen: "position sfen 9/9/9/9/9/9/9/1R7/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      const dy = move.from.y - move.to.y;
      const dx = Math.abs(move.from.x - move.to.x);
      return dx === 0 && dy >= 2;
    },
    successMessage: "素晴らしい！この突破力が飛車の武器です。"
  },
  {
    step: 2,
    title: "飛車が成る（龍）",
    description: "飛車も敵陣に入ると「龍（りゅう）」に成れます。敵陣に入って成ってみましょう！",
    sfen: "position sfen 9/9/9/9/9/9/9/1R7/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.to.y <= 2;
    },
    successMessage: "最強駒「龍」の誕生です！龍は「飛車の動き＋王様の動き（斜め1マス）」ができます。"
  }
];

// 8. 王将
export const KING_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "王将（玉）の動き",
    description: "王様（玉）は全方向に1マスずつ動けます。取られたら負けなので、逃げる練習をしましょう。上へ逃げてください。",
    sfen: "position sfen 9/9/9/9/9/9/9/4K4/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.to.y < 7;
    },
    successMessage: "OKです！常に安全な場所へ逃げることが重要です。"
  }
];

// 詰将棋 (1手詰)
export const TSUME_1_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "1手詰 第1問",
    description: "相手の玉は「2一」にいます。「2三」には相手の歩がいて、逃げ道をふさいでくれています。持ち駒の「金」を使って、一撃で詰ませてください！",
    // ★修正: 2三の歩を 'p' (小文字=相手の歩) に変更
    sfen: "position sfen 7k1/9/7P1/9/9/9/9/9/9 b G 1",
    checkMove: (move) => {
      // 2二(x:7, y:1)に金を打てば正解
      return move.drop === true && move.to.x === 7 && move.to.y === 1;
    },
    successMessage: "正解！頭金（あたまきん）です。2三の歩が邪魔で、玉は逃げられません。"
  },
  {
    step: 2,
    title: "1手詰 第2問（不成）",
    description: "銀を2一に移動させて王手をかけましょう。ただし、普通に「成る」と金と同じ動きになり、斜め後ろに下がれないため王手が消えてしまいます。「成らない」を選んでください！",
    sfen: "position sfen 8l/6GSk/7Np/9/9/9/9/9/9 b - 1",
    checkMove: (move) => {
      if (!move.from) return false;
      return move.from.x === 7 && move.from.y === 1 && move.to.x === 7 && move.to.y === 0 && move.piece === "S";
    },
    successMessage: "大正解！銀は成らないことで、斜め後ろへの効きを残せます。これを「銀の不成（ならず）」と言います。"
  },
  // ★修正: 第3問
  {
    step: 3,
    title: "1手詰 第3問（金の死角）",
    description: "相手の「金」の弱点を突く問題です。金は「斜め後ろ」には動けません。持ち駒の「銀」を、金に取られない場所に打って詰ませてください！",
    // ★修正: 不要な歩を消し、全体を1筋(右端)に寄せました
    // 1一玉(k), 1三金(g), 1四香(l)
    sfen: "position sfen 7k1/9/7G1/7L1/9/9/9/9/9 b S 1",
    checkMove: (move) => {
      // 2二(x:7, y:1)に銀を打てば正解
      // ※1筋に寄ったので、正解の場所も変わらず2二です
      return move.to.x === 7 && move.to.y === 1 && move.piece === "G";
    },
    successMessage: "お見事！金は斜め後ろ（2二）に下がれないため、この銀を取ることができません。"
  }
];


export const TSUME_2_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "1手詰・中盤 第1問",
    description: "持ち駒はありませんが、盤上の駒が協力して詰ませる形です。4四にいる「角」のライン（利き）が重要です。3三の「金」をどこに動かせば詰むでしょうか？",
    // 盤面: 2一玉(k), 1三銀(s), 3三金(G), 4四角(B)
    // 持ち駒なし (-)
    sfen: "position sfen 7k1/9/6G1S/5b3/9/9/9/9/9 b - 1",
    checkMove: (move) => {
      // 3三(x:6, y:2) にある金を 2二(x:7, y:1) に移動すれば正解
      // ※角の利きがあるので、玉は金を取れません
      if (!move.from) return false;
      return move.to.x === 7 && move.to.y === 1 && move.piece === "+S";
    },
    successMessage: "正解！角の紐（サポート）がついているので、相手は金を取ることができません。"
  },
  
  {
    step: 3,
    title: "1手詰・中盤 第3問",
    description: "盤上にある自分の「馬」を使って詰ませる問題です。邪魔な相手の駒を取り除きながら王手をかけてください！",
    sfen: "position sfen 7B+B/9/6pk1/7pp/9/9/9/9/9 b - 1",
    checkMove: (move) => {
      // 1一(x:8, y:0) の馬を 2一(x:7, y:0) に移動（角を取る）
      if (!move.from) return false;
      return (
        move.from.x === 8 && move.from.y === 0 && // 移動元: 1一
        move.to.x === 8 && move.to.y === 1 &&     // 移動先: 2一
        move.piece === "+B"                       // 駒: 馬
      );
    },
    successMessage: "正解！相手の角を取ることで、玉の逃げ道を完全に塞ぎました。"
  },

  {
    step: 3,
    title: "1手詰・中盤 第3問",
    description: "相手の守りは堅そうに見えますが、「角の頭（2二）」が弱点です！角は斜めにしか動けないため、目の前は守れていません。持ち駒の「金」を打って詰ませてください。",
    // 盤面:
    // 1段目: 7マス空き, 2一角(b), 1一玉(k) -> 7bk
    // 2段目: 9マス空き -> 9
    // 3段目: 7マス空き, 2三馬(+B・自), 1三桂(n) -> 7+Bn
    // 持ち駒: 金(G)
    sfen: "position sfen 6bk1/9/6+BN1/9/9/9/9/9/9 b G 1",
    checkMove: (move) => {
      // 2二(x:7, y:1) に金(G)を打てば正解
      return move.to.x === 8 && move.to.y === 0 && move.piece === "+N";
    },
    successMessage: "お見事！相手の角は頭（前）を守れないため、打った金を取れません。また、2三の馬が効いているので玉でも取れません。"
  }
];


// 詰将棋 (1手詰・実戦編)
export const TSUME_3_LESSONS: TrainingStep[] = [
  {
    step: 1,
    title: "1手詰・実戦編 第1問",
    description: "3三にいる「飛車」を使って詰ませる問題です。このまま動かすだけでは逃げられてしまいますが、「成る（パワーアップ）」とどうなるでしょうか？",
    // 盤面:
    // 1一香(l)
    // 1二玉(k)
    // 1三歩(p), 2三歩(p), 3三飛(R) ※飛車は自分の駒
    sfen: "position sfen 8l/8k/6RPp/9/9/9/9/9/9 b - 1",
    checkMove: (move) => {
      // 3三(x:6, y:2) の飛車を 3二(x:6, y:1) に「成って」移動
      if (!move.from) return false;
      return (
        move.from.x === 6 && move.from.y === 2 && // 移動元: 3三
        move.to.x === 6 && move.to.y === 1 &&     // 移動先: 3二
        move.piece === "+R"                       // 駒: 龍(成った飛車)
      );
    },
    successMessage: "正解！飛車が「龍」に成ることで斜めにも動けるようになり、玉の逃げ道（2一）を塞ぐことができました。"
  },

  {
    step: 2,
    title: "1手詰・実戦編 第2問",
    description: "持ち駒の「飛車」を使って詰ませる問題です。近づけて打つと逃げられてしまいます。大駒は「離して打つ」のがコツです！",
    // 盤面:
    // 1段目: 4マス空き, 5一龍(+R・自), 4マス空き -> 4+R4
    // 2段目: 2マス空き, 7二玉(k), 6マス空き -> 2k6
    // 3段目: 3マス空き, 6三歩(p), 3マス空き, 2三歩(p), 1マス空き -> 3p3p1
    // 持ち駒: 飛(R)
    sfen: "position sfen 4+R4/6k2/4p1pp1/9/9/9/9/9/9 b R 1",
    checkMove: (move) => {
      // 4二(x:5, y:1) に飛車(R)を打てば正解
      // ※3二(x:6, y:1)だと4三に逃げられるため不正解
      return move.drop === true && move.to.x === 5 && move.to.y === 1 && move.piece === "R";
    },
    successMessage: "正解！4二に打つことで玉の逃げ道をなくせます。"
  }
];

// --- Lesson 0: 歩の動きと成り（復習） ---
type XY = { x: number; y: number };

// あなたの page.tsx から渡ってくる move の形（ユーザー調査結果に合わせた最小型）
type TrainingMove = {
  from?: XY;                 // 打ちの場合 undefined
  to: XY;
  piece: string;             // 例: "P", "+P", "R", "+R"
  drop?: boolean;            // 打ちなら true
  promote?: boolean;         // 実装によってはあるかも（保険）
};

const isPawnMove = (m: TrainingMove) =>
  !!m.from && !m.drop && (m.piece === "P" || m.piece === "+P");

const isPromotedPawnMove = (m: TrainingMove) => {
  // 実装差異に強くする（piece が +P / promote フラグ / 文字列先頭+）
  const promotedByPiece = typeof m.piece === "string" && m.piece.startsWith("+");
  const promotedByFlag = (m as any).promote === true || (m as any).promoted === true;
  return !!m.from && !m.drop && (m.piece === "+P" || promotedByPiece || promotedByFlag);
};

const movedOneStepStraight = (m: TrainingMove) => {
  if (!m.from) return false;
  const dx = Math.abs(m.to.x - m.from.x);
  const dy = Math.abs(m.to.y - m.from.y);
  return dx === 0 && dy === 1;
};

export const PAWN_LESSON_0_STEPS: TrainingStep[] = [
  {
    step: 1,
    title: "歩は前に1マス",
    description:
      "歩は前に1マスだけ進めます。まずは歩を1マス進めてみよう。",
    // buildPositionFromUsi() が受けられるように「position sfen ...」形式にする（安全）
    sfen: "position sfen 4k4/9/9/9/9/9/4P4/9/4K4 b - 1",
    hintStars: [{ file: 5, rank: 6 }],
    checkMove: (move: TrainingMove) => isPawnMove(move) && movedOneStepStraight(move),
    successMessage: "OK！歩は前に1マスだね。",
  },

  {
    step: 2,
    title: "クイズ：歩を動かすのはどれ？",
    description:
      "盤上に歩と金がいます。『歩』を前に1マス動かしてください（歩以外を動かしたら不正解）。",
    sfen: "position sfen 4k4/9/9/9/9/9/4P4/4G4/4K4 b - 1",
    hintStars: [{ file: 5, rank: 6 }],
    checkMove: (move: TrainingMove) => {
      // 「歩を動かしたこと」だけを判定（座標依存しない）
      return isPawnMove(move) && movedOneStepStraight(move);
    },
    successMessage: "正解！いま動かしたのは歩だよ。",
  },

  {
    step: 3,
    title: "敵陣に入ると成れる（歩→と金）",
    description:
      "相手の陣地（相手側3段）に入ると『成る』ことができます。歩を進めて、成れるなら『成る』を選ぼう。",
    // 4段目に歩を置いて、1歩で敵陣（3段目）に入る位置
    sfen: "position sfen 4k4/9/9/4P4/9/9/9/9/4K4 b - 1",
    hintStars: [{ file: 5, rank: 6 }],
    checkMove: (move: TrainingMove) => isPromotedPawnMove(move),
    successMessage: "ナイス！歩が成って『と金』になったよ。",
  },

  {
    step: 4,
    title: "クイズ：成れるけど『成らない（不成）』もできる",
    description:
      "成れる場面でも『不成』を選べます。今回は、歩を敵陣へ進めるけど『成らない』を選んでみよう。",
    sfen: "position sfen 4k4/9/9/4P4/9/9/9/9/4K4 b - 1",
    hintStars: [{ file: 5, rank: 6 }],
    checkMove: (move: TrainingMove) => {
      // 成れても「成らない」＝結果が P のまま
      return isPawnMove(move) && !isPromotedPawnMove(move);
    },
    successMessage: "OK！成れる場面でも不成を選べるね。",
  },

  {
    step: 5,
    title: "クイズ：敵陣に入った後でも成れる",
    description:
      "敵陣に入った『次の手』でも成れます。歩をもう1マス進めて、今度は『成る』を選ぼう。",
    // すでに敵陣（3段目）に歩がいる状態から、もう1回進めて成る
    sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b - 1",
    hintStars: [{ file: 5, rank: 6 }],
    checkMove: (move: TrainingMove) => isPromotedPawnMove(move),
    successMessage: "正解！敵陣に入った後の手でも成れるよ。",
  },
];

// --- Lesson 1: 歩の役割（壁・道を開ける・捨て駒・と金） ---
// 既存の TrainingMove 系があればそれを使うが、安全のためローカル定義を入れる
type AnyMove = {
  from?: XY;
  to: XY;
  piece?: string;
  drop?: boolean;
  promote?: boolean;
  promoted?: boolean;
};

const l1_piece = (m: AnyMove) => (typeof m.piece === "string" ? m.piece : "");
const l1_isPawn = (m: AnyMove) => !!m.from && !m.drop && l1_piece(m) === "P";
const l1_isTokin = (m: AnyMove) => {
  const p = l1_piece(m);
  const promotedByPiece = p.startsWith("+");
  const promotedByFlag = (m as any).promote === true || (m as any).promoted === true;
  return !!m.from && !m.drop && (p === "+P" || promotedByPiece || promotedByFlag);
};
const l1_oneStepStraight = (m: AnyMove) => {
  if (!m.from) return false;
  const dx = Math.abs(m.to.x - m.from.x);
  const dy = Math.abs(m.to.y - m.from.y);
  return dx === 0 && dy === 1;
};
const l1_oneStepSideways = (m: AnyMove) => {
  if (!m.from) return false;
  const dx = Math.abs(m.to.x - m.from.x);
  const dy = Math.abs(m.to.y - m.from.y);
  return dx === 1 && dy === 0;
};
const l1_isKingSideStep = (m: AnyMove) => l1_piece(m) === "K" && l1_oneStepSideways(m);

export const PAWN_LESSON_1_ROLE_STEPS: TrainingStep[] = [
  {
    step: 1,
    title: "歩は自陣の壁",
    description:
      "歩は王様の前で「壁」になります。いまは歩が飛車の筋を止めてくれています。歩は動かさず、王を左右どちらかに1マス動かしてみよう。",
    sfen: "position sfen k3r4/9/9/9/9/9/9/4P4/4K4 b - 1",
    checkMove: (move: AnyMove) => l1_isKingSideStep(move),
    successMessage: "OK！歩が壁になっていると、王が安全になりやすいね。",
  },

  {
    step: 2,
    title: "攻め駒の前の壁は退ける（飛車）",
    description:
      "飛車の前にいる歩は、攻めるときは邪魔になりがち。歩を1マス進めて、飛車の道を作ろう。",
    sfen: "position sfen k8/9/9/9/9/9/9/4P4/4R3K b - 1",
    checkMove: (move: AnyMove) => l1_isPawn(move) && l1_oneStepStraight(move),
    successMessage: "ナイス！攻めるときは「攻め駒の前の壁」をどかす意識が大事。",
  },

  {
    step: 3,
    title: "攻め駒の前の壁は退ける（角）",
    description:
      "角の斜めの道を歩が塞いでいます。歩を1マス進めて、角の道を開けよう。",
    sfen: "position sfen k8/9/9/9/9/9/9/5P3/6B1K b - 1",
    checkMove: (move: AnyMove) => l1_isPawn(move) && l1_oneStepStraight(move),
    successMessage: "OK！角や飛車のラインは、歩で塞がないように意識しよう。",
  },

  {
    step: 4,
    title: "歩はどんどん捨てよう（歩交換）",
    description:
      "歩は軽い駒です。まずは歩を前に進めて相手の歩を取ろう（歩交換）。",
    sfen: "position sfen k8/9/9/9/4p4/4P4/9/9/8K b - 1",
    checkMove: (move: AnyMove) => l1_isPawn(move) && l1_oneStepStraight(move),
    successMessage: "いいね！歩交換は攻めの入口。歩は「軽い」から捨てやすい。",
  },

  {
    step: 5,
    title: "歩はどんどん捨てよう（取らせて崩す）",
    description:
      "相手に取らせる歩も大事。歩を1マス進めると、相手の金が取れる位置になります。歩を1マス進めてみよう。",
    sfen: "position sfen k8/9/9/9/9/4g4/9/4P4/4R3K b - 1",
    checkMove: (move: AnyMove) => l1_isPawn(move) && l1_oneStepStraight(move),
    successMessage: "OK！歩は取られても痛くないことが多い。形を崩すために使えるよ。",
  },

  {
    step: 6,
    title: "と金は強い（成った歩で取ろう）",
    description:
      "歩が成ると「と金」になって強くなります。と金で前の歩を取ってみよう。",
    sfen: "position sfen k8/9/9/9/9/3PpP3/3P+PP3/4P4/8K b - 1",
    checkMove: (move: AnyMove) => l1_isTokin(move) && l1_oneStepStraight(move),
    successMessage: "ナイス！と金は前線で超えらい。歩が成る価値がわかるね。",
  },
];

// （すでにあるなら重複定義しないでOK）
const l2_isPawnDrop = (move: any) => {
  const piece = typeof move?.piece === "string" ? move.piece : "";
  const isDrop = move?.drop === true || move?.from == null; // from無しも打ち扱い
  return isDrop && piece.toUpperCase() === "P";
};

const l2_isPromotedPawnMove = (move: any) => {
  const piece = typeof move?.piece === "string" ? move.piece : "";
  const promotedByPiece = piece.startsWith("+");
  const promotedByFlag = move?.promote === true || move?.promoted === true;
  const isMove = move?.from != null && move?.drop !== true;
  return isMove && (piece === "+P" || promotedByPiece || promotedByFlag);
};

const l2_oneStepStraight = (move: any) => {
  if (!move?.from || !move?.to) return false;
  const dx = Math.abs(move.to.x - move.from.x);
  const dy = Math.abs(move.to.y - move.from.y);
  return dx === 0 && dy === 1;
};

// ---- 54 / 53 判定（座標系の違いに強くする）----
// あなたの move.to が (x,y) / (file,rank) / 0-index / 1-index / 反転 のどれでも拾えるようにしています。
const getXY = (pos: any): { x: number; y: number } | null => {
  if (!pos) return null;
  if (typeof pos.x === "number" && typeof pos.y === "number") return { x: pos.x, y: pos.y };
  if (typeof pos.file === "number" && typeof pos.rank === "number") return { x: pos.file, y: pos.rank };
  return null;
};

const isMasu = (pos: any, file: number, rank: number) => {
  const xy = getXY(pos);
  if (!xy) return false;

  // 候補（よくある4パターン＋保険）
  const candidates: Array<[number, number]> = [
    // 1-index: (file, rank)
    [file, rank],
    // 0-index: (file-1, rank-1)
    [file - 1, rank - 1],
    // file 反転（左が9列のとき）: x = 9-file
    [9 - file, rank - 1],
    // rank 反転（下が9段のとき）: y = 9-rank
    [file - 1, 9 - rank],
    [9 - file, 9 - rank],
    // 1-index + rank反転（保険）
    [file, 10 - rank],
    [10 - file, rank],
  ];

  return candidates.some(([cx, cy]) => xy.x === cx && xy.y === cy);
};

const isTarefuDrop54or53 = (move: any) => {
  if (!l2_isPawnDrop(move)) return false;
  // 5四 or 5三
  return isMasu(move.to, 5, 4) || isMasu(move.to, 5, 3);
};

// --- Lesson 2: 垂れ歩（図1-1 採用版） ---
// ※ SFEN は図1-1 に合わせて作成（表示用）
export const PAWN_LESSON_2_TAREFU_STEPS: TrainingStep[] = [
  {
    step: 1,
    title: "垂れ歩（図1-1）：持ち歩はどこに打つ？",
    description:
      "図1-1の局面です。先手は持ち駒に歩が1枚あります。\n垂れ歩として正しい地点に「歩を打って」ください。",
    // 先手番で先手の持ち駒に歩が1枚ある表示用SFEN
    sfen: "position sfen 7kl/6gb1/8p/5pp2/9/9/9/7R1/4K4 b P 1",
    // 正解マス：ここでは 2三 を正解にする
    checkMove: (m: AnyMove) => l2_isPawnDrop(m) && isMasu(m.to, 2, 4),
    successMessage: "ナイス！そこに打つのが垂れ歩。『次に突いて成る』狙いを作れるよ。",
  },

  {
    step: 2,
    title: "狙いを実行：突いて成る",
    description:
      "垂れ歩を打ったら、次は『突いて成る』のが狙い。\n歩を前に進めて、成れるなら成ってください。",
    // Step1 で 2三 に歩を打った後の局面（表示用）
    sfen: "position sfen 7kl/6gb1/8p/5ppP1/9/9/9/7R1/4K4 b 1",
    // 「成った歩で動いた」＋到達マスが 2二（典型）
    checkMove: (m: AnyMove) => l2_isPromotedPawnMove(m) && isMasu(m.to, 2, 3),
    successMessage: "OK！垂れ歩 → 突いて成る、がつながったね。",
  },
];

// --- Lesson 3: 継ぎ歩 ---
// 既存の type / helper があるため型定義は省略しています
const l3_piece = (m: any) => (typeof m?.piece === "string" ? m.piece : "");
const l3_isPawnMove = (m: any) => !!m?.from && m?.drop !== true && l3_piece(m).toUpperCase() === "P";
const l3_isPawnDrop = (m: any) => (m?.drop === true || m?.from == null) && l3_piece(m).toUpperCase() === "P";

const l3_pawnMoveTo = (file: number, rank: number) => (m: any) => l3_isPawnMove(m) && isMasu(m.to, file, rank);
const l3_pawnDropTo = (file: number, rank: number) => (m: any) => l3_isPawnDrop(m) && isMasu(m.to, file, rank);

// ここだけ触れば「正解地点」と「ヒント表示」を変えられる（手直しが楽）
const l3_cfg = {
  step1_correct_to: sq(2, 4),

  // ★Step1 用の矢印（2五→2四）
  step1_hint_arrow: { from: sq(2, 5), to: sq(2, 4) },

  // Step2: ドロップ先は 2五（継ぎ歩で打つ場所）
  step2_correct_drop_to: sq(2, 5),

  step3_correct_drop_to: sq(8, 4),

  // Step2: drop 用のヒント（to のみ。Overlay 側で from 無しを drop と解釈）
  step2_hint_arrow: { to: sq(2, 5), kind: "drop" as const, dir: "hand" as const },
};

// --- Lesson 3 (scripted single-step with phases) ---
export const PAWN_LESSON_3_TSUGIFU_STEPS: TrainingStep[] = [
  {
    step: 1,
    title: "歩交換：継ぎ歩の練習（段階式）",
    description:
      "継ぎ歩を練習をするときじゃな",
    // デフォルト SFEN はフェーズ0 に合わせる（表示は scriptPhases が優先されます）
    sfen: "position sfen 7kl/6gb1/7pp/5pp2/7P1/9/9/7R1/4K4 b P 1",
    // 矢印は各フェーズ側で指定する（ここは空にしておく）
    hintArrows: [],
    checkMove: l3_pawnMoveTo(l3_cfg.step1_correct_to.file, l3_cfg.step1_correct_to.rank),
    successMessage: "OK！これで継ぎ歩の準備ができました（フェーズ進行）。",

    // スクリプト化したフェーズ（phase0..phase2）
    scriptPhases: [
      // phase0: human: 2五→2四
      {
        sfen: "position sfen 7kl/6gb1/7pp/5pp2/7P1/9/9/7R1/4K4 b P 1",
        hintArrows: [l3_cfg.step1_hint_arrow],
        checkMove: l3_pawnMoveTo(l3_cfg.step1_correct_to.file, l3_cfg.step1_correct_to.rank),
      },

      // phase1: auto snapshot after human move
      {
        sfen: "position sfen 7kl/6gb1/7pp/5ppP1/9/9/9/7R1/4K4 w P 1",
        hintArrows: [],
        checkMove: (_m) => true,
      },

      // phase2: auto-response snapshot (後手 has 2P in hand)
      {
        sfen: "position sfen 7kl/6gb1/8p/5ppp1/9/9/9/7R1/4K4 b 2P 1",
        hintArrows: [l3_cfg.step2_hint_arrow],
        checkMove: l3_pawnDropTo(l3_cfg.step2_correct_drop_to.file, l3_cfg.step2_correct_drop_to.rank),
      },

      // phase3: auto snapshot after human drop
      {
        sfen: "position sfen 7kl/6gb1/8p/5ppp1/7P1/9/9/7R1/4K4 w P 1",
        hintArrows: [],
        checkMove: (_m) => true,
      },

      // phase4: auto-response snapshot where 2五 becomes opponent pawn (手番 b, 持ち駒 Pp)
      {
        sfen: "position sfen 7kl/6gb1/8p/5pp2/7p1/9/9/7R1/4K4 b Pp 1",
        hintArrows: [{ to: sq(2, 4), kind: "drop" as const, dir: "hand" as const }],
        checkMove: l3_pawnDropTo(l3_cfg.step1_correct_to.file, l3_cfg.step1_correct_to.rank),
      },

      // phase5: final snapshot (post auto-response)
      {
        sfen: "position sfen 7kl/6gb1/8p/5ppP1/7p1/9/9/7R1/4K4 w p 1",
        hintArrows: [],
        checkMove: (_m) => true,
        successMessage: "これで君も継ぎ歩マスターじゃ",
      },
    ],
  },
];

// --- Shogi rules foundation lessons (for roadmap rules_* entries) ---
const r_piece = (m: AnyMove) => (typeof m.piece === "string" ? m.piece : "");
const r_hasFrom = (m: AnyMove) => !!m.from && !m.drop;
const r_dxdy = (m: AnyMove) => {
  if (!m.from) return { dx: 99, dy: 99 };
  return { dx: m.to.x - m.from.x, dy: m.to.y - m.from.y };
};
const r_oneStepAny = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return Math.abs(dx) <= 1 && Math.abs(dy) <= 1 && !(dx === 0 && dy === 0);
};
const r_pawnForwardOne = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return r_piece(m).toUpperCase() === "P" && dx === 0 && Math.abs(dy) === 1;
};
const r_lanceLike = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return r_piece(m).toUpperCase() === "L" && dx === 0 && Math.abs(dy) >= 1;
};
const r_knightLike = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return r_piece(m).toUpperCase() === "N" && Math.abs(dx) === 1 && Math.abs(dy) === 2;
};
const r_silverLike = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return r_piece(m).toUpperCase() === "S" && Math.abs(dx) <= 1 && Math.abs(dy) === 1;
};
const r_goldLike = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  if (r_piece(m).toUpperCase() !== "G") return false;
  return Math.abs(dx) + Math.abs(dy) >= 1 && Math.abs(dx) <= 1 && Math.abs(dy) <= 1;
};
const r_bishopLike = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return r_piece(m).toUpperCase().replace("+", "") === "B" && Math.abs(dx) === Math.abs(dy) && Math.abs(dx) >= 1;
};
const r_rookLike = (m: AnyMove) => {
  if (!r_hasFrom(m)) return false;
  const { dx, dy } = r_dxdy(m);
  return r_piece(m).toUpperCase().replace("+", "") === "R" && ((dx === 0 && dy !== 0) || (dx !== 0 && dy === 0));
};

// ルール導入レッスンの見た目系設定（矢印など）をまとめて管理
const RULES_UI = {
  boardPiecesWin: {
    // 4三 → 5二 へ金を動かすヒント矢印
    step1HintArrows: [{ from: sq(4, 3), to: sq(5, 2), kind: "move" as "move" | "drop" }],
    // 正解時に相手玉（5一）を小刻みに横振動
    step1CorrectPieceMotions: [
      {
        target: { file: 5, rank: 1, owner: "gote" as const, pieceBase: "K" as const },
        motion: { type: "shake-x" as const, amplitudePx: 4.2, durationMs: 520, delayMs: 200, repeat: 0 },
      },
    ],
  },
};

export const DEFAULT_SHOGI_RULES_LESSON_ID = "rules_00_board_pieces_win";

export const SHOGI_RULES_LESSON_STEPS: Record<string, TrainingStep[]> = {
  rules_00_board_pieces_win: [
    {
      step: 1,
      title: "盤・駒・勝ち条件",
      description: "将棋は相手の王様を動けなくすれば勝ちじゃ！",
      sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
      hintArrows: RULES_UI.boardPiecesWin.step1HintArrows,
      onCorrectPieceMotions: RULES_UI.boardPiecesWin.step1CorrectPieceMotions,
      demoMoveCheck: (m: AnyMove) =>
        r_hasFrom(m) &&
        r_piece(m).toUpperCase() === "G" &&
        isMasu(m.to, 5, 2),
      // このステップは「正解」扱いにしない（コメント演出のみ）
      checkMove: (_m: AnyMove) => false,
      postCorrectDemo: [
        { delayMs: 0, comment: "もし相手が金を取り返して来たら？" },
        { delayMs: 1500, sfen: "position sfen 9/4k4/4K4/9/9/9/9/9/9 b g 1" },
        { delayMs: 3000, comment: "王様を取り返せる！", sfen: "position sfen 9/4K4/9/9/9/9/9/9/9 b Kg 1" },
        { delayMs: 3000, comment: "王様がとられてしまうから、\n王様が動けなくなった時点で勝ち！", markCorrect: true },
      ],
      successMessage: "OK！王を詰ませるのが勝ち条件です。",
    },
    {
      step: 2,
      title: "盤・駒・勝ち条件",
      description: "王様が動けない状態。。。\n世界はそれを「詰み」（つみ）と呼ぶんだぜ！！",
      sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
      hintArrows: RULES_UI.boardPiecesWin.step1HintArrows,
      onCorrectPieceMotions: RULES_UI.boardPiecesWin.step1CorrectPieceMotions,
      checkMove: (m: AnyMove) =>
        r_hasFrom(m) &&
        r_piece(m).toUpperCase() === "G" &&
        isMasu(m.from, 4, 3) &&
        isMasu(m.to, 5, 2),
      successMessage: "相手の王様を「詰ます」ことが将棋の勝利条件なのじゃ",
    },
    {
      step: 3,
      title: "盤・駒・勝ち条件（実践）",
      description: "金を5二に動かして、王様がどこにも逃げられないことを体験しよう。",
      sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
      hintArrows: RULES_UI.boardPiecesWin.step1HintArrows,
      checkMove: (_m: AnyMove) => false,
      scriptPhases: [
        {
          sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
          hintArrows: [{ from: sq(4, 3), to: sq(5, 2), kind: "move" }],
          checkMove: (m: AnyMove) =>
            r_hasFrom(m) &&
            r_piece(m).toUpperCase() === "G" &&
            isMasu(m.from, 4, 3) &&
            isMasu(m.to, 5, 2),
          successMessage: "相手の王様はどこにも動けない。",
        },
        {
          // 相手玉が41に逃げる → プレイヤーが金で取る
          sfen: "position sfen 5k3/4G4/4K4/9/9/9/9/9/9 b - 1",
          delayMs: 500,
          hintArrows: [{ from: sq(5, 2), to: sq(4, 1), kind: "move" }],
          checkMove: (m: AnyMove) =>
            r_hasFrom(m) &&
            r_piece(m).toUpperCase() === "G" &&
            isMasu(m.from, 5, 2) &&
            isMasu(m.to, 4, 1),
          successMessage: "逃げても取れる！",
        },
        {
          // 金を43へ戻し、相手玉は51から → もう一度52へ寄る
          sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
          hintArrows: [{ from: sq(4, 3), to: sq(5, 2), kind: "move" }],
          checkMove: (m: AnyMove) =>
            r_hasFrom(m) &&
            r_piece(m).toUpperCase() === "G" &&
            isMasu(m.from, 4, 3) &&
            isMasu(m.to, 5, 2),
          successMessage: "もう一度52へ寄ってみよう。",
        },
        {
          // 相手玉が42に逃げる → プレイヤーが金で取る
          sfen: "position sfen 9/4Gk3/4K4/9/9/9/9/9/9 b - 1",
          delayMs: 500,
          hintArrows: [{ from: sq(5, 2), to: sq(4, 2), kind: "move" }],
          checkMove: (m: AnyMove) =>
            r_hasFrom(m) &&
            r_piece(m).toUpperCase() === "G" &&
            isMasu(m.from, 5, 2) &&
            isMasu(m.to, 4, 2),
          successMessage: "斜めに逃げても取れる！",
        },
        {
          // 追加: 4k4/9/4Gk... 局面（旧5番を6番へ）
          sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
          hintArrows: [{ from: sq(4, 3), to: sq(5, 2), kind: "move" }],
          checkMove: (m: AnyMove) =>
            r_hasFrom(m) &&
            r_piece(m).toUpperCase() === "G" &&
            isMasu(m.from, 4, 3) &&
            isMasu(m.to, 5, 2),
          successMessage: "この形でも同じじゃ。",
        },
        {
          // 相手玉が金を取る → プレイヤーが自玉で取り返す
          sfen: "position sfen 9/4k4/4K4/9/9/9/9/9/9 b g 1",
          hintArrows: [{ from: sq(5, 3), to: sq(5, 2), kind: "move" }],
          checkMove: (m: AnyMove) =>
            r_hasFrom(m) &&
            r_piece(m).toUpperCase() === "K" &&
            isMasu(m.from, 5, 3) &&
            isMasu(m.to, 5, 2),
          successMessage: "王様がどこに逃げても同じじゃ！",
        },
      ],
      successMessage: "素晴らしい！王様を詰ませる感覚が掴めたかな？",
    },
    {
      step: 4,
      title: "盤・駒・勝ち条件（確認問題）",
      description: "同じ局面で 5二に金を動かしてから、ゲーム終了かどうかを答えよう。",
      sfen: "position sfen 4k4/9/4KG3/9/9/9/9/9/9 b - 1",
      hintArrows: RULES_UI.boardPiecesWin.step1HintArrows,
      // まずは 5二に金を動かす
      checkMove: (m: AnyMove) =>
        r_hasFrom(m) &&
        r_piece(m).toUpperCase() === "G" &&
        isMasu(m.to, 5, 2),
      // 着手後に二択を表示
      choiceQuestion: {
        prompt: "これでゲームは終了？",
        options: [
          { label: "終了", correct: true },
          { label: "終わりじゃない", correct: false },
        ],
      },
      successMessage: "正解！この形は終了（先手勝ち）です。",
    },
  ],
  rules_01_capture_and_hands: [
    {
      step: 1,
      title: "駒の取り方・持ち駒",
      description: "歩で前の相手駒を取ってみよう。取った駒は持ち駒になります。",
      sfen: "position sfen 4k4/9/9/9/9/4p4/4P4/9/4K4 b - 1",
      checkMove: (m: AnyMove) => r_pawnForwardOne(m),
      successMessage: "ナイス！取った駒は次に“打つ”ことができます。",
    },
  ],
  rules_02_pawn_move_single: [
    {
      step: 1,
      title: "歩の動き（1枚）",
      description: "歩は前に1マス。1手だけ進めてみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/4P4/9/4K4 b - 1",
      hintStars: [{ file: 5, rank: 6 }],
      checkMove: (m: AnyMove) => r_pawnForwardOne(m),
      successMessage: "正解！歩は前に1マスです。",
    },
  ],
  rules_03_lance_knight_silver_gold: [
    {
      step: 1,
      title: "香・桂・銀・金の動き",
      description: "香車を前に動かしてみよう（まずは近接駒の導入）。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/L8/4K4 b - 1",
      checkMove: (m: AnyMove) => r_lanceLike(m),
      successMessage: "OK！香車は前へまっすぐ進みます。",
    },
    {
      step: 2,
      title: "香・桂・銀・金の動き",
      description: "桂馬を“L字”に跳ねてみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/1N7/4K4 b - 1",
      checkMove: (m: AnyMove) => r_knightLike(m),
      successMessage: "ナイス！桂馬は1つ飛び越えて動けます。",
    },
    {
      step: 3,
      title: "香・桂・銀・金の動き",
      description: "銀か金を1手動かして、違いを体感しよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/4S4/4G4/4K4 b - 1",
      checkMove: (m: AnyMove) => r_silverLike(m) || r_goldLike(m),
      successMessage: "OK！銀と金は利きが少し違います。",
    },
  ],
  rules_04_bishop_rook_range: [
    {
      step: 1,
      title: "角・飛の動き",
      description: "角を斜めに動かしてみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/2B6/4K4 b - 1",
      checkMove: (m: AnyMove) => r_bishopLike(m),
      successMessage: "正解！角は斜めの遠距離駒です。",
    },
    {
      step: 2,
      title: "角・飛の動き",
      description: "飛車を縦か横に動かしてみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/2R6/4K4 b - 1",
      checkMove: (m: AnyMove) => r_rookLike(m),
      successMessage: "正解！飛車は縦横の遠距離駒です。",
    },
  ],
  rules_05_promotion_basics: [
    {
      step: 1,
      title: "成りの基本",
      description: "敵陣で歩を進めて、成りの発生を体験しよう。",
      sfen: "position sfen 4k4/9/9/4P4/9/9/9/9/4K4 b - 1",
      checkMove: (m: AnyMove) => r_piece(m).toUpperCase().replace("+", "") === "P" && r_pawnForwardOne(m),
      successMessage: "OK！成れる条件を満たすと成る/不成を選べます。",
    },
    {
      step: 2,
      title: "成りの基本",
      description: "今回は“成る”を選んでみよう。",
      sfen: "position sfen 4k4/9/4P4/9/9/9/9/9/4K4 b - 1",
      checkMove: (m: AnyMove) => l2_isPromotedPawnMove(m),
      successMessage: "正解！駒が成ると利きが強くなることがあります。",
    },
  ],
  rules_06_drop_basics: [
    {
      step: 1,
      title: "打つ（持ち駒を置く）",
      description: "持ち駒は、打ったあとに次の手で動ける場所にしか打てません。歩を打てるマスを見つけて打ってみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b P 1",
      checkMove: (m: AnyMove) => l2_isPawnDrop(m),
      successMessage: "ナイス！『打ったあとも動ける場所に打つ』が大事な基本です。",
    },
    {
      step: 2,
      title: "打つ（持ち駒を置く）",
      description: "持ち駒の歩を盤上に打ってみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b P 1",
      checkMove: (m: AnyMove) => l2_isPawnDrop(m),
      successMessage: "ナイス！持ち駒は“打つ”ことで再利用できます。",
    },
  ],
  rules_07_nifu: [
    {
      step: 1,
      title: "禁止事項：二歩",
      description: "同じ筋に自分の歩がある場所には打てません。別の筋に歩を打とう。",
      sfen: "position sfen 4k4/9/9/9/4P4/9/9/9/4K4 b P 1",
      checkMove: (m: AnyMove) => l2_isPawnDrop(m) && !isMasu(m.to, 5, 5),
      successMessage: "OK！同じ筋に歩を2枚置く二歩は禁止です。",
    },
  ],
  rules_08_uchifuzume_intro: [
    {
      step: 1,
      title: "禁止事項：打ち歩詰め（紹介）",
      description: "打ち歩詰めという禁止ルールがあります。ここでは“存在”だけ覚えよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/4K4/9 b - 1",
      checkMove: (m: AnyMove) => r_piece(m).toUpperCase() === "K" && r_oneStepAny(m),
      successMessage: "了解！打ち歩詰めは実戦で必ず意識するルールです。",
    },
  ],
  rules_09_check_and_responses: [
    {
      step: 1,
      title: "王手と応手：逃げる",
      description: "王手されたら、まず“逃げる”対応をしてみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/4K4/4r4 b - 1",
      checkMove: (m: AnyMove) => r_piece(m).toUpperCase() === "K" && r_oneStepAny(m),
      successMessage: "OK！受け方1つ目は“逃げる”。",
    },
    {
      step: 2,
      title: "王手と応手：取る",
      description: "次は攻め駒を“取る”対応をしよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/3GK4/9 b - 1",
      checkMove: (m: AnyMove) => r_piece(m).toUpperCase() === "G" && r_oneStepAny(m),
      successMessage: "OK！受け方2つ目は“取る”。",
    },
    {
      step: 3,
      title: "王手と応手：合い駒",
      description: "最後は“合い駒”で利きを遮ってみよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/4K4/4r4 b G 1",
      checkMove: (m: AnyMove) => m.drop === true,
      successMessage: "ナイス！受け方3つ目は“合い駒”。",
    },
  ],
  rules_10_sennichite_jishogi: [
    {
      step: 1,
      title: "千日手・持将棋（紹介）",
      description: "千日手・持将棋は引き分け系の重要ルールです。まずは名前を覚えよう。",
      sfen: "position sfen 4k4/9/9/9/9/9/9/4K4/9 b - 1",
      checkMove: (m: AnyMove) => r_piece(m).toUpperCase() === "K" && r_oneStepAny(m),
      successMessage: "OK！実戦で出たときに判断できれば十分です。",
    },
  ],
};