/**
 * arrowGeometry.ts — 矢印座標計算の一元管理
 *
 * ★ 座標系：すべてのサイズ値は「マス単位 (0〜9)」で指定する。
 *   ArrowOverlay SVG は viewBox="0 0 9 9" を使い、実際の描画サイズ
 *   (boardSize px) に自動スケーリングされる。
 *   → boardSize の変化 / AutoScaleToFit の transform に完全追従する。
 *
 * ★ 調整ポイント
 *   - 線の太さ      → DEFAULT_ARROW_STYLE.strokeWidth  (マス単位)
 *   - 矢尻の大きさ  → DEFAULT_ARROW_STYLE.headSize      (マス単位)
 *   - 始点の位置     → DEFAULT_ARROW_STYLE.startCircleRadius (マス単位)
 *   - 色・透明度     → DEFAULT_ARROW_STYLE.color / opacity
 *   - 破線パターン   → DEFAULT_ARROW_STYLE.dashArray     (マス単位)
 */

// ───── 基準定数 ─────

/** 参照マスサイズ（px）。ドキュメント目的のみ（座標計算では使わない） */
export const REF_CELL = 50;

/** 参照ボードサイズ（px）。ドキュメント目的のみ */
export const REF_BOARD = REF_CELL * 9; // 450

/** SVG viewBox に使うマス数。ArrowOverlay は viewBox="0 0 9 9" を使う */
export const REF_BOARD_CELLS = 9;

// ───── 型定義 ─────

/** 盤面マス座標 (0‥8, 左上=0,0) */
export type Square = { x: number; y: number };

/**
 * 矢印ごとの見た目スタイル。
 * 省略したプロパティには DEFAULT_ARROW_STYLE が使われる。
 */
export type ArrowStyle = {
  /** 線の太さ（基準 px, default 8） */
  strokeWidth?: number;
  /** 色（CSS color, default "#f59e0b" = amber-400） */
  color?: string;
  /** 不透明度 0‥1（default 0.85） */
  opacity?: number;
  /** 矢尻の大きさ（基準 px, default 18） */
  headSize?: number;
  /**
   * 始点オフセット半径（基準 px, default 14）。
   * from マス中心から to 方向へ radius だけずらした円周上の点が始点になる。
   */
  startCircleRadius?: number;
  /** 破線パターン（基準 px, default "12 6"）。undefined で実線 */
  dashArray?: string;
  /** 破線アニメーション（default true） */
  animated?: boolean;
};

/** 矢印データ */
export type Arrow = {
  id: string;
  from: Square;
  to: Square;
  style?: ArrowStyle;
};

// ───── デフォルトスタイル ─────

export const DEFAULT_ARROW_STYLE: Required<ArrowStyle> = {
  // ★ マス単位 (0〜9 座標系)。1マス = REF_CELL(50)px 相当。
  strokeWidth: 0.22,          // mobile でも視認しやすいサイズ
  color: "#f59e0b",
  opacity: 0.95,
  headSize: 0.55,             // mobile でもはっきり見える矢尻
  startCircleRadius: 0.30,    // 始点オフセット—短距離でも消えない値
  dashArray: "",              // "" (empty) = 実線。ArrowOverlay で || undefined 判定済み
  animated: false,            // デフォルトは非アニメ
};

// ───── ユーティリティ ─────

/**
 * 将棋座標 (file 1―9, rank 1―9) → 表示インデックス (x 0―8, y 0―8)。
 *   先手表示: file 9→x 0 … file 1→x 8,  rank 1→y 0 … rank 9→y 8
 *   後手表示: file 1→x 0 … file 9→x 8,  rank 9→y 0 … rank 1→y 8
 *
 * ★ 必ず整数 (0..8) を返す。小数除算・+0.5 などは一切しない。
 */
export function shogiToDisplay(file: number, rank: number, flipped = false) {
  // file/rank: 1..9 (将棋座標) → x,y: 0..8 (マスインデックス)
  if (!flipped) {
    return { x: 9 - file, y: rank - 1 };
  }
  return { x: file - 1, y: 9 - rank };
}

/**
 * マス中心のセル座標 (viewBox 0〜9 系)。
 * ArrowOverlay が viewBox="0 0 9 9" を使うため、この座標をそのまま使う。
 */
export function cellCenter(sq: Square): { cx: number; cy: number } {
  return {
    cx: sq.x + 0.5,
    cy: sq.y + 0.5,
  };
}

/**
 * @deprecated cellCenter() を使うこと。旧px座標系 (viewBox 0〜450) 用。
 * ArrowOverlay が viewBox="0 0 9 9" に移行したため非推奨。
 */
export function cellCenterPx(sq: Square): { cx: number; cy: number } {
  return {
    cx: (sq.x + 0.5) * REF_CELL,
    cy: (sq.y + 0.5) * REF_CELL,
  };
}

/** ArrowStyle のデフォルトマージ */
export function mergeStyle(
  base: Required<ArrowStyle>,
  override?: ArrowStyle,
): Required<ArrowStyle> {
  if (!override) return base;
  return { ...base, ...override };
}

/**
 * 矢印の始点 (x1,y1) ・終点 (x2,y2) をセル座標 (0〜9) で返す。
 *
 * ★ 計算ルール
 *   - 終点: toCenter から headSize 分だけ手前に引き戻す
 *     → marker（refX=headSize）で矢尻先端が toCenter に来る
 *     → line 本体は矢尻の根元で終わり、「線が長すぎる」問題を解消
 *   - 始点: from 中心 → to 方向に startOff だけオフセット
 *     → startOff は len*0.4 までクランプ（短距離で矢印が消えないため）
 *   - len ≤ 1e-6 の場合は同一点を返す（描画側で skip）
 */
export function arrowEndpoints(
  from: Square,
  to: Square,
  style: Required<ArrowStyle>,
): { x1: number; y1: number; x2: number; y2: number } {
  const fc = cellCenter(from);
  const tc = cellCenter(to);

  const dx = tc.cx - fc.cx;
  const dy = tc.cy - fc.cy;
  const len = Math.hypot(dx, dy);

  // 同一マス: 描画側で skip されるが一応安全な値を返す
  if (len < 1e-6) {
    return { x1: fc.cx, y1: fc.cy, x2: tc.cx, y2: tc.cy };
  }

  const ux = dx / len;
  const uy = dy / len;

  // startOff は 「矢印長の 40%」を上限にクランプ
  const startOff = Math.min(style.startCircleRadius, len * 0.4);

  // endOff: line 終点を手前に引き戻す (線を短くする)。
  // 矢尻先端は toCenter に留まるよう ArrowOverlay の refX で補正する。
  //   refX = headSize - endOff → 矢尻先端が endOff 分だけ line 終点より先に突出
  //   → 結果: 矢尻先端 = line終点 + endOff = toCenter に一致
  const endOff = Math.min(style.headSize * 0.6, len * 0.4);

  return {
    x1: fc.cx + ux * startOff,
    y1: fc.cy + uy * startOff,
    x2: tc.cx - ux * endOff,
    y2: tc.cy - uy * endOff,
  };
}
