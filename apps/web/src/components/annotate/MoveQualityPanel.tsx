"use client";

import React from "react";
import { getImpactDescriptor, type HighlightClassification } from "@/lib/analysisUtils";
import styles from "./MoveQualityPanel.module.css";

type MoveQualityItem = {
  ply: number;
  moveLabel: string;
  diff: number | null;
};

type MoveQualityPanelProps = {
  items: MoveQualityItem[];
};

const indicatorClassMap: Record<HighlightClassification, string> = {
  good: styles.indicatorGood,
  inaccuracy: styles.indicatorInaccuracy,
  mistake: styles.indicatorMistake,
  blunder: styles.indicatorBlunder,
};

const labelMap: Record<HighlightClassification, string> = {
  good: "好手 (Good)",
  inaccuracy: "疑問手 (Inaccuracy)",
  mistake: "悪手 (Mistake)",
  blunder: "大悪手 (Blunder)",
};

export default function MoveQualityPanel({ items }: MoveQualityPanelProps) {
  const notableItems = items
    .map((item) => {
      const descriptor = getImpactDescriptor(item.diff);
      if (!descriptor.highlight) return null;
      return {
        ply: item.ply,
        moveLabel: item.moveLabel,
        diffLabel: descriptor.diffLabel,
        classification: descriptor.classification as HighlightClassification,
      };
    })
    .filter((entry): entry is { ply: number; moveLabel: string; diffLabel: string; classification: HighlightClassification } =>
      Boolean(entry),
    );

  return (
    <div className={styles.panel}>
      <div className={styles.header}>好手 / 悪手サマリー</div>
      {notableItems.length ? (
        <ul className={styles.list}>
          {notableItems.map((item) => (
            <li key={item.ply} className={styles.item}>
              <div className={`${styles.indicator} ${indicatorClassMap[item.classification]}`} />
              <div className={styles.itemBody}>
                <div className={styles.itemTitle}>
                  <span className={styles.itemPly}>{item.ply}手目</span>
                  <span className={styles.itemMove}>{item.moveLabel}</span>
                </div>
                <div className={styles.itemMeta}>
                  <span className={styles.itemClassification}>{labelMap[item.classification]}</span>
                  <span className={styles.itemDiff}>{item.diffLabel}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className={styles.empty}>解析結果が集まるとここに表示されます。</div>
      )}
    </div>
  );
}
