"""
Tests for Flip 7 game engine.
"""

import pytest
from flip_7.data.models import (
    NumberCard, ActionCard, ModifierCard,
    ActionType, ModifierType
)
from flip_7.core.engine import GameEngine
from flip_7.data.events import EventType


class TestGameInitialization:
    """Test game initialization."""

    def test_start_new_game(self):
        """Test starting a new game."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob", "Charlie"])

        assert game_state is not None
        assert len(game_state.players) == 3
        assert game_state.players[0].name == "Alice"
        assert game_state.players[1].name == "Bob"
        assert game_state.players[2].name == "Charlie"
        assert game_state.is_complete is False
        assert game_state.current_round is None

    def test_start_game_with_too_few_players(self):
        """Test that game requires at least 2 players."""
        engine = GameEngine()

        with pytest.raises(ValueError, match="at least 2 players"):
            engine.start_new_game(["Alice"])

    def test_start_game_with_duplicate_names(self):
        """Test that player names must be unique."""
        engine = GameEngine()

        with pytest.raises(ValueError, match="unique"):
            engine.start_new_game(["Alice", "Bob", "Alice"])

    def test_start_game_creates_event_logger(self):
        """Test that starting a game creates an event logger."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])

        event_logger = engine.get_event_logger()
        assert event_logger is not None
        assert len(event_logger.events) == 1  # GameStartedEvent

    def test_start_game_event_logged(self):
        """Test that GameStartedEvent is logged."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])

        events = engine.get_event_logger().events
        assert events[0].event_type == EventType.GAME_STARTED
        assert events[0].player_names == ["Alice", "Bob"]


class TestRoundManagement:
    """Test round management."""

    def test_start_new_round(self):
        """Test starting a new round."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob", "Charlie"])

        round_state = engine.start_new_round()

        assert round_state.round_number == 1
        assert round_state.dealer_id in [p.player_id for p in engine.game_state.players]
        assert len(round_state.player_states) == 3
        assert round_state.is_complete is False

    def test_dealer_rotation(self):
        """Test that dealer rotates each round."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob", "Charlie"])

        # Start first round
        round1 = engine.start_new_round()
        dealer1_id = round1.dealer_id

        # End round
        round1.is_complete = True
        game_state.round_history.append(round1)
        game_state.current_round = None

        # Start second round
        round2 = engine.start_new_round()
        dealer2_id = round2.dealer_id

        # Dealers should be different
        assert dealer1_id != dealer2_id

    def test_start_round_without_game(self):
        """Test that starting round requires a game."""
        engine = GameEngine()

        with pytest.raises(ValueError, match="not been started"):
            engine.start_new_round()

    def test_start_round_creates_player_states(self):
        """Test that starting round creates player states."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])

        round_state = engine.start_new_round()

        for player in game_state.players:
            assert player.player_id in round_state.player_states
            ps = round_state.player_states[player.player_id]
            assert ps.name == player.name
            assert ps.total_score == 0
            assert ps.has_stayed is False


class TestCardDealing:
    """Test card dealing logic."""

    def test_deal_card_to_player(self):
        """Test dealing a card to a player."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id
        card = NumberCard(value=12)

        engine.deal_card_to_player(player_id, card)

        player_state = game_state.current_round.player_states[player_id]
        assert len(player_state.cards_in_hand) == 1
        assert isinstance(player_state.cards_in_hand[0], NumberCard)
        assert player_state.cards_in_hand[0].value == card.value

    def test_deal_card_decrements_deck(self):
        """Test that dealing a card decrements deck count."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        initial_count = game_state.current_round.cards_remaining_in_deck
        player_id = game_state.players[0].player_id

        engine.deal_card_to_player(player_id, NumberCard(value=12))

        assert game_state.current_round.cards_remaining_in_deck == initial_count - 1

    def test_deal_card_updates_score(self):
        """Test that dealing cards updates player score."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        engine.deal_card_to_player(player_id, NumberCard(value=12))
        engine.deal_card_to_player(player_id, NumberCard(value=11))

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.round_score == 23

    def test_deal_freeze_card(self):
        """Test that dealing Freeze card ends player's turn."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        # Deal some number cards first
        engine.deal_card_to_player(player_id, NumberCard(value=12))
        engine.deal_card_to_player(player_id, NumberCard(value=11))

        # Deal Freeze card
        engine.deal_card_to_player(player_id, ActionCard(action_type=ActionType.FREEZE))

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.has_stayed is True
        assert player_state.total_score == 23  # Should have banked points

    def test_deal_flip_three_card(self):
        """Test that dealing Flip Three card activates the effect."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        engine.deal_card_to_player(player_id, ActionCard(action_type=ActionType.FLIP_THREE))

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.flip_three_active is True
        assert player_state.flip_three_count == 3

    def test_deal_second_chance_card(self):
        """Test that dealing Second Chance card sets the flag."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        engine.deal_card_to_player(player_id, ActionCard(action_type=ActionType.SECOND_CHANCE))

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.has_second_chance is True


class TestPlayerActions:
    """Test player actions (hit/stay)."""

    def test_player_stay(self):
        """Test player choosing to stay."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        # Deal some cards
        engine.deal_card_to_player(player_id, NumberCard(value=12))
        engine.deal_card_to_player(player_id, NumberCard(value=11))

        # Player stays
        engine.player_stay(player_id)

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.has_stayed is True
        assert player_state.round_score == 23
        assert player_state.total_score == 23

    def test_player_cannot_stay_twice(self):
        """Test that player can't stay twice."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        engine.deal_card_to_player(player_id, NumberCard(value=12))
        engine.player_stay(player_id)

        with pytest.raises(ValueError, match="already stayed"):
            engine.player_stay(player_id)

    def test_use_second_chance(self):
        """Test using Second Chance to discard a duplicate."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        # Deal Second Chance card and two duplicates
        engine.deal_card_to_player(player_id, ActionCard(action_type=ActionType.SECOND_CHANCE))
        engine.deal_card_to_player(player_id, NumberCard(value=12))
        engine.deal_card_to_player(player_id, NumberCard(value=12))

        player_state = game_state.current_round.player_states[player_id]
        initial_card_count = len(player_state.cards_in_hand)

        # Get the actual card from player's hand (not the one we created)
        duplicate_card = next(c for c in player_state.cards_in_hand if isinstance(c, NumberCard))

        # Use Second Chance
        engine.use_second_chance(player_id, duplicate_card)

        # Should have removed both the duplicate and Second Chance card
        assert len(player_state.cards_in_hand) == initial_card_count - 2
        assert player_state.has_second_chance is False


class TestBustDetection:
    """Test bust detection and handling."""

    def test_player_bust_with_duplicates(self):
        """Test that player busts when getting duplicate cards."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id
        player_state = game_state.current_round.player_states[player_id]

        # Deal duplicate cards (two cards with value 12)
        engine.deal_card_to_player(player_id, NumberCard(value=12))
        engine.deal_card_to_player(player_id, NumberCard(value=12))

        # Player should be busted due to duplicates
        assert player_state.is_busted is True
        assert player_state.round_score == 0

    def test_bust_event_logged(self):
        """Test that bust event is logged."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        # Deal duplicate cards to cause a bust
        engine.deal_card_to_player(player_id, NumberCard(value=11))
        engine.deal_card_to_player(player_id, NumberCard(value=11))

        # Check for bust event
        bust_events = engine.get_event_logger().get_events(event_type=EventType.PLAYER_BUSTED)
        assert len(bust_events) > 0

    def test_round_continues_after_single_bust(self):
        """Test that round continues when one player busts but others haven't finished."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob", "Charlie"])
        engine.start_new_round()

        alice_id = game_state.players[0].player_id
        bob_id = game_state.players[1].player_id
        charlie_id = game_state.players[2].player_id

        # Alice busts with duplicate cards
        alice_state = game_state.current_round.player_states[alice_id]
        engine.deal_card_to_player(alice_id, NumberCard(value=10))
        engine.deal_card_to_player(alice_id, NumberCard(value=10))

        # Alice should be busted
        assert alice_state.is_busted is True

        # Round should NOT have ended (Bob and Charlie haven't finished)
        assert game_state.current_round is not None
        assert game_state.current_round.is_complete is False

        # Bob and Charlie can still play
        engine.deal_card_to_player(bob_id, NumberCard(value=10))
        engine.player_stay(bob_id)

        # Round still not complete
        assert game_state.current_round is not None

        # Charlie finishes
        engine.deal_card_to_player(charlie_id, NumberCard(value=9))
        engine.player_stay(charlie_id)

        # NOW the round should end (all players done)
        assert game_state.current_round is None
        assert len(game_state.round_history) == 1
        assert game_state.round_history[0].is_complete is True


class TestRoundEnding:
    """Test round ending logic."""

    def test_end_round(self):
        """Test ending a round."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        # Have both players take cards and stay
        for player in game_state.players:
            engine.deal_card_to_player(player.player_id, NumberCard(value=12))
            engine.player_stay(player.player_id)

        # Round should have ended automatically
        assert game_state.current_round is None
        assert len(game_state.round_history) == 1
        assert game_state.round_history[0].is_complete is True

    def test_round_end_event_logged(self):
        """Test that round end event is logged."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        # Have both players stay
        for player in game_state.players:
            engine.deal_card_to_player(player.player_id, NumberCard(value=12))
            engine.player_stay(player.player_id)

        # Check for round end event
        round_end_events = engine.get_event_logger().get_events(event_type=EventType.ROUND_ENDED)
        assert len(round_end_events) == 1


class TestGameCompletion:
    """Test game completion logic."""

    def test_game_ends_when_player_reaches_200(self):
        """Test that game ends when a player reaches 200."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])

        # Play rounds until someone reaches 200
        # Give Alice 33 points per round (12+11+10), needs ~7 rounds to reach 200

        for round_num in range(10):
            engine.start_new_round()

            # Give Alice high score each round
            alice_id = game_state.players[0].player_id
            engine.deal_card_to_player(alice_id, NumberCard(value=12))
            engine.deal_card_to_player(alice_id, NumberCard(value=11))
            engine.deal_card_to_player(alice_id, NumberCard(value=10))
            # This gives 33 points per round
            engine.player_stay(alice_id)

            # Give Bob lower score
            bob_id = game_state.players[1].player_id
            engine.deal_card_to_player(bob_id, NumberCard(value=9))
            engine.player_stay(bob_id)

            # Check if game is complete
            if game_state.is_complete:
                break

        # Game should be complete (Alice gets 33 per round, reaches 200+ after 7 rounds)
        assert game_state.is_complete is True
        assert game_state.winner_id is not None

    def test_game_end_event_logged(self):
        """Test that game end event is logged when game completes."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])

        # Simulate a quick game - give each player 42 points per round (12+11+10+9)
        for _ in range(10):
            engine.start_new_round()

            for player in game_state.players:
                # Deal cards without creating duplicates
                engine.deal_card_to_player(player.player_id, NumberCard(value=12))
                engine.deal_card_to_player(player.player_id, NumberCard(value=11))
                engine.deal_card_to_player(player.player_id, NumberCard(value=10))
                engine.deal_card_to_player(player.player_id, NumberCard(value=9))
                engine.player_stay(player.player_id)

            if game_state.is_complete:
                break

        # Check for game end event
        if game_state.is_complete:
            game_end_events = engine.get_event_logger().get_events(event_type=EventType.GAME_ENDED)
            assert len(game_end_events) == 1
