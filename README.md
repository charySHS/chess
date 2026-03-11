# NewChess

Python chess project with a separated `chess_core`, a Pygame UI layer, and early engine / NN infrastructure for Stockfish-supervised training.

## Copyright and license

Copyright (c) 2026 charySHS. All rights reserved.

This repository is proprietary source code and is not released under an open-source license.
You may not copy, modify, distribute, sublicense, or use this code outside the permissions explicitly granted by the copyright holder.

## Current state

- Core board representation and legal move generation in `src/chess_core/`
- Pygame board UI in `src/ui/`
- Start menu, themes, click-to-move, drag-and-drop, promotion picker
- Local human-vs-engine mode using the built-in search engine
- Side-panel engine HUD and move-review badge feedback
- Checkmate / stalemate detection through the core
- Early engine stack in `src/engine/`
- Early value-network training and inference stack in `src/nn/`

## Project layout

```text
main.py                 Root launcher
src/main.py             Direct launcher that also works from IDE run tasks
src/chess_core/         Rules, board, move generation
src/ui/                 Rendering, input, scenes, themes
src/engine/             Search, evaluation, Stockfish bridge
src/nn/                 Encoding, dataset, model, training, inference
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

## Tests

```bash
./.venv/bin/python -m pytest tests/test_core.py tests/test_perft.py
```

## Environment variables

```env
NEWCHESS_THEME=glass
NEWCHESS_STOCKFISH_PATH=stockfish
NEWCHESS_STOCKFISH_DEPTH=12
NEWCHESS_MODEL_PATH=artifacts/value_network.npz
NEWCHESS_TRAINING_DATA=data/stockfish_samples.jsonl
```

## Stockfish / NN direction

Current engine and NN code is foundational:

- `src/engine/stockfish_bridge.py` can analyze FENs and review moves
- `src/nn/dataset.py` can generate / persist Stockfish-supervised samples
- `src/nn/model.py` is a small NumPy value network
- `src/nn/trainer.py` trains the value net from saved samples
- `src/nn/infer.py` ranks legal moves from the trained model
- `src/engine/search.py` now includes iterative deepening, a transposition table, and quiescence search
- `src/engine/evaluator.py` now includes stronger handcrafted evaluation terms

What is not finished yet:

- strong engine strength and time management
- robust move review UX
- production-grade training corpus generation
- online multiplayer and backend wiring

## Git / GitHub

GitHub remote target:

```bash
https://github.com/charySHS/chess
```
