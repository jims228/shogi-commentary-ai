#!/usr/bin/env python3
"""
ML学習用データ生成スクリプト
wkbk_articles.jsonl → annotate API → training_data.csv
"""
import json
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.services.features import notes_to_explanations, classify_blunder

WKBK_PATH = Path("tools/datasets/wkbk/wkbk_articles.jsonl")
OUTPUT_PATH = Path("tools/datasets/ml/training_data.csv")

def load_wkbk(path: Path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def kifu_to_notes(kifu: str):
    import httpx
    # "position sfen ..." → そのままUSIとして渡す
    # init_sfenはすでに "position sfen ..." 形式なのでusinewgame後に使える
    usi = kifu  # annotateはposition sfen形式も受け付けるはず
    try:
        resp = httpx.post(
            "http://localhost:8787/annotate",
            json={"usi": usi},
            timeout=30.0,
        )
        data = resp.json()
        notes = data.get("notes", [])
        if not notes:
            # デバッグ: レスポンス確認
            print(f"  Response: {str(data)[:100]}")
        return notes, data.get("bioshogi")
    except Exception as e:
        print(f"  Error: {e}")
        return [], None

def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    articles = list(load_wkbk(WKBK_PATH))
    print(f"Loaded {len(articles)} articles")

    rows = []
    for i, article in enumerate(articles[:50]):  # まず50件でテスト
        init_sfen = article.get("init_sfen") or ""
        if not init_sfen:
            continue
        # "position sfen <sfen>" の sfen部分を抽出
        sfen_part = init_sfen.replace("position sfen ", "").strip()
        # 正解手順を取得
        moves_answers = article.get("moves_answers", [])
        if not moves_answers:
            continue
        moves_str = moves_answers[0].get("moves_str", "")
        if not moves_str:
            continue
        # USI形式に組み立て
        kifu = f"startpos moves {moves_str}" if sfen_part.startswith("lnsgkgsnl") else f"sfen {sfen_part} moves {moves_str}"

        print(f"[{i+1}/50] Processing {article.get('lineage_key', '?')}...")
        notes, bioshogi = kifu_to_notes(kifu)
        explanations = notes_to_explanations(notes, bioshogi)

        for exp in explanations:
            if exp.eval_delta is None:
                continue
            blunder = classify_blunder(exp.eval_delta)
            label = blunder[0] if blunder else "普通"
            rows.append({
                "ply": exp.ply,
                "move": exp.move,
                "eval_before": exp.eval_before,
                "eval_after": exp.eval_after,
                "eval_delta": exp.eval_delta,
                "phase": exp.position_phase.value if exp.position_phase else "",
                "move_type": exp.move_type.value if exp.move_type else "",
                "castle_info": exp.castle_info or "",
                "attack_info": exp.attack_info or "",
                "technique_count": len(exp.technique_info),
                "label": label,
            })

    if not rows:
        print("No data generated")
        return

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_PATH}")

    # 統計表示
    from collections import Counter
    labels = Counter(r["label"] for r in rows)
    print("Label distribution:")
    for label, count in labels.most_common():
        print(f"  {label}: {count}")

if __name__ == "__main__":
    main()
