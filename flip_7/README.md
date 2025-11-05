# Flip 7 Game Tracker

A comprehensive game tracking and simulation platform for the Flip 7 card game, featuring rich statistics, event logging, and JSON persistence.

## Game Rules Summary

**Objective:** Be the first player to reach 200 points by collecting number cards across multiple rounds.

**Card Types:**
- **Number Cards:** 0-12 (each value N appears N times in deck, except 0 appears once)
- **Modifier Cards:** +2, +4, +6, +8, +10 (bonus points), ×2 (double your number card total)
- **Action Cards:** Freeze, Flip Three, Second Chance

**Key Mechanics:**
- **Flip 7 Bonus:** Get exactly 7 number cards in a round for +15 bonus points
- **Win:** Reach 200 or more total points to win the game
- **Bust:** Getting two cards with the SAME VALUE = ZERO points for that round (unless you have Second Chance)
- **Second Chance:** Saves you from one duplicate - use it to discard a duplicate card
- **Scoring:** `(number cards + bonuses) × multiplier + Flip 7 bonus`

## Environment Setup

### Prerequisites
- Anaconda or Miniconda installed
- Python 3.10+

### Initial Setup

From the project root directory:

```bash
# Source the setup script (this will create and activate the environment)
source flip_7/setup_env.sh
```

This will:
1. Create a conda environment named `pigs-flip7`
2. Install Python 3.10 and required dependencies
3. Install the `flip7` package in development mode
4. Activate the environment

### Manual Setup (Alternative)

If you prefer to set up manually:

```bash
# Create environment
conda env create -f flip_7/environment.yml

# Activate environment
conda activate pigs-flip7

# Install package in development mode
pip install -e .
```

### Activating the Environment Later

```bash
conda activate pigs-flip7
```

### Deactivating

```bash
conda deactivate
```

### Updating the Environment

```bash
conda env update -f flip_7/environment.yml --prune
```

## 🖥️ Using the GUI

### Quick Start

The easiest way to start the Flip 7 GUI:

```bash
# From the project root
./flip_7/launch_gui.sh
```

This will:
1. Activate the `pigs-flip7` environment
2. Start the Streamlit web interface
3. Open your browser to `http://localhost:8501`

### Manual Launch

If you prefer to launch manually:

```bash
# Activate environment
conda activate pigs-flip7

# Launch Streamlit
streamlit run flip_7/gui/app.py
```

### GUI Features

The Flip 7 GUI provides a complete game tracking interface:

#### 🏠 Home Screen
- Quick stats overview
- Recent games list
- Navigation to all features

#### 🎮 New Game
- Add/remove players
- Validation (minimum 2 players)
- Automatic round initialization

#### 🎴 Game Play Interface
- **Player Cards**: Visual display of each player's cards with real-time score calculation
- **Deal Cards**: Interactive card picker with filtering by type
  - Number cards (0-12, organized in rows)
  - Modifier cards (+2, +4, +6, +8, +10, ×2)
  - Action cards (Freeze, Flip Three, Second Chance)
- **Player Actions**:
  - Stay (with validation for Flip Three)
  - Use Second Chance to discard duplicates
- **Status Indicators**: Active, Stayed, Busted, Flip Three status
- **Score Breakdown**: Real-time calculation showing base, bonuses, multiplier, Flip 7
- **Auto-save**: Game saves automatically after each action

#### 📊 Statistics
- **Leaderboard**: Win rates, games won, average scores
- **Historical Stats**: Total games, Flip 7 frequency, bust rates, card distribution
- **Player Details**: Individual performance metrics and game history

#### 📂 Game Browser
- Load saved games (complete or in progress)
- Filter by status
- Sort by date or rounds
- View game details before loading
- Delete unwanted games

### GUI Tips

- **Card Selection**: Click the card type tab, then click the specific card to deal it
- **Score Preview**: See real-time score calculations before players stay
- **Flip 7 Detection**: Interface highlights when a player has exactly 7 number cards
- **Second Chance**: Only available when player has duplicate number cards
- **Auto-save**: All games save automatically - no need to manually save

## Architecture

The Flip 7 tracker follows a three-layer architecture:

```
flip_7/
├── core/           # Game engine and rules
│   ├── deck.py     # Deck creation and management
│   ├── rules.py    # Score calculation and validation
│   └── engine.py   # Game flow controller
├── data/           # Models and persistence
│   ├── models.py   # Card types, GameState, PlayerState, etc.
│   ├── events.py   # Event logging system
│   ├── statistics.py   # Statistics calculation
│   └── persistence.py  # JSON serialization
└── tests/          # Comprehensive test suite
```

## Usage Examples

### Quick Start: Manual Game Logging

```python
from flip_7.core.engine import GameEngine
from flip_7.data.models import NumberCard, ModifierCard, ModifierType
from flip_7.data.persistence import GameRepository

# Create a new game
engine = GameEngine()
game_state = engine.start_new_game(["Alice", "Bob", "Charlie"])

# Start first round
engine.start_new_round()

# Deal cards to Alice
alice_id = game_state.players[0].player_id
engine.deal_card_to_player(alice_id, NumberCard(value=12))
engine.deal_card_to_player(alice_id, NumberCard(value=11))
engine.deal_card_to_player(alice_id, ModifierCard(modifier_type=ModifierType.PLUS_5, value=5))

# Alice stays
engine.player_stay(alice_id)

# ... continue with other players and rounds ...

# Save the game
repo = GameRepository()
repo.save_game(game_state, engine.get_event_logger())
```

### Loading and Analyzing Games

```python
from flip_7.data.persistence import GameRepository
from flip_7.data.statistics import StatisticsCalculator

# Load a saved game
repo = GameRepository()
game_state, event_log = repo.load_game("game-id-here")

# Calculate statistics
stats_calc = StatisticsCalculator()

# Get game statistics
game_stats = stats_calc.calculate_game_stats(game_state)
print(f"Winner: {game_stats.winner_name} ({game_stats.winner_score} points)")
print(f"Total Flip 7s: {game_stats.flip_7_count}")

# Get all games and build leaderboard
all_games = repo.get_all_completed_games()
leaderboard = stats_calc.get_leaderboard(all_games)

for player_stats in leaderboard:
    print(f"{player_stats.player_name}: {player_stats.win_rate:.1f}% win rate")
```

### Score Calculation

```python
from flip_7.core.rules import calculate_score
from flip_7.data.models import NumberCard, ModifierCard, ModifierType

cards = [
    NumberCard(value=12),
    NumberCard(value=11),
    NumberCard(value=10),
    NumberCard(value=9),
    NumberCard(value=9),
    NumberCard(value=9),
    NumberCard(value=9),
    ModifierCard(modifier_type=ModifierType.PLUS_10, value=10),
    ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
]

breakdown = calculate_score(cards)
print(f"Base score: {breakdown.base_score}")
print(f"Bonus points: {breakdown.bonus_points}")
print(f"Multiplier: {breakdown.multiplier}x")
print(f"Flip 7 bonus: {breakdown.flip_7_bonus}")
print(f"Final score: {breakdown.final_score}")
# Output: Final score: 143 = ((12+11+10+9+9+9+9) + 10) * 2 + 15
```

## Running Tests

```bash
# Run all tests
pytest flip_7/tests/ -v

# Run with coverage
pytest flip_7/tests/ --cov=flip_7 --cov-report=term-missing

# Run specific test file
pytest flip_7/tests/test_rules.py -v

# Run specific test
pytest flip_7/tests/test_rules.py::TestScoreCalculation::test_flip_7_bonus -v
```

### Expected Test Coverage

The test suite targets >80% code coverage across:
- Score calculation with all modifier combinations
- Flip 7 detection
- Bust checking
- Game flow and state transitions
- Event logging
- Persistence (save/load)

## Key Features

### ✅ Implemented

- **Streamlit GUI:** Full-featured web interface for game tracking
  - Interactive card picker with visual selection
  - Real-time score calculation and preview
  - Player status indicators (Active, Stayed, Busted, Flip Three)
  - Auto-save functionality
  - Game browser with filtering and sorting
  - Statistics dashboard with leaderboards
- **Complete Data Models:** Cards, Players, Rounds, Games
- **Strict Validation:** Prevents invalid game states
- **Event Sourcing:** Full audit trail of all game actions
- **Score Calculation:** Handles all modifiers, bonuses, and Flip 7
- **JSON Persistence:** Save/load games with full state
- **Rich Statistics:** Win rates, averages, leaderboards, historical analysis
- **Comprehensive Tests:** >80% coverage target
- **Type Safety:** Full type hints throughout
- **Conda Environment:** Isolated environment with easy setup

### 🚧 Future Enhancements

- **Simulation:** Automated gameplay with AI strategies
- **Advanced Analytics:** Charts, graphs, and trend visualizations
- **Multi-game Stats:** Cross-game comparisons and patterns
- **Export Features:** PDF reports, CSV exports

## File Storage

Games are stored in the `flip7_games/` directory (configurable):

```
flip7_games/
├── {game-id-1}/
│   ├── game_state.json   # Complete game state
│   └── events.json       # Event log
├── {game-id-2}/
│   ├── game_state.json
│   └── events.json
└── ...
```

## API Reference

### Core Classes

- **`GameEngine`**: Main game controller
  - `start_new_game(player_names)` - Initialize a game
  - `start_new_round()` - Begin a new round
  - `deal_card_to_player(player_id, card)` - Deal a card
  - `player_stay(player_id)` - Player ends turn
  - `use_second_chance(player_id, card)` - Discard duplicate
  - `end_round()` - Complete the round

- **`GameRepository`**: Game persistence
  - `save_game(game_state, event_logger)` - Save to disk
  - `load_game(game_id)` - Load from disk
  - `list_games()` - Get all game metadata
  - `get_all_completed_games()` - For statistics

- **`StatisticsCalculator`**: Analytics
  - `calculate_game_stats(game_state)` - Single game stats
  - `calculate_player_stats(player_name, games)` - Player performance
  - `get_leaderboard(games)` - Ranked player list
  - `calculate_historical_stats(games)` - Aggregate metrics

### Data Models

- **`GameState`**: Top-level game state
- **`RoundState`**: Single round state
- **`PlayerState`**: Player's current status
- **`Card`** hierarchy: `NumberCard`, `ActionCard`, `ModifierCard`
- **`ScoreBreakdown`**: Detailed score calculation

## Contributing

When adding features:
1. Follow PEP 8 style guidelines
2. Add type hints to all functions
3. Write tests achieving >80% coverage
4. Update this README with new features

## Troubleshooting

### Environment Issues

If you encounter environment problems:

```bash
# Remove and recreate the environment
conda deactivate
conda env remove -n pigs-flip7
source flip_7/setup_env.sh
```

### Import Errors

Ensure you're in the project root and the environment is activated:

```bash
conda activate pigs-flip7
cd /path/to/PIGS
python -c "import flip_7; print('Success!')"
```

### Test Failures

If tests fail after updates:

```bash
# Reinstall package in development mode
pip install -e . --force-reinstall --no-deps
```

## License

See the main project LICENSE file.