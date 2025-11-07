"""
Base strategy classes for flip_7 simulation framework.

This module defines the abstract BaseStrategy class that all game-playing
strategies must inherit from, plus helper classes for tracking game context.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Counter as CounterType
from collections import Counter

from flip_7.data.models import (
    Card, NumberCard, ActionCard, ModifierCard,
    PlayerState, GameState, ActionType
)


@dataclass
class OpponentInfo:
    """
    Information about an opponent visible to the strategy.

    Attributes:
        player_id: Unique identifier
        name: Player name
        total_score: Cumulative score across all rounds
        round_score: Current round score
        has_stayed: Whether they've stayed this round
        is_busted: Whether they've busted
        card_count: Number of cards in their hand (visible)
    """
    player_id: str
    name: str
    total_score: int
    round_score: int
    has_stayed: bool
    is_busted: bool
    card_count: int


@dataclass
class DeckStatistics:
    """
    Statistics about the deck and visible cards.

    Attributes:
        cards_remaining: Number of cards left in deck
        cards_in_discard: Number of cards in discard pile
        visible_cards: All cards that have been played (visible to all)
        number_card_counts: Count of each number value seen
        total_cards_seen: Total number of cards observed
    """
    cards_remaining: int
    cards_in_discard: int
    visible_cards: List[Card]
    number_card_counts: CounterType[int] = field(default_factory=Counter)
    total_cards_seen: int = 0

    def __post_init__(self):
        """Calculate derived statistics from visible cards."""
        self.total_cards_seen = len(self.visible_cards)
        self.number_card_counts = Counter(
            card.value for card in self.visible_cards
            if isinstance(card, NumberCard)
        )


@dataclass
class StrategyContext:
    """
    Complete context provided to a strategy for decision-making.

    This encapsulates all information available to a player during their turn,
    including their own state, opponent states, and deck statistics.

    Attributes:
        my_player_id: This strategy's player ID
        my_cards: Cards currently in hand
        my_round_score: Current round score
        my_total_score: Cumulative score across all rounds
        my_has_stayed: Whether this player has stayed
        my_is_busted: Whether this player is busted
        my_has_second_chance: Whether holding a Second Chance card
        my_flip_three_active: Whether Flip Three is currently active
        my_flip_three_count: Cards remaining to take (0-3)
        opponents: Information about all opponents
        deck_stats: Statistics about deck and visible cards
        round_number: Current round number
    """
    my_player_id: str
    my_cards: List[Card]
    my_round_score: int
    my_total_score: int
    my_has_stayed: bool
    my_is_busted: bool
    my_has_second_chance: bool
    my_flip_three_active: bool
    my_flip_three_count: int
    opponents: List[OpponentInfo]
    deck_stats: DeckStatistics
    round_number: int

    def count_number_cards(self) -> int:
        """Count how many number cards are in hand."""
        return sum(1 for card in self.my_cards if isinstance(card, NumberCard))

    def get_number_values_in_hand(self) -> List[int]:
        """Get list of number card values in hand."""
        return [card.value for card in self.my_cards if isinstance(card, NumberCard)]

    def has_multiplier(self) -> bool:
        """Check if hand contains a x2 multiplier card."""
        from flip_7.data.models import ModifierType
        return any(
            isinstance(card, ModifierCard) and
            card.modifier_type == ModifierType.MULTIPLY_2
            for card in self.my_cards
        )

    def calculate_duplicate_probability(self) -> Dict[int, float]:
        """
        Calculate probability of drawing a duplicate for each number value in hand.

        Returns:
            Dictionary mapping number values to probability of drawing that value
        """
        if self.deck_stats.cards_remaining == 0:
            return {}

        # Count each number value in hand
        hand_values = Counter(self.get_number_values_in_hand())

        # For each value, calculate probability of drawing it
        probabilities = {}
        for value in hand_values.keys():
            # Total copies of this value in full deck (value 0=1, value 1=1, ..., value 12=12)
            total_in_deck = max(1, value) if value <= 12 else 0

            # How many have we seen (in hand + visible)
            in_hand = hand_values[value]
            seen_elsewhere = self.deck_stats.number_card_counts.get(value, 0)
            total_seen = in_hand + seen_elsewhere

            # Remaining in deck
            remaining = max(0, total_in_deck - total_seen)

            # Probability of drawing this value
            if self.deck_stats.cards_remaining > 0:
                # This is approximate - assumes uniform distribution among unseen cards
                # More accurate calculation would track exact deck composition
                prob = remaining / self.deck_stats.cards_remaining
            else:
                prob = 0.0

            probabilities[value] = prob

        return probabilities

    def get_highest_opponent_score(self) -> int:
        """Get the highest total score among all opponents."""
        if not self.opponents:
            return 0
        return max(opp.total_score for opp in self.opponents)


class BaseStrategy(ABC):
    """
    Abstract base class for all flip_7 game strategies.

    Strategies implement decision-making logic for automated gameplay.
    All strategies must implement:
    - decide_hit_or_stay: Main decision point on each turn
    - decide_second_chance_discard: Which duplicate to discard when busting

    Strategies receive full game context including:
    - Their own hand and scores
    - Opponent states (scores, card counts, stayed/busted status)
    - Visible cards (all cards that have been played)
    - Deck statistics (cards remaining, etc.)
    """

    def __init__(self, name: Optional[str] = None):
        """
        Initialize the strategy.

        Args:
            name: Optional custom name for this strategy instance
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def decide_hit_or_stay(self, context: StrategyContext) -> bool:
        """
        Decide whether to take another card (hit) or bank current score (stay).

        This is the primary decision point for any strategy. Called on each
        player turn when they're eligible to make a choice.

        Args:
            context: Complete game context including hand, scores, opponents, etc.

        Returns:
            True to HIT (take another card), False to STAY (bank score and end turn)

        Note:
            - Cannot stay if flip_three_active (must complete flip three first)
            - This method will not be called if player has already stayed or busted
            - The game engine enforces these constraints
        """
        pass

    @abstractmethod
    def decide_second_chance_discard(
        self,
        context: StrategyContext,
        duplicate_value: int,
        duplicate_cards: List[NumberCard]
    ) -> NumberCard:
        """
        Decide which duplicate card to discard when using Second Chance.

        Called when a player draws a duplicate number card and has a Second Chance
        card available. Must choose which copy of the duplicate to discard.

        Args:
            context: Complete game context
            duplicate_value: The value that was duplicated
            duplicate_cards: List of exactly 2 cards with the duplicate value

        Returns:
            The specific card instance to discard (must be one of duplicate_cards)

        Note:
            - In most cases, both cards are equivalent (same value)
            - Advanced strategies might track card_ids for specific reasoning
            - Default behavior: discard the most recently drawn card (last in list)
        """
        pass

    @abstractmethod
    def decide_flip_three_target(
        self,
        context: StrategyContext,
        possible_targets: List[str]
    ) -> str:
        """
        Decide who should receive the Flip Three effect.

        Called when a player draws a Flip Three action card. The player must choose
        which player (including themselves) should be forced to take 3 more cards.

        Args:
            context: Complete game context
            possible_targets: List of player IDs eligible to receive the effect
                            (only includes active players who haven't stayed)

        Returns:
            The player_id of the target (can be context.my_player_id for self)

        Note:
            - Returned player_id must be in possible_targets list
            - Strategic considerations:
              * Apply to opponent with high score to force them to bust
              * Apply to self if you need more cards and are behind
        """
        pass

    @abstractmethod
    def decide_freeze_target(
        self,
        context: StrategyContext,
        possible_targets: List[str]
    ) -> str:
        """
        Decide who should be frozen.

        Called when a player draws a Freeze action card. The player must choose
        which player (including themselves) should bank their current score and
        end their turn for the round.

        Args:
            context: Complete game context
            possible_targets: List of player IDs eligible to receive the effect
                            (only includes active players who haven't stayed)

        Returns:
            The player_id of the target (can be context.my_player_id for self)

        Note:
            - Returned player_id must be in possible_targets list
            - Strategic considerations:
              * Freeze self if you have a good score and want to bank it
              * Freeze opponent to prevent them from improving their score
        """
        pass

    def on_game_start(self, game_state: GameState, my_player_id: str) -> None:
        """
        Optional callback when a new game starts.

        Strategies can override this to initialize any game-specific state tracking.

        Args:
            game_state: Initial game state
            my_player_id: This strategy's player ID
        """
        pass

    def on_round_start(self, game_state: GameState, my_player_id: str) -> None:
        """
        Optional callback when a new round starts.

        Strategies can override this to reset per-round tracking.

        Args:
            game_state: Game state at round start
            my_player_id: This strategy's player ID
        """
        pass

    def on_round_end(self, game_state: GameState, my_player_id: str) -> None:
        """
        Optional callback when a round ends.

        Strategies can override this to update statistics or learning.

        Args:
            game_state: Final game state for the round
            my_player_id: This strategy's player ID
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
