#!/usr/bin/env python3
"""
Example script demonstrating Flip 7 game tracking.

This script shows how to:
1. Create a new game
2. Play through a round manually
3. Save the game
4. Calculate statistics

Run with: python flip_7/example_game.py
"""

from flip_7.core.engine import GameEngine
from flip_7.data.models import NumberCard, ModifierCard, ActionCard, ModifierType, ActionType
from flip_7.data.persistence import GameRepository
from flip_7.data.statistics import StatisticsCalculator
from flip_7.core.rules import calculate_score


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 60 + "\n")


def main():
    print_separator()
    print("🎴 Flip 7 Game Tracker - Example Game")
    print_separator()

    # Create a new game
    print("Creating a new game with 3 players...")
    engine = GameEngine()
    game_state = engine.start_new_game(["Alice", "Bob", "Charlie"])
    print(f"✓ Game created: {game_state.game_id}")
    print(f"  Players: {', '.join([p.name for p in game_state.players])}")

    print_separator()
    print("📋 Starting Round 1")
    print_separator()

    # Start first round
    round_state = engine.start_new_round()
    dealer = next(p for p in game_state.players if p.player_id == round_state.dealer_id)
    print(f"Dealer: {dealer.name}")

    # Get player IDs
    alice_id = game_state.players[0].player_id
    bob_id = game_state.players[1].player_id
    charlie_id = game_state.players[2].player_id

    print("\n--- Alice's Turn ---")
    # Alice gets a great hand with Flip 7
    alice_cards = [
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

    for card in alice_cards:
        engine.deal_card_to_player(alice_id, card)

    # Calculate and show Alice's score
    alice_state = game_state.current_round.player_states[alice_id]
    alice_breakdown = calculate_score(alice_state.cards_in_hand)

    print(f"Cards dealt: {len(alice_state.cards_in_hand)}")
    print(f"Number cards: {alice_breakdown.number_card_count}")
    print(f"Base score: {alice_breakdown.base_score}")
    print(f"Bonus points: +{alice_breakdown.bonus_points}")
    print(f"Multiplier: x{alice_breakdown.multiplier}")
    if alice_breakdown.has_flip_7:
        print(f"🎉 FLIP 7! Bonus: +{alice_breakdown.flip_7_bonus}")
    print(f"Round score: {alice_breakdown.final_score}")

    engine.player_stay(alice_id)
    print(f"✓ Alice stays with {alice_state.total_score} points")

    print("\n--- Bob's Turn ---")
    # Bob gets a modest hand
    bob_cards = [
        NumberCard(value=10),
        NumberCard(value=10),
        NumberCard(value=9),
        ModifierCard(modifier_type=ModifierType.PLUS_5, value=5)
    ]

    for card in bob_cards:
        engine.deal_card_to_player(bob_id, card)

    bob_state = game_state.current_round.player_states[bob_id]
    bob_breakdown = calculate_score(bob_state.cards_in_hand)

    print(f"Cards dealt: {len(bob_state.cards_in_hand)}")
    print(f"Round score: {bob_breakdown.final_score}")

    engine.player_stay(bob_id)
    print(f"✓ Bob stays with {bob_state.total_score} points")

    print("\n--- Charlie's Turn ---")
    # Charlie gets Flip Three and must take 3 cards
    charlie_cards = [
        ActionCard(action_type=ActionType.FLIP_THREE),
        NumberCard(value=12),
        NumberCard(value=11),
        NumberCard(value=10)
    ]

    for card in charlie_cards:
        engine.deal_card_to_player(charlie_id, card)

    charlie_state = game_state.current_round.player_states[charlie_id]
    charlie_breakdown = calculate_score(charlie_state.cards_in_hand)

    print(f"⚠️  Charlie drew Flip Three! Must take 3 cards.")
    print(f"Round score: {charlie_breakdown.final_score}")

    engine.player_stay(charlie_id)
    print(f"✓ Charlie stays with {charlie_state.total_score} points")

    print_separator()
    print("📊 Round 1 Results")
    print_separator()

    # Round has ended automatically since all players stayed
    completed_round = game_state.round_history[0]

    # Sort players by score
    round_results = [
        (game_state.players[i].name, completed_round.player_states[game_state.players[i].player_id].round_score)
        for i in range(len(game_state.players))
    ]
    round_results.sort(key=lambda x: x[1], reverse=True)

    for i, (name, score) in enumerate(round_results, 1):
        marker = "👑" if i == 1 else f"{i}."
        print(f"{marker} {name}: {score} points")

    print_separator()
    print("💾 Saving Game")
    print_separator()

    # Save the game
    repo = GameRepository(base_dir="flip7_games")
    repo.save_game(game_state, engine.get_event_logger())
    print(f"✓ Game saved to: flip7_games/{game_state.game_id}/")
    print(f"  - game_state.json")
    print(f"  - events.json")

    print_separator()
    print("📈 Statistics")
    print_separator()

    # Show event statistics
    event_logger = engine.get_event_logger()
    print(f"Total events logged: {len(event_logger.events)}")
    print(f"Cards dealt: {event_logger.get_event_count(EventType.CARD_DEALT) if hasattr(EventType, 'CARD_DEALT') else 'N/A'}")

    # Show game metadata
    metadata = repo.list_games()[0]  # Get the game we just saved
    print(f"\nGame Metadata:")
    print(f"  ID: {metadata.game_id}")
    print(f"  Players: {', '.join(metadata.player_names)}")
    print(f"  Rounds played: {metadata.total_rounds}")
    print(f"  Status: {'Complete' if metadata.is_complete else 'In Progress'}")

    print_separator()
    print("✅ Example Complete!")
    print_separator()
    print("\nNext steps:")
    print("  1. Run more rounds to complete the game")
    print("  2. Load the saved game: repo.load_game('game_id')")
    print("  3. Calculate full statistics after multiple games")
    print("  4. Check out flip_7/README.md for more examples")
    print()


if __name__ == "__main__":
    from flip_7.data.events import EventType
    main()
