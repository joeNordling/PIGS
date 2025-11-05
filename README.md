# PIGS - Project Internet Game Simulator

> A platform for creating simulations and GUIs for stat tracking board/card games.

**PIGS** stands for "Project Internet Game Simulator" - a modular platform where each game is self-contained with its own simulation engine, GUI, and comprehensive data persistence layer.

## 🎯 Project Philosophy

- **One Game = One Directory**: Each game is completely independent
- **Modular Design**: Games don't interfere with each other
- **Rich Statistics**: Track everything with detailed analytics
- **Event Sourcing**: Complete audit trail of all game actions
- **Easy Expansion**: Adding a new game doesn't affect existing ones

## 📦 Current Games

### 🎴 Flip 7 (Fully Implemented)

A card game where players race to 200 points while avoiding duplicate cards.

**Status:** ✅ Complete - Full GUI, statistics, and event logging

**Key Features:**
- Modern Streamlit web interface
- Real-time score calculation
- Duplicate card bust detection
- Auto-save functionality
- Comprehensive statistics and leaderboards
- Event-sourced game history
- Deck persistence and reshuffling

**Quick Start:**
```bash
# Setup (one time)
source flip_7/setup_env.sh

# Launch GUI
./flip_7/launch_gui.sh
```

**Documentation:**
- [Full README](flip_7/README.md) - Complete documentation
- [Quick Start Guide](flip_7/QUICKSTART.md) - 3-minute setup
- [Rules Summary](flip_7/RULES_SUMMARY.md) - Official game rules

**Tech Stack:**
- Python 3.10+
- Streamlit for GUI
- JSON for persistence
- Type-safe data models
- Comprehensive test suite

---

### 🔮 Future Games

- *Add your favorite board/card games here!*
- Each game follows the same three-layer architecture
- Minimal dependencies - maximum reusability

## 🏗️ Architecture

Each game follows a consistent three-layer structure:

```
game_name/
├── core/                   # Game engine & rules
│   ├── deck.py            # Card/piece management
│   ├── rules.py           # Scoring & validation
│   └── engine.py          # Game flow controller
├── data/                   # Models & persistence
│   ├── models.py          # Game state, player state, cards
│   ├── events.py          # Event logging system
│   ├── statistics.py      # Analytics & leaderboards
│   └── persistence.py     # JSON save/load
├── gui/                    # User interface
│   ├── app.py             # Main application
│   └── components/        # UI components
├── tests/                  # Test suite
├── environment.yml         # Conda dependencies
├── setup_env.sh           # Environment setup script
├── launch_gui.sh          # GUI launcher
└── README.md              # Game-specific docs
```

## 🚀 Getting Started

### Prerequisites

- **Anaconda or Miniconda** - [Download here](https://docs.conda.io/en/latest/miniconda.html)
- **Python 3.10+** - Installed via conda
- **Git** - For cloning the repository

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd PIGS

# Navigate to a game (e.g., Flip 7)
cd flip_7

# Setup environment
source setup_env.sh

# Launch the game
./launch_gui.sh
```

Each game has its own isolated conda environment to prevent dependency conflicts.

## 📊 Key Features

### Per-Game Features

✅ **Rich Statistics**
- Player leaderboards
- Win rates and averages
- Historical analysis
- Custom metrics per game

✅ **Event Logging**
- Complete game history
- Replay capability
- Audit trails
- Statistical analysis

✅ **Data Persistence**
- JSON-based storage
- Save/load games
- Browse past games
- Export capabilities (planned)

✅ **Modern GUI**
- Streamlit web interface
- Responsive design
- Real-time updates
- Auto-save functionality

### Platform Features

✅ **Isolated Environments**
- Per-game conda environments
- No dependency conflicts
- Easy version management

✅ **Modular Design**
- Games don't affect each other
- Shared patterns across games
- Easy to add new games

✅ **Type Safety**
- Full type hints
- Clear interfaces
- Self-documenting code

✅ **Testing**
- Comprehensive test suites
- >80% coverage target
- Game logic validation

## 🎮 Adding a New Game

Want to add your favorite game to PIGS? Here's how:

### 1. Create Game Directory

```bash
mkdir -p game_name/{core,data,gui/components,tests}
touch game_name/{core,data,gui,tests}/__init__.py
```

### 2. Setup Environment

Create `game_name/environment.yml`:

```yaml
name: pigs-game_name
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - pip
  - pip:
    - streamlit>=1.28.0
    - pytest>=7.0.0
    - pytest-cov>=4.0.0
    - -e ..  # Install in editable mode
```

### 3. Implement Core Layers

**Core Layer** (`core/`):
- `rules.py` - Game rules, scoring, validation
- `deck.py` or `board.py` - Game pieces management
- `engine.py` - Game flow and state management

**Data Layer** (`data/`):
- `models.py` - Game state, player state, pieces
- `events.py` - Event definitions for logging
- `statistics.py` - Analytics calculations
- `persistence.py` - JSON serialization

**GUI Layer** (`gui/`):
- `app.py` - Main Streamlit application
- `components/` - Reusable UI components

**Tests** (`tests/`):
- Unit tests for rules
- Integration tests for engine
- Coverage >80%

### 4. Create Launcher Scripts

Copy and adapt from `flip_7/`:
- `setup_env.sh` - Environment setup
- `launch_gui.sh` - GUI launcher
- `README.md` - Game documentation

### 5. Update Project Config

Add to `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
include = ["flip_7*", "game_tracker*", "your_game*"]
```

### 6. Document Your Game

Create comprehensive documentation:
- Game rules
- Quick start guide
- API reference
- Examples

## 📁 Repository Structure

```
PIGS/
├── flip_7/                 # Flip 7 game (complete)
│   ├── core/              # Game engine
│   ├── data/              # Models & persistence
│   ├── gui/               # Streamlit interface
│   ├── tests/             # Test suite
│   ├── environment.yml    # Conda environment
│   ├── setup_env.sh       # Setup script
│   ├── launch_gui.sh      # Launcher
│   └── README.md          # Documentation
├── shared/                 # Shared utilities (future)
│   └── (common tools across games)
├── pyproject.toml         # Project configuration
├── LICENSE                # Project license
└── README.md              # This file
```

## 🛠️ Development

### Code Standards

- **Style:** PEP 8
- **Type Hints:** Required for all public APIs
- **Documentation:** Docstrings for all modules, classes, and functions
- **Testing:** >80% coverage for game logic

### Testing

```bash
# Run tests for a specific game
conda activate pigs-flip7
pytest flip_7/tests/ -v

# With coverage
pytest flip_7/tests/ --cov=flip_7 --cov-report=term-missing
```

### Building

```bash
# Build distribution (from project root)
python -m build
```

## 🎯 Design Principles

### 1. **Modularity**
Each game is self-contained. You can delete a game directory without affecting others.

### 2. **Extensibility**
Adding a new game doesn't require changes to existing games or shared infrastructure.

### 3. **Data-Driven**
Rich statistics and game state tracking via JSON persistence. Every action is logged.

### 4. **Layered Architecture**
Clear separation: Core (logic) → Data (models) → GUI (interface)

### 5. **Type Safety**
Full type hints throughout for better IDE support and fewer runtime errors.

### 6. **Test Coverage**
Comprehensive tests ensure game logic is correct and changes don't break existing functionality.

## 📚 Documentation

Each game has its own documentation:

- **README.md** - Complete reference
- **QUICKSTART.md** - Fast setup guide
- **RULES_SUMMARY.md** - Official game rules
- **API Reference** - In code docstrings

Project-level documentation:

- **This README** - Platform overview

## 🤝 Contributing

We welcome contributions! To add a new game:

1. Fork the repository
2. Create a new game directory following the structure above
3. Implement the three layers (core, data, GUI)
4. Add comprehensive tests
5. Document your game
6. Submit a pull request

### Guidelines

- Follow the established architecture pattern
- Maintain >80% test coverage
- Include comprehensive documentation
- Use type hints throughout
- Follow PEP 8 style guide

## 📝 Technical Stack

### Core Technologies

- **Python 3.10+** - Primary language
- **Streamlit** - Modern web interface
- **JSON** - Data persistence
- **pytest** - Testing framework
- **Conda** - Environment management

### Why These Choices?

- **Python:** Easy prototyping, rich ecosystem, great for game logic
- **JSON:** Human-readable, simple, adequate for game state
- **Streamlit:** Beautiful UI with minimal code, perfect for data apps
- **Conda:** Isolated environments prevent dependency conflicts
- **Directory-per-game:** Clear separation, independent versioning

## 🔮 Future Enhancements

### Platform-Level

- [ ] Shared utilities library (after 2-3 games to avoid premature abstraction)
- [ ] Common UI components across games
- [ ] Cross-game analytics
- [ ] Unified statistics dashboard
- [ ] Export to various formats (PDF, CSV, Excel)

### Game-Level

- [ ] AI opponents and simulations
- [ ] Multiplayer support (local/online)
- [ ] Mobile-friendly responsive designs
- [ ] Real-time updates with WebSockets
- [ ] Advanced visualizations and charts
- [ ] Tournament mode
- [ ] Achievement system

## 📊 Current Status

| Game | Core | Data | GUI | Tests | Status |
|------|------|------|-----|-------|--------|
| Flip 7 | ✅ | ✅ | ✅ | ✅ | **Complete** |
| *Your Game* | - | - | - | - | *Add here!* |

## 💡 Example Use Cases

### Track Real Games
Use PIGS to track your physical board/card game sessions:
- Record every move
- Calculate scores automatically
- Build player statistics over time
- Analyze strategies

### Simulate Games
Run thousands of simulated games to:
- Test strategies
- Balance game mechanics
- Find optimal plays
- Generate statistics

### Learn Game Theory
Use PIGS as an educational tool:
- Understand probability
- Analyze decision trees
- Study game balance
- Explore strategies

## 🆘 Getting Help

### For Flip 7
- Check [flip_7/README.md](flip_7/README.md)
- See [flip_7/QUICKSTART.md](flip_7/QUICKSTART.md)
- Review [flip_7/RULES_SUMMARY.md](flip_7/RULES_SUMMARY.md)

### For Development
- Check existing game implementations for patterns
- Review test files for examples

### Issues & Questions
- Open an issue on GitHub
- Check existing documentation
- Review code comments and docstrings

## 📜 License

See [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with Python and Streamlit
- Inspired by the joy of board and card games
- Designed for players, by players

---

**Ready to play?** Pick a game, run the setup script, and start tracking! 🎮

**Want to contribute?** Add your favorite game using the architecture guide above! 🚀
