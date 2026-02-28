/**
 * 解説機能の入出力型定義
 * 対応バックエンド: backend/api/services/ai_service.py, backend/api/main.py /api/explain
 */

// ---------------------------------------------------------------------------
// DB参照結果（wkbk_articles / shogi-extend 由来）
// ---------------------------------------------------------------------------

export type WkbkDbRefItem = {
  /** wkbk_articles の key（MD5ハッシュ） */
  key: string;
  /** lineage カテゴリ（手筋/詰将棋/etc.） — 著作権に配慮し title は含まない */
  lineage_key: string;
  /** タグ一覧 */
  tags: string[];
  /** 難易度 1〜5 */
  difficulty: number | null;
  /** lineage_key の UI 表示ヒント（丸写し禁止のため title は入らない） */
  category_hint: string | null;
  /** LLM生成済みの goal が存在する場合のみ、要約文を含む */
  goal_summary: string | null;
};

export type DbRefs = {
  /** SFEN による検索でヒットしたか */
  hit: boolean;
  /** ヒットした場合の詳細 */
  items: WkbkDbRefItem[];
};

// ---------------------------------------------------------------------------
// /api/explain リクエスト
// ---------------------------------------------------------------------------

export type ExplainRequest = {
  /** 局面 SFEN（"position sfen ..." 形式、または "startpos" も可） */
  sfen?: string;
  /** 手番（"b" = 先手 / "w" = 後手） */
  turn?: "b" | "w";
  /** 手数（0始まり） */
  ply?: number;
  /** エンジン推奨手（USI形式） */
  bestmove?: string;
  /** エンジン評価値（センチポーン） */
  score_cp?: number | null;
  /** 詰み手数（正=先手詰み, 負=後手詰み） */
  score_mate?: number | null;
  /** PV（主要変化）— スペース区切りの USI 手順 */
  pv?: string;
  /** ユーザーが実際に指した手（USI形式） */
  user_move?: string;
  /** Δcp（指した手とbestmoveの評価差） */
  delta_cp?: number | null;
  /** 候補手一覧（MultiPV出力） */
  candidates?: ExplainCandidate[];
  /** 棋力レベル */
  explain_level?: "beginner" | "intermediate" | "advanced";
  /** 棋譜全体の手順（USI形式リスト） */
  history?: string[];
};

export type ExplainCandidate = {
  move: string;
  score_cp?: number | null;
  score_mate?: number | null;
  pv?: string;
};

// ---------------------------------------------------------------------------
// /api/explain レスポンス（既存 + db_refs 追加）
// ---------------------------------------------------------------------------

export type PvGuideItem = {
  move: string;
  note: string;
};

export type DetectionItem = {
  id: string;
  nameJa: string;
  confidence: number;
  reasons: string[];
};

/** 構造化解説 JSON（既存 ExplainJson 互換） */
export type ExplainJson = {
  headline: string;
  why: string[];
  pvGuide: PvGuideItem[];
  risks: string[];
  confidence: number;
  style?: DetectionItem | null;
  opening?: DetectionItem | null;
  castle?: DetectionItem | null;
};

export type ExplainVerify = {
  ok: boolean;
  errors: string[];
};

export type ExplainResponse = {
  /** テキスト形式の解説（フォールバック用） */
  explanation: string;
  /** 構造化解説 JSON（preferred） */
  explanation_json?: ExplainJson | null;
  /** スキーマ検証結果 */
  verify?: ExplainVerify;
  /** wkbk DB 参照結果 */
  db_refs?: DbRefs;
};

// ---------------------------------------------------------------------------
// /api/explain/digest レスポンス
// ---------------------------------------------------------------------------

export type TurningPoint = {
  ply: number;
  move: string;
  why: string;
  evidence: EvidenceItem;
  db_refs?: DbRefs;
};

export type Mistake = {
  ply: number;
  move: string;
  reason: string;
  next_time_tip: string;
  evidence: EvidenceItem;
  db_refs?: DbRefs;
};

export type BestAlternative = {
  ply: number;
  played: string;
  best: string;
  diff: number;
  evidence: EvidenceItem;
};

export type EvidenceItem = {
  pv: string[];
  eval_before: number | null;
  eval_after: number | null;
  eval_delta: number | null;
  mate?: number | null;
};

export type FullGameExplainResponse = {
  summary: string[];
  turning_points: TurningPoint[];
  mistakes: Mistake[];
  best_alternatives: BestAlternative[];
};
