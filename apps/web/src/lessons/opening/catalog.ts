export type OpeningLevel = "L1" | "L2" | "L3";

export type OpeningCatalogItem = {
  id: string;
  nameJa: string;
  skillTag: string;
  levelSet: OpeningLevel[];
  sourceUrl: string;
};

export const OPENING_CATALOG: OpeningCatalogItem[] = [
  { id: "yagura-opening", nameJa: "矢倉（戦法）", skillTag: "opening:yagura", levelSet: ["L1"], sourceUrl: "" },
  { id: "kaku-gawari", nameJa: "角換わり", skillTag: "opening:kaku_gawari", levelSet: ["L1"], sourceUrl: "" },
  { id: "yokofudori", nameJa: "横歩取り", skillTag: "opening:yokofudori", levelSet: ["L1"], sourceUrl: "" },
  { id: "aigakari", nameJa: "相掛かり", skillTag: "opening:aigakari", levelSet: ["L1"], sourceUrl: "" },
  { id: "shikenbisha", nameJa: "四間飛車", skillTag: "opening:shikenbisha", levelSet: ["L1"], sourceUrl: "" },
  { id: "sankenbisha", nameJa: "三間飛車", skillTag: "opening:sankenbisha", levelSet: ["L1"], sourceUrl: "" },
  { id: "mukai-bisha", nameJa: "向かい飛車", skillTag: "opening:mukai_bisha", levelSet: ["L1"], sourceUrl: "" },
  { id: "nakabisha", nameJa: "中飛車", skillTag: "opening:nakabisha", levelSet: ["L1"], sourceUrl: "" },
];


