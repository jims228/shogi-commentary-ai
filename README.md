# ShogiStep

An AI system that verbalizes professional-level reasoning behind shogi moves.

## Goal

The goal is to build a system that explains not just what the best move is, but *why* — capturing the intent, causal chains, and key concepts that a professional commentator would identify. This is pursued both as academic research and as the foundation for a shogi learning application.

## Research Question

Can an AI verbalize professional-level shogi reasoning? What techniques are required, and how can explanation quality be defined and measured?

## Current System — Pipeline

The system uses a five-stage pipeline to generate move explanations:

```
KIF input
  → Feature extraction (8-dimensional: king_safety, piece_activity, attack_pressure, phase, move_intent, ...)
  → ML prediction
      ├── FocusPredictor       (F1 = 0.706)
      ├── ImportancePredictor
      └── StyleSelector        (accuracy = 0.974)
  → Prompt construction (ExplanationPlanner)
  → LLM generation (Gemini API, gemini-2.5-flash-lite)
  → ~80-character Japanese move explanation
```

The planner pipeline is activated when `use_planner=true` or `prev_moves` is provided. The legacy single-pass path is preserved for backward compatibility.

## Directory Structure

```
shogi-commentary-ai/
├── backend/
│   ├── ai/
│   │   ├── castle_detector.py      # Castle formation detection
│   │   ├── opening_detector.py     # Opening classification
│   │   └── pv_reason.py            # Principal variation reasoning
│   └── api/
│       ├── main.py                 # FastAPI application entry point
│       ├── engine_state.py         # YaneuraOu engine interface (Stream/Batch)
│       ├── routers/
│       │   ├── explain.py          # /api/explain — single-move commentary
│       │   ├── annotate.py         # /annotate  — batch KIF annotation
│       │   ├── games.py            # /api/games — game record management
│       │   └── analysis.py         # /api/analysis
│       ├── services/
│       │   ├── explanation_planner.py   # Structured intermediate plan builder
│       │   ├── ai_service.py            # LLM prompt dispatch
│       │   ├── position_features.py     # 8-dimensional feature extraction
│       │   ├── board_analyzer.py        # Threats, hanging pieces, castle hints
│       │   ├── focus_predictor.py       # ML: what to focus on
│       │   ├── importance_predictor.py  # ML: move importance score
│       │   ├── ml_trainer.py            # Model training pipeline
│       │   └── bioshogi.py              # bioshogi Ruby service client
│       └── utils/
│           ├── gemini_client.py         # Gemini API configuration
│           └── shogi_explain_core.py    # SFEN / board state parser
├── bioshogi_service/                    # Ruby-based shogi logic service (port 7070)
├── data/
│   ├── annotated/                       # Annotated position dataset
│   ├── models/                          # Trained ML model artifacts
│   ├── human_eval/                      # Human evaluation sets
│   └── experiments/                     # Experiment outputs
├── scripts/
│   ├── run_backend.sh                   # Backend startup script
│   ├── ingest_kifu.py                   # KIF file ingestion pipeline
│   ├── train_models.py                  # ML model training
│   ├── batch_generate_commentary.py     # Batch commentary generation
│   └── compare_legacy_vs_planner.py     # Pipeline comparison tool
├── tools/
│   └── generate_training_data.py        # Training data generation
├── engine/
│   └── engine_server.py                 # USI engine HTTP gateway
├── supabase/
│   └── migrations/                      # Database migration SQL
├── docker/                              # Dockerfile / entrypoint
├── tests/
├── .env.example
└── requirements.txt
```

## Setup & Usage

### Prerequisites

- Python 3.10+
- YaneuraOu engine binary (set via `ENGINE_CMD`)
- Ruby 3.2.2 via rbenv (for the bioshogi service)
- Gemini API key (required for LLM commentary)
- Supabase project (optional, for game record persistence)

### Installation

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and fill in your keys
```

### Running the Backend

```bash
# Start without LLM (engine analysis only)
USE_LLM=0 bash scripts/run_backend.sh

# Start with LLM commentary generation
USE_LLM=1 bash scripts/run_backend.sh
```

The startup script also launches the bioshogi Ruby service on port 7070.

### Running Tests

```bash
python -m pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/annotate` | Batch KIF annotation |
| POST | `/api/explain` | Generate commentary for a single move |
| POST | `/api/games` | Save a game record |
| GET | `/api/games` | List saved game records |

### `/api/explain` — Request Parameters

| Field | Type | Description |
|-------|------|-------------|
| `sfen` | string | Board position in SFEN format |
| `move` | string | Move in USI notation |
| `prev_moves` | string[]? | Prior moves for context (activates planner pipeline) |
| `use_planner` | bool? | Explicitly enable the planner pipeline |

### `MoveExplanation` — Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ply` | int | Move number |
| `move` | str | Move in USI notation |
| `eval_before` | int? | Evaluation score before the move |
| `eval_after` | int? | Evaluation score after the move |
| `eval_delta` | int? | Change in evaluation score |
| `move_type` | MoveType? | Move category (attack / defense / both / technique) |
| `position_phase` | Phase? | Game phase (opening / middle / endgame) |
| `narrative` | str? | LLM-generated explanation text |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10, FastAPI |
| ML | scikit-learn (RandomForest, GradientBoosting, OneVsRest) |
| LLM | Google Gemini API (`gemini-2.5-flash-lite`), `thinking_budget=0` |
| Shogi Engine | YaneuraOu + NNUE via subprocess; bioshogi (Ruby 3.2.2) |
| Database | Supabase (PostgreSQL) |
| Frontend (planned) | React Native / Expo SDK 54 |
