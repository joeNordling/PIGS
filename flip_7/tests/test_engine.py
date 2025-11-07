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

        # Deal Freeze card and apply to self
        freeze_card = ActionCard(action_type=ActionType.FREEZE)
        engine.deal_card_to_player(player_id, freeze_card)
        engine.apply_action_card_effect(freeze_card, player_id, player_id)

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.has_stayed is True
        assert player_state.total_score == 23  # Should have banked points

    def test_deal_flip_three_card(self):
        """Test that dealing Flip Three card activates the effect."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(player_id, flip_three_card)
        engine.apply_action_card_effect(flip_three_card, player_id, player_id)

        player_state = game_state.current_round.player_states[player_id]
        assert player_state.flip_three_active is True
        assert player_state.flip_three_count == 3

    def test_flip_three_requires_exactly_three_more_cards(self):
        """Test that FLIP_THREE card doesn't count itself as one of the 3 cards."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id
        player_state = game_state.current_round.player_states[player_id]

        # Deal FLIP_THREE card and apply to self
        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(player_id, flip_three_card)
        engine.apply_action_card_effect(flip_three_card, player_id, player_id)

        # Should have 1 card in hand (the FLIP_THREE card itself)
        assert len(player_state.cards_in_hand) == 1
        assert player_state.flip_three_active is True
        assert player_state.flip_three_count == 3, "Should require 3 MORE cards after FLIP_THREE"

        # Deal first card - should decrement count
        engine.deal_card_to_player(player_id, NumberCard(value=5))
        assert len(player_state.cards_in_hand) == 2
        assert player_state.flip_three_count == 2, "First card should decrement count to 2"

        # Deal second card - should decrement count
        engine.deal_card_to_player(player_id, NumberCard(value=7))
        assert len(player_state.cards_in_hand) == 3
        assert player_state.flip_three_count == 1, "Second card should decrement count to 1"

        # Deal third card - should complete the flip three effect
        engine.deal_card_to_player(player_id, NumberCard(value=3))
        assert len(player_state.cards_in_hand) == 4, "Should have 4 total: FLIP_THREE + 3 number cards"
        assert player_state.flip_three_active is False, "Effect should be complete after 3 cards"
        assert player_state.flip_three_count == 0, "Count should be 0 after completing effect"

    def test_flip_three_with_action_card_during_effect(self):
        """Test that action cards drawn during FLIP_THREE don't count toward the 3."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id
        player_state = game_state.current_round.player_states[player_id]

        # Deal FLIP_THREE card and apply to self
        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(player_id, flip_three_card)
        engine.apply_action_card_effect(flip_three_card, player_id, player_id)
        assert player_state.flip_three_count == 3

        # Deal an action card (SECOND_CHANCE) - should NOT count toward the 3
        sc_card = ActionCard(action_type=ActionType.SECOND_CHANCE)
        engine.deal_card_to_player(player_id, sc_card)
        engine.apply_action_card_effect(sc_card, player_id, player_id)
        assert player_state.flip_three_count == 3, "Action cards shouldn't count"
        assert len(player_state.cards_in_hand) == 2

        # Now deal 3 number cards
        engine.deal_card_to_player(player_id, NumberCard(value=5))
        assert player_state.flip_three_count == 2

        engine.deal_card_to_player(player_id, NumberCard(value=7))
        assert player_state.flip_three_count == 1

        engine.deal_card_to_player(player_id, NumberCard(value=3))
        assert player_state.flip_three_count == 0
        assert player_state.flip_three_active is False
        assert len(player_state.cards_in_hand) == 5, "Should have FLIP_THREE + SECOND_CHANCE + 3 numbers"

    def test_flip_three_with_modifier_cards(self):
        """Test that modifier cards count toward the 3 cards in FLIP_THREE."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id
        player_state = game_state.current_round.player_states[player_id]

        # Deal FLIP_THREE card and apply to self
        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(player_id, flip_three_card)
        engine.apply_action_card_effect(flip_three_card, player_id, player_id)
        assert player_state.flip_three_count == 3

        # Deal a modifier card - SHOULD count toward the 3
        engine.deal_card_to_player(player_id, ModifierCard(modifier_type=ModifierType.PLUS_2, value=2))
        assert player_state.flip_three_count == 2, "Modifier cards should count"

        # Deal a number card
        engine.deal_card_to_player(player_id, NumberCard(value=5))
        assert player_state.flip_three_count == 1

        # Deal another modifier card
        engine.deal_card_to_player(player_id, ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=0))
        assert player_state.flip_three_count == 0
        assert player_state.flip_three_active is False

    def test_deal_second_chance_card(self):
        """Test that dealing Second Chance card sets the flag."""
        engine = GameEngine()
        game_state = engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        player_id = game_state.players[0].player_id

        sc_card = ActionCard(action_type=ActionType.SECOND_CHANCE)
        engine.deal_card_to_player(player_id, sc_card)
        engine.apply_action_card_effect(sc_card, player_id, player_id)

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

        # Deal Second Chance card and apply it
        sc_card = ActionCard(action_type=ActionType.SECOND_CHANCE)
        engine.deal_card_to_player(player_id, sc_card)
        engine.apply_action_card_effect(sc_card, player_id, player_id)

        # Deal two duplicates
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


class TestActionCardTargeting:
    """Test action card targeting functionality."""

    def test_flip_three_can_target_opponent(self):
        """Test that Flip Three can be applied to an opponent."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id
        bob_id = engine.game_state.players[1].player_id

        # Deal Flip Three to Alice
        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(alice_id, flip_three_card)

        # Alice applies it to Bob
        engine.apply_action_card_effect(flip_three_card, bob_id, alice_id)

        # Check that Bob has Flip Three active, not Alice
        game_state = engine.game_state
        alice_state = game_state.current_round.player_states[alice_id]
        bob_state = game_state.current_round.player_states[bob_id]

        assert not alice_state.flip_three_active
        assert bob_state.flip_three_active
        assert bob_state.flip_three_count == 3

    def test_flip_three_can_target_self(self):
        """Test that Flip Three can be applied to self."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id

        # Deal Flip Three to Alice
        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(alice_id, flip_three_card)

        # Alice applies it to herself
        engine.apply_action_card_effect(flip_three_card, alice_id, alice_id)

        # Check that Alice has Flip Three active
        game_state = engine.game_state
        alice_state = game_state.current_round.player_states[alice_id]

        assert alice_state.flip_three_active
        assert alice_state.flip_three_count == 3

    def test_freeze_can_target_opponent(self):
        """Test that Freeze can be applied to an opponent."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id
        bob_id = engine.game_state.players[1].player_id

        # Give Bob some cards first
        engine.deal_card_to_player(bob_id, NumberCard(value=7))
        engine.deal_card_to_player(bob_id, NumberCard(value=5))

        # Deal Freeze to Alice
        freeze_card = ActionCard(action_type=ActionType.FREEZE)
        engine.deal_card_to_player(alice_id, freeze_card)

        # Alice freezes Bob
        engine.apply_action_card_effect(freeze_card, bob_id, alice_id)

        # Check that Bob is frozen (stayed) and score is banked
        game_state = engine.game_state
        bob_state = game_state.current_round.player_states[bob_id]

        assert bob_state.has_stayed
        assert bob_state.round_score == 12  # 7 + 5
        assert bob_state.total_score == 12

    def test_freeze_can_target_self(self):
        """Test that Freeze can be applied to self."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id

        # Give Alice some cards first
        engine.deal_card_to_player(alice_id, NumberCard(value=10))

        # Deal Freeze to Alice
        freeze_card = ActionCard(action_type=ActionType.FREEZE)
        engine.deal_card_to_player(alice_id, freeze_card)

        # Alice freezes herself
        engine.apply_action_card_effect(freeze_card, alice_id, alice_id)

        # Check that Alice is frozen
        game_state = engine.game_state
        alice_state = game_state.current_round.player_states[alice_id]

        assert alice_state.has_stayed
        assert alice_state.round_score == 10

    def test_second_chance_first_can_be_kept(self):
        """Test that first Second Chance can be kept by the drawer."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id

        # Deal Second Chance to Alice
        sc_card = ActionCard(action_type=ActionType.SECOND_CHANCE)
        engine.deal_card_to_player(alice_id, sc_card)

        # Alice keeps it
        engine.apply_action_card_effect(sc_card, alice_id, alice_id)

        # Check that Alice has Second Chance
        game_state = engine.game_state
        alice_state = game_state.current_round.player_states[alice_id]

        assert alice_state.has_second_chance

    def test_second_chance_second_must_go_to_opponent(self):
        """Test that second Second Chance must be given to opponent."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id
        bob_id = engine.game_state.players[1].player_id

        # Give Alice first Second Chance
        sc_card1 = ActionCard(action_type=ActionType.SECOND_CHANCE)
        engine.deal_card_to_player(alice_id, sc_card1)
        engine.apply_action_card_effect(sc_card1, alice_id, alice_id)

        # Deal second Second Chance to Alice
        sc_card2 = ActionCard(action_type=ActionType.SECOND_CHANCE)
        engine.deal_card_to_player(alice_id, sc_card2)

        # Alice tries to keep second one - should fail
        with pytest.raises(ValueError, match="already has a Second Chance"):
            engine.apply_action_card_effect(sc_card2, alice_id, alice_id)

        # Alice gives it to Bob - should succeed
        engine.apply_action_card_effect(sc_card2, bob_id, alice_id)

        # Check that Bob now has Second Chance
        game_state = engine.game_state
        bob_state = game_state.current_round.player_states[bob_id]

        assert bob_state.has_second_chance

    def test_cannot_target_player_who_has_stayed(self):
        """Test that action cards cannot target players who have stayed."""
        engine = GameEngine()
        engine.start_new_game(["Alice", "Bob"])
        engine.start_new_round()

        alice_id = engine.game_state.players[0].player_id
        bob_id = engine.game_state.players[1].player_id

        # Bob stays
        engine.deal_card_to_player(bob_id, NumberCard(value=7))
        engine.player_stay(bob_id)

        # Alice gets Flip Three
        flip_three_card = ActionCard(action_type=ActionType.FLIP_THREE)
        engine.deal_card_to_player(alice_id, flip_three_card)

        # Alice tries to apply to Bob who has stayed - should fail
        with pytest.raises(ValueError, match="already stayed"):
            engine.apply_action_card_effect(flip_three_card, bob_id, alice_id)
