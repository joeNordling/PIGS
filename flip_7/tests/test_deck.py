"""
Tests for Flip 7 deck creation and management.
"""

import pytest
from flip_7.data.models import NumberCard, ActionCard, ModifierCard, ActionType, ModifierType
from flip_7.core.deck import (
    create_deck, shuffle_deck, get_deck_statistics,
    DeckManager, NUMBER_CARD_DISTRIBUTION, ACTION_CARD_COUNTS, MODIFIER_CARD_DISTRIBUTION
)


class TestDeckCreation:
    """Test deck creation logic."""

    def test_create_deck_returns_correct_total_cards(self):
        """Test that deck has the correct total number of cards."""
        deck = create_deck()

        expected_total = (
            sum(NUMBER_CARD_DISTRIBUTION.values()) +
            sum(ACTION_CARD_COUNTS.values()) +
            sum(MODIFIER_CARD_DISTRIBUTION.values())
        )

        assert len(deck) == expected_total

    def test_create_deck_number_cards(self):
        """Test that deck has correct number of each number card."""
        deck = create_deck()

        for value, expected_count in NUMBER_CARD_DISTRIBUTION.items():
            actual_count = sum(
                1 for card in deck
                if isinstance(card, NumberCard) and card.value == value
            )
            assert actual_count == expected_count, f"Expected {expected_count} cards with value {value}, got {actual_count}"

    def test_create_deck_action_cards(self):
        """Test that deck has correct number of each action card."""
        deck = create_deck()

        for action_type, expected_count in ACTION_CARD_COUNTS.items():
            actual_count = sum(
                1 for card in deck
                if isinstance(card, ActionCard) and card.action_type == action_type
            )
            assert actual_count == expected_count

    def test_create_deck_modifier_cards(self):
        """Test that deck has correct number of each modifier card."""
        deck = create_deck()

        for modifier_type, expected_count in MODIFIER_CARD_DISTRIBUTION.items():
            actual_count = sum(
                1 for card in deck
                if isinstance(card, ModifierCard) and card.modifier_type == modifier_type
            )
            assert actual_count == expected_count

    def test_create_deck_card_ids_are_unique(self):
        """Test that all cards have unique IDs."""
        deck = create_deck()

        card_ids = [card.card_id for card in deck]
        assert len(card_ids) == len(set(card_ids)), "Card IDs should be unique"

    def test_create_deck_is_repeatable(self):
        """Test that creating multiple decks gives same distribution."""
        deck1 = create_deck()
        deck2 = create_deck()

        # Should have same number of cards
        assert len(deck1) == len(deck2)

        # Should have same card types (though IDs will differ)
        def get_card_types(deck):
            return sorted([type(card).__name__ for card in deck])

        assert get_card_types(deck1) == get_card_types(deck2)


class TestDeckShuffling:
    """Test deck shuffling logic."""

    def test_shuffle_deck_preserves_size(self):
        """Test that shuffling doesn't change deck size."""
        deck = create_deck()
        original_size = len(deck)

        shuffled = shuffle_deck(deck)

        assert len(shuffled) == original_size

    def test_shuffle_deck_preserves_cards(self):
        """Test that shuffling doesn't add or remove cards."""
        deck = create_deck()

        # Count card types
        original_number_count = sum(1 for c in deck if isinstance(c, NumberCard))
        original_action_count = sum(1 for c in deck if isinstance(c, ActionCard))
        original_modifier_count = sum(1 for c in deck if isinstance(c, ModifierCard))

        shuffled = shuffle_deck(deck)

        shuffled_number_count = sum(1 for c in shuffled if isinstance(c, NumberCard))
        shuffled_action_count = sum(1 for c in shuffled if isinstance(c, ActionCard))
        shuffled_modifier_count = sum(1 for c in shuffled if isinstance(c, ModifierCard))

        assert original_number_count == shuffled_number_count
        assert original_action_count == shuffled_action_count
        assert original_modifier_count == shuffled_modifier_count

    def test_shuffle_deck_with_seed_is_reproducible(self):
        """Test that shuffling with same seed gives same result."""
        deck = create_deck()

        shuffled1 = shuffle_deck(deck, seed=42)
        shuffled2 = shuffle_deck(deck, seed=42)

        # Should be in same order
        for card1, card2 in zip(shuffled1, shuffled2):
            assert type(card1) == type(card2)
            if isinstance(card1, NumberCard):
                assert card1.value == card2.value

    def test_shuffle_deck_actually_shuffles(self):
        """Test that shuffling actually changes card order."""
        deck = create_deck()
        shuffled = shuffle_deck(deck, seed=42)

        # Check that at least some cards are in different positions
        differences = sum(
            1 for orig, shuf in zip(deck, shuffled)
            if orig.card_id != shuf.card_id
        )

        # With 94 cards, we expect most to be in different positions
        assert differences > 40, "Deck should be significantly shuffled"


class TestDeckStatistics:
    """Test deck statistics calculation."""

    def test_get_deck_statistics(self):
        """Test that deck statistics are correct."""
        stats = get_deck_statistics()

        assert stats["total_cards"] == 94  # Based on standard Flip 7 deck
        assert stats["number_cards"] == 79  # 1+1+2+3+4+5+6+7+8+9+10+11+12
        assert stats["action_cards"] == 9   # 3+3+3
        assert stats["modifier_cards"] == 6  # 5 bonus + 1 multiplier

    def test_deck_statistics_average_value(self):
        """Test that average number card value is calculated correctly."""
        stats = get_deck_statistics()

        # Calculate expected average
        total_value = sum(value * count for value, count in NUMBER_CARD_DISTRIBUTION.items())
        total_cards = sum(NUMBER_CARD_DISTRIBUTION.values())
        expected_avg = total_value / total_cards

        assert abs(stats["average_number_value"] - expected_avg) < 0.01


class TestDeckManager:
    """Test DeckManager class."""

    def test_deck_manager_initialization(self):
        """Test that DeckManager initializes correctly."""
        manager = DeckManager(shuffle=False)

        assert manager.cards_remaining() == 94
        assert len(manager.drawn_cards) == 0

    def test_deck_manager_draw_card(self):
        """Test drawing a card from the deck."""
        manager = DeckManager(shuffle=False)

        initial_count = manager.cards_remaining()
        card = manager.draw_card()

        assert card is not None
        assert manager.cards_remaining() == initial_count - 1
        assert len(manager.drawn_cards) == 1
        assert manager.drawn_cards[0] == card

    def test_deck_manager_draw_all_cards(self):
        """Test drawing all cards from the deck."""
        manager = DeckManager(shuffle=False)

        drawn = []
        while manager.cards_remaining() > 0:
            drawn.append(manager.draw_card())

        assert len(drawn) == 94
        assert manager.cards_remaining() == 0

    def test_deck_manager_draw_from_empty_deck(self):
        """Test that drawing from empty deck raises error."""
        manager = DeckManager(shuffle=False)

        # Draw all cards
        while manager.cards_remaining() > 0:
            manager.draw_card()

        # Try to draw one more
        with pytest.raises(ValueError, match="empty deck"):
            manager.draw_card()

    def test_deck_manager_peek_next_card(self):
        """Test peeking at the next card without drawing."""
        manager = DeckManager(shuffle=False)

        next_card = manager.peek_next_card()
        assert manager.cards_remaining() == 94  # Should not change

        # Drawing should get the same card
        drawn_card = manager.draw_card()
        assert drawn_card.card_id == next_card.card_id

    def test_deck_manager_peek_empty_deck(self):
        """Test that peeking at empty deck raises error."""
        manager = DeckManager(shuffle=False)

        # Draw all cards
        while manager.cards_remaining() > 0:
            manager.draw_card()

        with pytest.raises(ValueError, match="empty deck"):
            manager.peek_next_card()

    def test_deck_manager_reset(self):
        """Test resetting the deck."""
        manager = DeckManager(shuffle=False)

        # Draw some cards
        for _ in range(10):
            manager.draw_card()

        assert manager.cards_remaining() == 84
        assert len(manager.drawn_cards) == 10

        # Reset
        manager.reset(shuffle=False)

        assert manager.cards_remaining() == 94
        assert len(manager.drawn_cards) == 0

    def test_deck_manager_shuffle_with_seed(self):
        """Test that DeckManager respects shuffle seed."""
        manager1 = DeckManager(shuffle=True, seed=42)
        manager2 = DeckManager(shuffle=True, seed=42)

        # Should draw same cards in same order
        for _ in range(10):
            card1 = manager1.draw_card()
            card2 = manager2.draw_card()

            assert type(card1) == type(card2)
            if isinstance(card1, NumberCard):
                assert card1.value == card2.value
