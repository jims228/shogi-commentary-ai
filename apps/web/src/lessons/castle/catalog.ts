export type CastleLevel = "L1" | "L2" | "L3";

export type CastleCatalogItem = {
  id: string;
  nameJa: string;
  skillTag: string;
  levelSet: CastleLevel[];
  sourceUrl: string;
};

export const CASTLE_CATALOG: CastleCatalogItem[] = [
  { id: "yagura", nameJa: "矢倉", skillTag: "castle:yagura", levelSet: ["L1"], sourceUrl: "" },
  { id: "funagakoi", nameJa: "舟囲い", skillTag: "castle:funagakoi", levelSet: ["L1"], sourceUrl: "" },
  { id: "mino", nameJa: "美濃囲い", skillTag: "castle:mino", levelSet: ["L1"], sourceUrl: "" },
  { id: "hidari-mino", nameJa: "左美濃", skillTag: "castle:hidari_mino", levelSet: ["L1"], sourceUrl: "" },
  { id: "anaguma", nameJa: "穴熊", skillTag: "castle:anaguma", levelSet: ["L1"], sourceUrl: "" },
  { id: "kinmusou", nameJa: "金無双", skillTag: "castle:kinmusou", levelSet: ["L1"], sourceUrl: "" },
  { id: "nakazumai", nameJa: "中住まい", skillTag: "castle:nakazumai", levelSet: ["L1"], sourceUrl: "" },
];


