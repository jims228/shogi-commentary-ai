export type TesujiPiece =
  | "pawn"
  | "lance"
  | "knight"
  | "silver"
  | "gold"
  | "bishop"
  | "rook";

export type TesujiLevel = "L1" | "L2" | "L3";

export type TesujiCatalogItem = {
  /** file名やURLに使う想定のslug */
  id: string;
  piece: TesujiPiece;
  techniqueNameJa: string;
  /** 習熟度トラッキング用のタグ（localStorage等のキーとして使う想定） */
  skillTag: string;
  /** 対応するレベルセット（例: L1のみ先に埋める） */
  levelSet: TesujiLevel[];
  /** 出典リンク表示用（MVPでは未使用でもOK） */
  sourceUrl: string;
};

/**
 * 手筋カタログ（量産の母艦）
 *
 * - techniqueNameJa は「指定の一覧」と完全一致させる
 * - sourceUrl は後で実URLを入れる（文章/図の転載はしない）
 */
export const TESUJI_CATALOG: TesujiCatalogItem[] = [
  // pawn
  { id: "tarefu", piece: "pawn", techniqueNameJa: "垂れ歩", skillTag: "pawn:tarefu", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "tsugifu", piece: "pawn", techniqueNameJa: "継ぎ歩", skillTag: "pawn:tsugifu", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "tataki", piece: "pawn", techniqueNameJa: "叩きの歩/焦点の歩", skillTag: "pawn:tataki_focus", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "renda", piece: "pawn", techniqueNameJa: "歩の連打", skillTag: "pawn:ren_da", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "hikae", piece: "pawn", techniqueNameJa: "控えの歩", skillTag: "pawn:hikae", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "sokobu", piece: "pawn", techniqueNameJa: "底歩", skillTag: "pawn:sokobu", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },

  // lance
  { id: "dengaku-sashi", piece: "lance", techniqueNameJa: "田楽刺し", skillTag: "lance:dengaku", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "2dan-rocket", piece: "lance", techniqueNameJa: "2段ロケット", skillTag: "lance:2dan_rocket", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "sokokyo", piece: "lance", techniqueNameJa: "底香", skillTag: "lance:sokokyo", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },

  // knight
  { id: "fundoshi-kei", piece: "knight", techniqueNameJa: "ふんどしの桂", skillTag: "knight:fundoshi", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "futo-no-kei", piece: "knight", techniqueNameJa: "歩頭の桂", skillTag: "knight:futo", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "tsurushi-kei", piece: "knight", techniqueNameJa: "つるし桂", skillTag: "knight:tsurushi", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "hikae-kei", piece: "knight", techniqueNameJa: "控えの桂", skillTag: "knight:hikae", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "tsugikei", piece: "knight", techniqueNameJa: "継ぎ桂", skillTag: "knight:tsugi", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },

  // silver
  { id: "warigin", piece: "silver", techniqueNameJa: "割打ちの銀", skillTag: "silver:warigin", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "keitogin", piece: "silver", techniqueNameJa: "桂頭の銀", skillTag: "silver:keitogin", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "haragin", piece: "silver", techniqueNameJa: "腹銀", skillTag: "silver:haragin", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },

  // gold
  { id: "atamakin", piece: "gold", techniqueNameJa: "頭金", skillTag: "gold:atama", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "shirikin", piece: "gold", techniqueNameJa: "尻金", skillTag: "gold:shirikin", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },

  // bishop
  { id: "kaku-ryotori", piece: "bishop", techniqueNameJa: "角での両取り", skillTag: "bishop:ryotori", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "suji-chigai", piece: "bishop", techniqueNameJa: "筋違いの角打ち", skillTag: "bishop:suji_chigai", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "kaku-kei", piece: "bishop", techniqueNameJa: "角桂連携", skillTag: "bishop:kaku_kei", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "kobo-kaku", piece: "bishop", techniqueNameJa: "攻防の角", skillTag: "bishop:kobo", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },

  // rook
  { id: "juji-hisha", piece: "rook", techniqueNameJa: "十字飛車", skillTag: "rook:juji", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "home-rook-drop", piece: "rook", techniqueNameJa: "自陣への飛車打ち", skillTag: "rook:home_drop", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "ikken-ryu", piece: "rook", techniqueNameJa: "一間龍", skillTag: "rook:ikken", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
  { id: "okuri", piece: "rook", techniqueNameJa: "送りの手筋", skillTag: "rook:okuri", levelSet: ["L1", "L2", "L3"], sourceUrl: "" },
];


