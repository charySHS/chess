# NewChess

Python chess project with a separated `chess_core`, a polished pygame desktop UI, an experimental Kivy frontend, a stronger in-house engine, and a local engine-lab stack for self-play, benchmarking, rating, and training workflows.

## Copyright and license

Copyright (c) 2026 charySHS. All rights reserved.

This repository is proprietary source code and is not released under an open-source license.
You may not copy, modify, distribute, sublicense, or use this code outside the permissions explicitly granted by the copyright holder.

## Current state

- Core board representation and legal move generation in `src/chess_core/`
- Primary pygame frontend in `src/ui/`
- Experimental Kivy frontend in `src/ui_kivy/`
- Home screen with Apple-inspired liquid-glass styling, update cards, and a cleaner menu flow
- Local pass-and-play and human-vs-engine modes
- Drag-and-drop, click-to-move, promotion picker, undo, board flip, theme switching
- In-game move history, engine HUD, captures panel, move animations, transition polish, and audio alerts
- Built-in engine with iterative deepening, alpha-beta / PVS search, quiescence search, null-move pruning, LMR, killer/history ordering, aspiration windows, Zobrist hashing, and a transposition table
- Optional Stockfish-backed move review when a local binary is available
- Early value-network training and inference stack in `src/nn/`
- Local engine-lab tooling for snapshots, rating runs, self-play sample generation, background training loops, and a desktop dashboard

## Project layout

```text
main.py                 Root launcher
src/main.py             Direct launcher that also works from IDE run tasks
src/chess_core/         Rules, board, move generation
src/ui/                 Rendering, input, scenes, themes
src/ui_kivy/            Experimental alternate Kivy frontend
src/engine/             Search, evaluation, Stockfish bridge, lab tooling
src/nn/                 Encoding, dataset, model, training, inference
scripts/                Benchmarks, engine lab runners, training utilities
tests/                  Core correctness tests
```

## Requirements

- Python 3.14 in the project `.venv`
- packages from `requirements.txt`
- Optional: a local `stockfish` binary on your `PATH`, or set `NEWCHESS_STOCKFISH_PATH`

## Setup

Create or reuse the local virtual environment, then install the runtime packages:

```bash
uv venv .venv
UV_CACHE_DIR=$(pwd)/.uv-cache uv pip install --python ./.venv/bin/python -r requirements.txt
```

The repo includes:

- `.env.example` as the committed template
- `.env` for local development

`src/config.py` reads `.env` automatically on import.

## Running the app

Preferred entry point:

```bash
./.venv/bin/python main.py
```

Direct IDE-style entry point also works:

```bash
./.venv/bin/python src/main.py
```

Backend selection:

- Default frontend: `pygame`
- Optional frontend: `kivy`

Example:

```bash
NEWCHESS_UI_BACKEND=kivy ./.venv/bin/python main.py
```

## Engine lab and training apps

Desktop training dashboard:

```bash
./.venv/bin/python scripts/engine_lab_app.py
```

CLI lab cycle:

```bash
./.venv/bin/python scripts/engine_lab.py \
  --depth 2 \
  --rating-games 8 \
  --selfplay-games 12 \
  --max-plies 80 \
  --training-data data/selfplay_baseline_v1.jsonl
```

Background runner for long training loops:

```bash
./.venv/bin/python scripts/engine_background_runner.py start \
  --depth 2 \
  --rating-games 4 \
  --selfplay-games 12 \
  --max-plies 80 \
  --cycles 0 \
  --sleep-seconds 10 \
  --snapshot-interval 5 \
  --train-model
```

Check runner status:

```bash
./.venv/bin/python scripts/engine_background_runner.py status
```

Stop the runner:

```bash
./.venv/bin/python scripts/engine_background_runner.py stop
```

## Controls

- `Left mouse`: click-to-select, click-to-place, or drag-to-move
- `Esc`: quit
- `M`: return to menu
- `R`: reset
- `U`: undo
- `F`: flip board
- `T`: change theme
- Promotion chooser: click a piece or press `Q`, `R`, `B`, `N`
- Menu options:
  - `Play Local Game`
  - `Play vs Engine`

## Review and engine notes

- The built-in engine is used for gameplay in local engine games.
- Engine search now runs off the main UI thread for smoother gameplay.
- Move review can use Stockfish if `NEWCHESS_STOCKFISH_PATH` points to a working binary.
- If Stockfish is not installed, review falls back to the internal engine and is therefore less authoritative.
- Review labels were tightened, but fallback review should still be treated as approximate.

## Engine notes

Current internal-engine features include:

- incremental `make_move` / `undo_move` search
- Zobrist-backed repetition tracking and transposition-table keys
- principal variation search
- aspiration windows
- null-move pruning
- late move reductions
- killer and history move ordering
- quiescence search with capture filtering
- handcrafted evaluation with piece-square tables, mobility, pawn structure, passed pawns, rook-file bonuses, king safety, bishop pair, and endgame king activity
- local benchmarking and snapshot-vs-current gauntlet tooling

## Tests

```bash
./.venv/bin/python -m pytest tests/test_core.py tests/test_movegen.py tests/test_engine.py tests/test_game_features.py tests/test_profiles.py tests/test_lab.py tests/test_background_runner.py
```

## Environment variables

```env
NEWCHESS_THEME=glass
NEWCHESS_UI_BACKEND=pygame
NEWCHESS_STOCKFISH_PATH=stockfish
NEWCHESS_STOCKFISH_DEPTH=12
NEWCHESS_MODEL_PATH=artifacts/value_network.npz
NEWCHESS_TRAINING_DATA=data/selfplay_baseline_v1.jsonl
```

## Benchmarking and snapshots

Search benchmark:

```bash
./.venv/bin/python scripts/benchmark_search.py --depth 3
```

Save a frozen engine snapshot profile:

```bash
./.venv/bin/python scripts/save_engine_snapshot.py
```

Rate current engine against a frozen snapshot:

```bash
./.venv/bin/python scripts/rate_engine.py --depth 2 --games 8 --max-plies 80
```

Generate self-play samples against the snapshot baseline:

```bash
./.venv/bin/python scripts/generate_selfplay_samples.py --games 8 --depth 2 --max-plies 80
```

## Stockfish / NN direction

Current engine and NN code is functional and now supports a local self-improvement loop:

- `src/engine/stockfish_bridge.py` can analyze FENs and review moves
- `src/nn/dataset.py` can persist self-play or Stockfish-supervised samples
- `src/nn/model.py` is a small NumPy value network
- `src/nn/trainer.py` trains the value net from saved samples
- `src/nn/infer.py` ranks legal moves from the trained model
- `src/engine/profile.py` defines snapshotable search/eval profiles
- `src/engine/lab.py` runs rating, self-play, and training cycles
- `src/engine/lab_app.py` provides a local desktop dashboard for visualization and control
- `src/engine/background_runner.py` supports unattended long-running training loops

What is not finished yet:

- stronger specialized move generation and deeper engine tuning
- stronger time management
- authoritative review without Stockfish installed
- full Kivy frontend parity
- production-grade value / policy training pipeline
- online multiplayer and backend wiring

## Git / GitHub

GitHub remote target:

```bash
https://github.com/charySHS/chess
```
