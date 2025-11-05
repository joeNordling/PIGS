# Flip 7 Official Rules Summary

## Deck Composition (94 cards total)

### Number Cards (79 cards)
- Values: 0-12
- Distribution: Each value N appears N times in the deck
- Exception: 0 appears only once
- Example: 12 appears 12 times, 5 appears 5 times, 0 appears 1 time

### Modifier Cards (6 cards)
- **Bonus Points:** +2, +4, +6, +8, +10 (1 each) = 5 cards
- **Multiplier:** ×2 (1 card)

### Action Cards (9 cards)
- **Freeze:** 3 cards - Player banks points and must stay immediately
- **Flip Three:** 3 cards - Player must accept the next 3 cards before staying
- **Second Chance:** 3 cards - Allows discarding ONE duplicate to avoid bust

## Objective
Be the first player to reach **200 or more total points** across all rounds.

## Critical Rules

### 💥 BUST CONDITION
**Getting 2 of the SAME number card value = INSTANT BUST**
- Player scores **0 points for that round**
- Example: Having two 12s = BUSTED
- Example: Having two 0s = BUSTED
- **Second Chance saves you:** If you have a Second Chance card, you can discard one duplicate to avoid busting

### 🏆 WIN CONDITION
- First player to reach **200+ total points wins** the game
- This is calculated across ALL rounds combined

### 🎉 FLIP 7 BONUS
- Get exactly **7 number cards** in a single round
- Earn **+15 bonus points**
- Cards can be different values (e.g., 12, 11, 10, 9, 8, 7, 6)

## Scoring Formula

```
Final Score = ((Base Number Cards + Bonus Modifiers) × Multiplier) + Flip 7 Bonus
```

### Example Calculation:
- Number cards: 12, 11, 10, 9, 8, 7, 6 = 63 points (7 cards)
- Modifier: +10 = +10 points
- Modifier: ×2 = doubles the above
- Calculation: (63 + 10) × 2 = 146
- Flip 7 bonus: +15 (because 7 number cards)
- **Final Score: 161 points**

## Action Cards Explained

### ❄️ Freeze (3 in deck)
- Player banks their current score
- Turn ends immediately
- No choice to continue

### 🔄 Flip Three (3 in deck)
- Player **must** accept the next 3 cards
- Cannot stay until all 3 cards are dealt
- After 3 cards, can choose to stay or continue

### 🎯 Second Chance (3 in deck)
- **Most valuable card!**
- Hold it in your hand
- Use it when you draw a duplicate
- Discard the duplicate number card to avoid busting
- Only works once per Second Chance card

## Game Flow

### Round Structure
1. Dealer is chosen (rotates each round)
2. Players take turns drawing cards
3. On each turn, player can:
   - **Hit:** Draw another card
   - **Stay:** End turn and bank current score
4. Round ends when:
   - All players have stayed, OR
   - A player busts, OR
   - Deck runs out

### Turn Actions
- **Hit:** Player chooses to draw a card
- **Stay:** Player banks their round score and adds it to total
- **Bust:** Player gets 0 for the round (duplicate cards)
- **Forced Actions:** Freeze auto-stays, Flip Three must take 3 cards

## Strategy Tips

1. **Watch for duplicates!** This is the #1 way to bust
2. **Second Chance is gold** - Save it for when you really need it
3. **Flip 7 is powerful** - 15 bonus points can swing the game
4. **Balance risk vs reward** - Sometimes staying at a safe score is smarter
5. **Know the deck** - Lower numbers appear less often (0 appears once, 1 appears once)

## Common Mistakes

❌ **Wrong:** "I hit 200 points, I'm busted!"
✅ **Correct:** Hitting 200+ means you WIN!

❌ **Wrong:** "I can stay during Flip Three"
✅ **Correct:** Must take all 3 cards before you can stay

❌ **Wrong:** "Second Chance lets me redraw any card"
✅ **Correct:** Only discards a duplicate to save from bust

❌ **Wrong:** "Freeze is bad"
✅ **Correct:** Freeze banks your points safely - sometimes that's exactly what you want

## Validation in the Tracker

The Flip 7 tracker enforces all rules strictly:
- ✅ Prevents staying during Flip Three
- ✅ Auto-detects duplicate cards and busts
- ✅ Validates Second Chance usage
- ✅ Calculates scores with all modifiers correctly
- ✅ Detects Flip 7 achievements automatically
- ✅ Ends game when someone reaches 200+
