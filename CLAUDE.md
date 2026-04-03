# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PIGS** (Project Internet Game Simulator) is a modular platform for stat-tracking board/card games. Each game lives in its own directory with an independent engine, GUI, and data layer. Currently one fully implemented game: **Flip 7**.

## Environment Setup

Each game uses its own isolated Conda environment:

```bash
source flip_7/setup_env.sh   # auto-creates and activates pigs-flip7 environment
# OR manually:
conda env create -f flip_7/environment.yml
conda activate pigs-flip7
pip install -e .
```

## Commands

**Run tests:**
```bash
pytest flip_7/tests/ -v
pytest flip_7/tests/ --cov=flip_7 --cov-report=term-missing
```

**Run a single test file:**
```bash
pytest flip_7/tests/test_engine.py -v
```

**Launch GUI:**
```bash
./flip_7/launch_gui.sh
# OR: streamlit run flip_7/gui/app.py
```

**Run simulations/notebooks:**
```bash
jupyter notebook flip_7/notebooks/simulation_analysis.ipynb
```

## Architecture

Each game follows this three-layer pattern:

```
<game>/
├── core/        # Pure game logic — no I/O, no side effects
├── data/        # Models, persistence, events, statistics
├── gui/         # Streamlit web interface consuming core + data
├── simulation/  # Strategy-based simulation runners
└── tests/       # pytest test suite
```

**Flip 7 specifics:**
- `core/engine.py` — game flow controller and state machine
- `core/rules.py` — score calculation, bust detection, win conditions
- `data/models.py` — frozen dataclasses (`GameState`, `PlayerState`, card types)
- `data/events.py` — event log for full audit trail / replay
- `data/persistence.py` — JSON save/load
- `data/statistics.py` — leaderboards and per-player analytics
- `gui/app.py` — Streamlit entry point with routing
- `gui/components/` — one file per UI screen/widget
- `simulation/strategy.py` — abstract base class for strategies

## Key Design Constraints

- **Immutability:** data models use frozen dataclasses; do not make them mutable.
- **Layer separation:** `core/` must not import from `gui/`; `gui/` calls into `core/` and `data/` only.
- **Self-contained games:** adding a new game means adding a new top-level directory — never modifying existing game code.
- **Event sourcing:** all state changes are logged as events; game state can be replayed from the event log.
- **Type hints are required** on all new code per project standards.

## Adding a New Game

Create `<game_name>/` mirroring the `flip_7/` layout: `core/`, `data/`, `gui/`, `simulation/`, `tests/`, `environment.yml`, `setup_env.sh`, `launch_gui.sh`. Each game gets its own Conda environment to avoid dependency conflicts.
