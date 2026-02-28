# 将棋解説AI (shogi-commentary-ai)

将棋の棋譜を解析し、手の意図・戦略・評価値をわかりやすく解説するAIシステムです。

## 概要

- **やねうら王** エンジンによる局面評価・最善手探索
- **Gemini** LLMによる自然言語解説生成
- **Supabase** による棋譜・解析結果の永続化
- **FastAPI** による REST API 提供

## ディレクトリ構成

```
shogi-commentary-ai/
├── backend/
│   ├── api/
│   │   ├── main.py          # FastAPI アプリ
│   │   ├── routers/         # エンドポイント定義
│   │   │   ├── annotate.py  # /annotate - 棋譜一括解析
│   │   │   ├── explain.py   # /api/explain - 1手解説
│   │   │   └── games.py     # /api/games - 棋譜管理
│   │   ├── services/        # ビジネスロジック
│   │   │   ├── engine.py    # やねうら王連携
│   │   │   ├── explanation.py  # 解説生成 (LLM)
│   │   │   ├── features.py  # 特徴量抽出
│   │   │   └── bioshogi.py  # bioshogi API クライアント
│   │   ├── db/
│   │   │   └── wkbk_db.py   # 将棋問題DB アクセス層
│   │   └── utils/
│   │       └── gemini_client.py  # Gemini API 設定
│   └── models/
│       └── explanation.py   # MoveExplanation / GameReport データ構造
├── engine/
│   └── engine_server.py     # USI エンジン HTTP ゲートウェイ
├── supabase/
│   └── migrations/          # DB マイグレーション SQL
├── docker/                  # Dockerfile / entrypoint
├── scripts/
│   └── run_backend.sh       # バックエンド起動スクリプト
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## セットアップ

### 必要条件

- Python 3.11+
- やねうら王エンジンバイナリ（`ENGINE_CMD` で指定）
- Gemini API キー（LLM解説を使う場合）
- Supabase プロジェクト（棋譜保存を使う場合）

### インストール

```bash
# 仮想環境
python -m venv .venv
source .venv/bin/activate

# 依存パッケージ
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .env を編集して各キーを設定
```

### 起動

```bash
# バックエンド起動 (LLM OFF)
USE_LLM=0 bash scripts/run_backend.sh

# バックエンド起動 (LLM ON)
USE_LLM=1 bash scripts/run_backend.sh
```

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/health` | ヘルスチェック |
| POST | `/annotate` | 棋譜一括アノテーション |
| POST | `/api/explain` | 1手解説生成 |
| POST | `/api/games` | 棋譜保存 |
| GET | `/api/games` | 棋譜一覧取得 |

## データモデル

### MoveExplanation

1手ごとの解析・解説情報を格納するモデル。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `ply` | int | 手数 |
| `move` | str | 指し手 (USI形式) |
| `eval_before` | int? | 指す前の評価値 |
| `eval_after` | int? | 指した後の評価値 |
| `eval_delta` | int? | 評価値変化 |
| `move_type` | MoveType? | 手の種類 (attack/defense/both/technique) |
| `position_phase` | Phase? | 局面フェーズ (opening/middle/endgame) |
| `narrative` | str? | LLM生成の解説文 |

### GameReport

棋譜全体のレポート。`MoveExplanation` のリストと転換点情報を含む。

## 開発方針

- `USE_LLM=0` でエンジン解析のみ動作させられる（LLMキー不要）
- 各サービスは独立して実装・テスト可能な設計
- Supabase なしでもローカル動作可能
