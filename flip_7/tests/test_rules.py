"""
Tests for Flip 7 game rules and scoring logic.
"""

import pytest
from flip_7.data.models import (
    NumberCard, ModifierCard, ActionCard,
    ModifierType, ActionType, PlayerState, RoundState
)
from flip_7.core.rules import (
    calculate_score, check_flip_7, check_bust,
    validate_player_can_stay, validate_player_can_hit,
    validate_second_chance_usage, check_round_end_condition,
    WINNING_SCORE, FLIP_7_BONUS_POINTS
)


class TestScoreCalculation:
    """Test score calculation logic."""

    def test_basic_number_cards(self):
        """Test scoring with only number cards."""
        cards = [
            NumberCard(value=12),
            NumberCard(value=11),
            NumberCard(value=10)
        ]

        breakdown = calculate_score(cards)

        assert breakdown.base_score == 33
        assert breakdown.bonus_points == 0
        assert breakdown.multiplier == 1
        assert breakdown.flip_7_bonus == 0
        assert breakdown.final_score == 33
        assert breakdown.has_flip_7 is False
        assert breakdown.number_card_count == 3

    def test_score_with_bonus_modifier(self):
        """Test scoring with bonus point modifiers."""
        cards = [
            NumberCard(value=12),
            NumberCard(value=11),
            ModifierCard(modifier_type=ModifierType.PLUS_5, value=5)
        ]

        breakdown = calculate_score(cards)

        assert breakdown.base_score == 23
        assert breakdown.bonus_points == 5
        assert breakdown.multiplier == 1
        assert breakdown.final_score == 28  # (23 + 5) * 1

    def test_score_with_multiplier(self):
        """Test scoring with x2 multiplier."""
        cards = [
            NumberCard(value=10),
            NumberCard(value=9),
            ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        ]

        breakdown = calculate_score(cards)

        assert breakdown.base_score == 19
        assert breakdown.multiplier == 2
        assert breakdown.final_score == 38  # 19 * 2

    def test_score_with_multiplier_and_bonus(self):
        """Test scoring with both multiplier and bonus."""
        cards = [
            NumberCard(value=12),
            NumberCard(value=11),
            ModifierCard(modifier_type=ModifierType.PLUS_4, value=4),
            ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        ]

        breakdown = calculate_score(cards)

        # (12 + 11 + 4) * 2 = 54
        assert breakdown.base_score == 23
        assert breakdown.bonus_points == 4
        assert breakdown.multiplier == 2
        assert breakdown.final_score == 54

    def test_flip_7_bonus(self):
        """Test Flip 7 bonus with exactly 7 number cards."""
        cards = [
            NumberCard(value=9),
            NumberCard(value=9),
            NumberCard(value=9),
            NumberCard(value=9),
            NumberCard(value=9),
            NumberCard(value=9),
            NumberCard(value=9)
        ]

        breakdown = calculate_score(cards)

        assert breakdown.number_card_count == 7
        assert breakdown.has_flip_7 is True
        assert breakdown.flip_7_bonus == FLIP_7_BONUS_POINTS
        assert breakdown.final_score == 63 + 15  # (9*7) + 15

    def test_flip_7_with_modifiers(self):
        """Test Flip 7 with modifier cards (should still count as Flip 7)."""
        cards = [
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            ModifierCard(modifier_type=ModifierType.PLUS_10, value=10),
            ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        ]

        breakdown = calculate_score(cards)

        # (70 + 10) * 2 + 15 = 175
        assert breakdown.has_flip_7 is True
        assert breakdown.final_score == 175

    def test_no_flip_7_with_6_cards(self):
        """Test that 6 number cards don't trigger Flip 7."""
        cards = [
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12)
        ]

        breakdown = calculate_score(cards)

        assert breakdown.has_flip_7 is False
        assert breakdown.flip_7_bonus == 0
        assert breakdown.final_score == 72  # 12 * 6

    def test_action_cards_dont_affect_score(self):
        """Test that action cards don't affect score calculation."""
        cards = [
            NumberCard(value=12),
            NumberCard(value=11),
            ActionCard(action_type=ActionType.FREEZE),
            ActionCard(action_type=ActionType.SECOND_CHANCE)
        ]

        breakdown = calculate_score(cards)

        assert breakdown.final_score == 23  # Only number cards count


class TestFlip7Detection:
    """Test Flip 7 detection logic."""

    def test_check_flip_7_true(self):
        """Test Flip 7 detection with 7 number cards."""
        cards = [NumberCard(value=9) for _ in range(7)]
        assert check_flip_7(cards) is True

    def test_check_flip_7_false_less_than_7(self):
        """Test Flip 7 detection with less than 7 cards."""
        cards = [NumberCard(value=12) for _ in range(6)]
        assert check_flip_7(cards) is False

    def test_check_flip_7_false_more_than_7(self):
        """Test Flip 7 detection with more than 7 cards."""
        cards = [NumberCard(value=10) for _ in range(8)]
        assert check_flip_7(cards) is False

    def test_check_flip_7_with_modifiers(self):
        """Test Flip 7 with modifier cards (modifiers don't count)."""
        cards = [
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            NumberCard(value=10),
            ModifierCard(modifier_type=ModifierType.PLUS_5, value=5)
        ]
        assert check_flip_7(cards) is True


class TestBustChecking:
    """Test bust detection logic."""

    def test_check_bust_at_200_is_win(self):
        """Test that reaching 200 is a win, not a bust."""
        assert check_bust(200) is True  # Reaches winning threshold
        assert check_bust(201) is True
        assert check_bust(250) is True

    def test_check_bust_under_200(self):
        """Test that scores under 200 haven't won yet."""
        assert check_bust(199) is False
        assert check_bust(150) is False
        assert check_bust(0) is False

    def test_duplicate_cards_detection(self):
        """Test detection of duplicate number cards."""
        from flip_7.core.rules import check_for_duplicate_cards

        # Test with duplicates
        cards_with_dup = [
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=10)
        ]
        assert check_for_duplicate_cards(cards_with_dup) is True

        # Test without duplicates
        cards_no_dup = [
            NumberCard(value=12),
            NumberCard(value=11),
            NumberCard(value=10)
        ]
        assert check_for_duplicate_cards(cards_no_dup) is False

        # Test with modifiers (modifiers don't cause duplicates)
        cards_with_modifiers = [
            NumberCard(value=12),
            ModifierCard(modifier_type=ModifierType.PLUS_2, value=2),
            ModifierCard(modifier_type=ModifierType.PLUS_2, value=2)
        ]
        assert check_for_duplicate_cards(cards_with_modifiers) is False


class TestValidation:
    """Test game action validation."""

    def test_validate_player_can_stay(self):
        """Test validation for player staying."""
        player = PlayerState(player_id="p1", name="Alice")
        round_state = RoundState(round_number=1, dealer_id="p1")

        # Should be valid initially
        result = validate_player_can_stay(player, round_state)
        assert result.is_valid is True

    def test_validate_player_cannot_stay_twice(self):
        """Test that player can't stay twice."""
        player = PlayerState(player_id="p1", name="Alice", has_stayed=True)
        round_state = RoundState(round_number=1, dealer_id="p1")

        result = validate_player_can_stay(player, round_state)
        assert result.is_valid is False
        assert "already stayed" in result.error_message.lower()

    def test_validate_player_cannot_stay_if_busted(self):
        """Test that busted player can't stay."""
        player = PlayerState(player_id="p1", name="Alice", is_busted=True)
        round_state = RoundState(round_number=1, dealer_id="p1")

        result = validate_player_can_stay(player, round_state)
        assert result.is_valid is False
        assert "busted" in result.error_message.lower()

    def test_validate_player_cannot_stay_during_flip_three(self):
        """Test that player can't stay during Flip Three."""
        player = PlayerState(
            player_id="p1",
            name="Alice",
            flip_three_active=True,
            flip_three_count=2
        )
        round_state = RoundState(round_number=1, dealer_id="p1")

        result = validate_player_can_stay(player, round_state)
        assert result.is_valid is False
        assert "flip three" in result.error_message.lower()

    def test_validate_player_can_hit(self):
        """Test validation for player hitting."""
        player = PlayerState(player_id="p1", name="Alice")
        round_state = RoundState(
            round_number=1,
            dealer_id="p1",
            cards_remaining_in_deck=50
        )

        result = validate_player_can_hit(player, round_state)
        assert result.is_valid is True

    def test_validate_player_cannot_hit_if_stayed(self):
        """Test that player can't hit after staying."""
        player = PlayerState(player_id="p1", name="Alice", has_stayed=True)
        round_state = RoundState(
            round_number=1,
            dealer_id="p1",
            cards_remaining_in_deck=50
        )

        result = validate_player_can_hit(player, round_state)
        assert result.is_valid is False

    def test_validate_player_cannot_hit_if_deck_empty(self):
        """Test that player can't hit with empty deck."""
        player = PlayerState(player_id="p1", name="Alice")
        round_state = RoundState(
            round_number=1,
            dealer_id="p1",
            cards_remaining_in_deck=0
        )

        result = validate_player_can_hit(player, round_state)
        assert result.is_valid is False
        assert "empty" in result.error_message.lower()

    def test_validate_second_chance_usage(self):
        """Test validation for Second Chance usage."""
        card1 = NumberCard(value=12)
        card2 = NumberCard(value=12)  # Duplicate

        player = PlayerState(
            player_id="p1",
            name="Alice",
            has_second_chance=True,
            cards_in_hand=[card1, card2]
        )

        result = validate_second_chance_usage(player, card1)
        assert result.is_valid is True

    def test_validate_second_chance_without_card(self):
        """Test that Second Chance requires the card."""
        card = NumberCard(value=12)

        player = PlayerState(
            player_id="p1",
            name="Alice",
            has_second_chance=False,
            cards_in_hand=[card]
        )

        result = validate_second_chance_usage(player, card)
        assert result.is_valid is False
        assert "does not have" in result.error_message.lower()

    def test_validate_second_chance_no_duplicate(self):
        """Test that Second Chance requires a duplicate."""
        card1 = NumberCard(value=12)
        card2 = NumberCard(value=11)  # Not a duplicate

        player = PlayerState(
            player_id="p1",
            name="Alice",
            has_second_chance=True,
            cards_in_hand=[card1, card2]
        )

        result = validate_second_chance_usage(player, card1)
        assert result.is_valid is False
        assert "duplicate" in result.error_message.lower()


class TestComplexScenarios:
    """Test complex scoring scenarios."""

    def test_maximum_possible_score(self):
        """Test maximum theoretical score in a round."""
        # 7 x 12 cards + multiple PLUS_10 + x2 = very high score
        cards = [
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            NumberCard(value=12),
            ModifierCard(modifier_type=ModifierType.PLUS_10, value=10),
            ModifierCard(modifier_type=ModifierType.PLUS_10, value=10),
            ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        ]

        breakdown = calculate_score(cards)

        # (84 + 20) * 2 + 15 = 223
        assert breakdown.final_score == 223

    def test_empty_hand(self):
        """Test scoring with no cards."""
        cards = []

        breakdown = calculate_score(cards)

        assert breakdown.final_score == 0
        assert breakdown.has_flip_7 is False

    def test_only_modifier_cards(self):
        """Test scoring with only modifier cards (no number cards)."""
        cards = [
            ModifierCard(modifier_type=ModifierType.PLUS_5, value=5),
            ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        ]

        breakdown = calculate_score(cards)

        # (0 + 5) * 2 = 10
        assert breakdown.final_score == 10


class TestRoundEndCondition:
    """Test round end condition checking."""

    def test_round_not_end_when_one_player_busts(self):
        """Test that round does not end when only one player busts."""
        # Create a round with 3 players
        round_state = RoundState(round_number=1, dealer_id="p1")
        round_state.player_states = {
            "p1": PlayerState(player_id="p1", name="Alice", is_busted=True),
            "p2": PlayerState(player_id="p2", name="Bob"),
            "p3": PlayerState(player_id="p3", name="Charlie")
        }
        round_state.cards_remaining_in_deck = 50

        # Round should NOT end (only Alice busted, Bob and Charlie haven't finished)
        assert check_round_end_condition(round_state) is False

    def test_round_ends_when_all_stayed_or_busted(self):
        """Test that round ends when all players have stayed or busted."""
        # Create a round with 3 players
        round_state = RoundState(round_number=1, dealer_id="p1")
        round_state.player_states = {
            "p1": PlayerState(player_id="p1", name="Alice", is_busted=True),
            "p2": PlayerState(player_id="p2", name="Bob", has_stayed=True),
            "p3": PlayerState(player_id="p3", name="Charlie", has_stayed=True)
        }
        round_state.cards_remaining_in_deck = 50

        # Round SHOULD end (all players finished)
        assert check_round_end_condition(round_state) is True

    def test_round_ends_when_all_stayed(self):
        """Test that round ends when all players have stayed."""
        # Create a round with 3 players
        round_state = RoundState(round_number=1, dealer_id="p1")
        round_state.player_states = {
            "p1": PlayerState(player_id="p1", name="Alice", has_stayed=True),
            "p2": PlayerState(player_id="p2", name="Bob", has_stayed=True),
            "p3": PlayerState(player_id="p3", name="Charlie", has_stayed=True)
        }
        round_state.cards_remaining_in_deck = 50

        # Round SHOULD end
        assert check_round_end_condition(round_state) is True

    def test_round_ends_when_deck_exhausted(self):
        """Test that round ends when deck is exhausted."""
        # Create a round with players still active
        round_state = RoundState(round_number=1, dealer_id="p1")
        round_state.player_states = {
            "p1": PlayerState(player_id="p1", name="Alice"),
            "p2": PlayerState(player_id="p2", name="Bob")
        }
        round_state.cards_remaining_in_deck = 0

        # Round SHOULD end (deck exhausted)
        assert check_round_end_condition(round_state) is True

    def test_round_ends_when_all_busted(self):
        """Test that round ends when all players have busted."""
        # Create a round where everyone busted
        round_state = RoundState(round_number=1, dealer_id="p1")
        round_state.player_states = {
            "p1": PlayerState(player_id="p1", name="Alice", is_busted=True),
            "p2": PlayerState(player_id="p2", name="Bob", is_busted=True),
            "p3": PlayerState(player_id="p3", name="Charlie", is_busted=True)
        }
        round_state.cards_remaining_in_deck = 50

        # Round SHOULD end (all players busted)
        assert check_round_end_condition(round_state) is True
