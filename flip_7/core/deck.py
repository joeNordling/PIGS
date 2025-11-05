"""
Deck creation and management for Flip 7.

This module implements the core deck functionality for the Flip 7 card game,
including deck creation with the official card distribution, deck shuffling,
card drawing, and deck state management. It provides both functional and
object-oriented interfaces for deck operations.

The module supports:
- Creating standard Flip 7 decks with the official card distribution
- Shuffling decks with optional seed for reproducible results
- Managing deck state and card drawing through the DeckManager class
- Calculating deck statistics and card distribution information
"""

import random
from typing import List
from flip_7.data.models import (
    Card, NumberCard, ActionCard, ModifierCard,
    ActionType, ModifierType
)


# ============================================================================
# Deck Specification
# ============================================================================

# Number cards distribution in a standard Flip 7 deck.
# The dictionary maps card values (0-12) to their frequency in the deck.
# Each card value appears a number of times equal to its value, except:
# - Value 0 appears once
# - Value 12 appears 12 times
NUMBER_CARD_DISTRIBUTION = {
    12: 12,
    11: 11,  
    10: 10,  
    9: 9,  
    8: 8, 
    7: 7,
    6: 6,
    5: 5,
    4: 4,
    3: 3,
    2: 2,
    1: 1,
    0: 1
}

# Distribution of action cards in the deck.
# Each action type (FLIP_THREE, FREEZE, SECOND_CHANCE) appears 3 times,
# for a total of 9 action cards in the deck.
ACTION_CARD_COUNTS = {
    ActionType.FLIP_THREE: 3,
    ActionType.FREEZE: 3,
    ActionType.SECOND_CHANCE: 3,
}

# Distribution of modifier cards in the deck.
# Includes both additive modifiers (PLUS_X) and multiplicative modifiers (MULTIPLY_2).
# Each modifier type appears once, for a total of 6 modifier cards.
MODIFIER_CARD_DISTRIBUTION = {
    ModifierType.PLUS_2: 1,
    ModifierType.PLUS_4: 1,
    ModifierType.PLUS_6: 1,
    ModifierType.PLUS_8: 1,
    ModifierType.PLUS_10: 1,
    ModifierType.MULTIPLY_2: 1,  # Four x2 multiplier cards
}


# ============================================================================
# Deck Creation
# ============================================================================

def create_deck() -> List[Card]:
    """
    Create a standard Flip 7 deck with all cards.

    Returns:
        A list of Card objects representing a complete, unshuffled deck.
        The deck contains:
        - 79 number cards (values 0-12, each appearing N times where N is its value)
        - 9 action cards (3×Flip Three, 3×Freeze, 3×Second Chance)
        - 6 modifier cards (5×plus cards [+2,+4,+6,+8,+10], 1×multiply×2)
        Total: 94 cards
    """
    deck: List[Card] = []

    # Add number cards
    for value, count in NUMBER_CARD_DISTRIBUTION.items():
        for _ in range(count):
            deck.append(NumberCard(value=value))

    # Add action cards
    for action_type, count in ACTION_CARD_COUNTS.items():
        for _ in range(count):
            deck.append(ActionCard(action_type=action_type))

    # Add modifier cards
    for modifier_type, count in MODIFIER_CARD_DISTRIBUTION.items():
        # Extract the numeric value from the modifier type
        if modifier_type == ModifierType.MULTIPLY_2:
            value = 2
        else:
            # Extract number from PLUS_X enum (e.g., PLUS_2 -> 2)
            value = int(modifier_type.value.split('_')[1])

        for _ in range(count):
            deck.append(ModifierCard(modifier_type=modifier_type, value=value))

    return deck


def shuffle_deck(deck: List[Card], seed: int = None) -> List[Card]:
    """
    Shuffle a deck of cards.

    Args:
        deck: The deck to shuffle (will not be modified)
        seed: Optional random seed for reproducible shuffling (useful for testing)

    Returns:
        A new shuffled deck
    """
    shuffled = deck.copy()
    if seed is not None:
        random.Random(seed).shuffle(shuffled)
    else:
        random.shuffle(shuffled)
    return shuffled


def get_deck_statistics() -> dict:
    """
    Get detailed statistics about a standard Flip 7 deck.

    Returns:
        A dictionary containing:
        - total_cards: Total number of cards in the deck
        - number_cards: Count of number cards
        - action_cards: Count of action cards
        - modifier_cards: Count of modifier cards
        - average_number_value: Mean value of number cards
        - number_distribution: Distribution of number card values
        - action_distribution: Distribution of action card types
        - modifier_distribution: Distribution of modifier card types
    """
    total_number_cards = sum(NUMBER_CARD_DISTRIBUTION.values())
    total_action_cards = sum(ACTION_CARD_COUNTS.values())
    total_modifier_cards = sum(MODIFIER_CARD_DISTRIBUTION.values())
    total_cards = total_number_cards + total_action_cards + total_modifier_cards

    # Calculate average number card value
    avg_value = sum(value * count for value, count in NUMBER_CARD_DISTRIBUTION.items()) / total_number_cards

    return {
        "total_cards": total_cards,
        "number_cards": total_number_cards,
        "action_cards": total_action_cards,
        "modifier_cards": total_modifier_cards,
        "average_number_value": round(avg_value, 2),
        "number_distribution": dict(NUMBER_CARD_DISTRIBUTION),
        "action_distribution": {at.value: count for at, count in ACTION_CARD_COUNTS.items()},
        "modifier_distribution": {mt.value: count for mt, count in MODIFIER_CARD_DISTRIBUTION.items()}
    }


# ============================================================================
# Deck Manager (for future simulation use)
# ============================================================================

class DeckManager:
    """
    Manages a deck for drawing cards during gameplay.

    This class provides stateful deck management with support for:
    - Automatic deck creation and shuffling
    - Card drawing with tracking of drawn cards
    - Peeking at upcoming cards
    - Deck state reset
    - Optional seeded shuffling for reproducible game sequences

    This class is particularly useful for:
    - Game simulations requiring automated card drawing
    - AI/Strategy testing with reproducible card sequences
    - Statistics gathering on game outcomes

    For manual game logging where cards are known in advance,
    cards can be specified directly instead of using this class.

    Attributes:
        deck: List[Card] - The remaining cards in the deck
        drawn_cards: List[Card] - Cards that have been drawn, in order
    """

    def __init__(self, shuffle: bool = True, seed: int = None):
        """
        Initialize a new deck manager.

        Args:
            shuffle: Whether to shuffle the deck on creation
            seed: Optional random seed for reproducible shuffling
        """
        self.deck = create_deck()
        if shuffle:
            self.deck = shuffle_deck(self.deck, seed=seed)
        self.drawn_cards: List[Card] = []

    def draw_card(self) -> Card:
        """
        Draw a card from the top of the deck.

        Returns:
            The drawn card

        Raises:
            ValueError: If the deck is empty
        """
        if not self.deck:
            raise ValueError("Cannot draw from empty deck")

        card = self.deck.pop(0)
        self.drawn_cards.append(card)
        return card

    def cards_remaining(self) -> int:
        """
        Get the number of cards remaining in the deck.

        Returns:
            Number of undrawn cards
        """
        return len(self.deck)

    def peek_next_card(self) -> Card:
        """
        Look at the next card without drawing it.

        Returns:
            The next card in the deck

        Raises:
            ValueError: If the deck is empty
        """
        if not self.deck:
            raise ValueError("Cannot peek at empty deck")
        return self.deck[0]

    def reset(self, shuffle: bool = True, seed: int = None):
        """
        Reset the deck to a full, fresh state.

        Args:
            shuffle: Whether to shuffle after resetting
            seed: Optional random seed for reproducible shuffling
        """
        self.deck = create_deck()
        if shuffle:
            self.deck = shuffle_deck(self.deck, seed=seed)
        self.drawn_cards = []
