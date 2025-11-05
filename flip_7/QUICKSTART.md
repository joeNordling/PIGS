# Flip 7 Quick Start Guide

Get started with Flip 7 game tracking in 3 minutes!

## Step 1: Setup Environment (One Time)

```bash
# From the PIGS project root
cd /Users/josephnordling/PIGS

# Run the setup script
source flip_7/setup_env.sh
```

This creates and activates the `pigs-flip7` conda environment with all dependencies.

## Step 2: Launch the GUI

```bash
# Easy way - use the launcher
./flip_7/launch_gui.sh

# OR manually
conda activate pigs-flip7
streamlit run flip_7/gui/app.py
```

The GUI will open in your browser at `http://localhost:8501`

## Step 3: Start Your First Game

### Create a New Game

1. Click **"Start New Game"** on the home screen
2. Add players:
   - Type a name in the input box
   - Click "➕ Add Player"
   - Add at least 2 players
3. Click **"🎯 Start Game"**

### Play a Round

For each player's turn:

1. **Deal Cards:**
   - Click "🎴 Deal Card" for the player
   - Select card type (Number, Modifier, or Action)
   - Click the specific card to deal it
   - Repeat until player is ready to stay

2. **Player Stays:**
   - Click "✋ Stay" when they're done
   - Score is automatically calculated and saved

3. **Special Actions:**
   - **Freeze:** Automatically banks points and ends turn
   - **Flip Three:** Player must take 3 more cards before staying
   - **Second Chance:** Click "🎯 Use Second Chance" to discard a duplicate

### Continue Playing

- After all players stay, click **"▶️ Start Next Round"**
- Game continues until someone reaches 200 points
- Game saves automatically after each action

## Key Features to Try

### 📊 View Statistics

Click "📊 Statistics" on the home screen to see:
- Player leaderboards
- Win rates and averages
- Flip 7 frequency
- Historical game data

### 📂 Load Saved Games

Click "📂 Load Game" to:
- Browse all saved games
- Filter by status (In Progress / Completed)
- Continue unfinished games
- Review completed games

### 🎴 Card Reference

**Number Cards:** 0-12
- Your main scoring cards
- Each value appears N times in deck (where N = value, except 0 appears once)
- ⚠️ **IMPORTANT:** Getting 2 of the same value = BUST (0 points for round!)
- Need exactly 7 number cards for Flip 7 bonus (+15 points)

**Modifier Cards:**
- +2, +4, +6, +8, +10: Add bonus points
- ×2: Double your number card total

**Action Cards:**
- ❄️ Freeze: Bank points and end turn immediately
- 🔄 Flip Three: Must take next 3 cards
- 🎯 Second Chance: **SAVE FROM BUST!** Discard a duplicate to avoid getting 0 points

### Scoring Formula

```
(base number cards + bonus points) × multiplier + Flip 7 bonus
```

**Example:**
- 7 number cards (9+9+9+9+10+11+12) = 69
- +10 modifier = 79
- ×2 multiplier = 158
- Flip 7 bonus = +15
- **Final Score: 173**

### Important Rules

**How to Win:** Be first to reach 200+ total points

**How to Bust:**
- Get two cards with the SAME VALUE → Zero points for the round
- Example: Drawing a 12 when you already have a 12 = BUST!

**Second Chance Saves You:**
- If you have a Second Chance card when you draw a duplicate, you're safe!
- Use it to discard the duplicate and continue playing

## Tips

- **Score Preview:** Watch the score update live as you deal cards
- **Flip 7 Indicator:** Interface highlights when a player has exactly 7 number cards
- **Validation:** Can't stay during Flip Three until all 3 cards are dealt
- **Auto-save:** No need to manually save - game saves after every action
- **Second Chance:** Only appears when player has duplicate number cards

## Troubleshooting

### GUI won't start?
```bash
# Make sure environment is activated
conda activate pigs-flip7

# Install streamlit if missing
pip install streamlit>=1.28.0

# Try launching manually
streamlit run flip_7/gui/app.py
```

### Import errors?
```bash
# Reinstall the package
cd /Users/josephnordling/PIGS
pip install -e .
```

### Environment not found?
```bash
# Re-run the setup
source flip_7/setup_env.sh
```

## What's Next?

- **Play multiple games** to build up statistics
- **Explore the leaderboard** to see player rankings
- **Review game history** in the game browser
- **Try the Python API** for programmatic access (see README.md)

## Need Help?

- Full documentation: `flip_7/README.md`
- Example game: `python flip_7/example_game.py`
- Game rules: Check the sidebar in the GUI (📖 Quick Reference)

---

**Ready to play?** Run `./flip_7/launch_gui.sh` and enjoy! 🎴
