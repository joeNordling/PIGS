"""
Data models for Flip 7 card game.

This module defines all core data structures including cards, player states,
round states, and game states. These models are designed to be:
- Immutable (using frozen dataclasses where appropriate)
- Type-safe (full type hints)
- Serializable (to/from JSON)
- Reusable for both manual game tracking and future simulations
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional
from uuid import uuid4


# ============================================================================
# Enumerations
# ============================================================================

class CardType(Enum):
    """Types of cards in Flip 7."""
    NUMBER = "number"
    ACTION = "action"
    MODIFIER = "modifier"


class ActionType(Enum):
    """Types of action cards."""
    FLIP_THREE = "flip_three"
    FREEZE = "freeze"
    SECOND_CHANCE = "second_chance"
    SCORE_MODIFIER = "score_modifier"


class ModifierType(Enum):
    """Types of modifier cards that affect scoring."""
    PLUS_2 = "plus_2"
    PLUS_4 = "plus_4"
    PLUS_6 = "plus_6"
    PLUS_8 = "plus_8"
    PLUS_10 = "plus_10"
    MULTIPLY_2 = "multiply_2"


class PlayerDecision(Enum):
    """Player decisions during their turn."""
    HIT = "hit"
    STAY = "stay"


class RoundEndReason(Enum):
    """Reasons why a round ended."""
    ALL_STAYED = "all_stayed"
    PLAYER_BUSTED = "player_busted"
    DECK_EXHAUSTED = "deck_exhausted"


# ============================================================================
# Card Models
# ============================================================================

@dataclass(frozen=True)
class Card:
    """
    Base class for all cards in Flip 7.

    Attributes:
        card_type: The type of card (NUMBER, ACTION, or MODIFIER)
        card_id: Unique identifier for this specific card instance
    """
    card_type: CardType
    card_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        """Convert card to dictionary for serialization."""
        return {
            "card_type": self.card_type.value,
            "card_id": self.card_id
        }


@dataclass(frozen=True)
class NumberCard(Card):
    """
    Number card with a point value.

    In Flip 7, number cards are the primary scoring mechanism.
    Values are: 12, 11, 10, or 9

    Attributes:
        value: The point value of this number card
    """
    value: int = field(kw_only=True)
    card_type: CardType = field(default=CardType.NUMBER, init=False)

    def to_dict(self) -> dict:
        """Convert card to dictionary for serialization."""
        d = super().to_dict()
        d["value"] = self.value
        return d


@dataclass(frozen=True)
class ActionCard(Card):
    """
    Action card that triggers special effects.

    Action cards modify game flow:
    - FREEZE: Player banks points and ends turn
    - FLIP_THREE: Player must accept next three cards
    - SECOND_CHANCE: Allows discarding a duplicate number card

    Attributes:
        action_type: The type of action this card triggers
    """
    action_type: ActionType = field(kw_only=True)
    card_type: CardType = field(default=CardType.ACTION, init=False)

    def to_dict(self) -> dict:
        """Convert card to dictionary for serialization."""
        d = super().to_dict()
        d["action_type"] = self.action_type.value
        return d


@dataclass(frozen=True)
class ModifierCard(Card):
    """
    Modifier card that affects scoring.

    Modifier cards change how points are calculated:
    - PLUS_X: Add X bonus points to the score
    - MULTIPLY_2: Double the number card points

    Attributes:
        modifier_type: The type of modifier
        value: The numeric value of the modifier (e.g., 2 for PLUS_2)
    """
    modifier_type: ModifierType = field(kw_only=True)
    value: int = field(kw_only=True)
    card_type: CardType = field(default=CardType.MODIFIER, init=False)

    def to_dict(self) -> dict:
        """Convert card to dictionary for serialization."""
        d = super().to_dict()
        d["modifier_type"] = self.modifier_type.value
        d["value"] = self.value
        return d


# ============================================================================
# Score Breakdown
# ============================================================================

@dataclass
class ScoreBreakdown:
    """
    Detailed breakdown of how a score was calculated.

    This provides transparency for score calculation and is useful
    for debugging, statistics, and displaying to users.

    Attributes:
        base_score: Sum of number card values
        bonus_points: Points added from PLUS_X modifiers
        multiplier: Multiplier applied (2 if x2 card present, else 1)
        flip_7_bonus: 15 points if player has 7 number cards
        final_score: The total score for this round
        has_flip_7: Whether the player achieved Flip 7
        number_card_count: How many number cards are in hand
    """
    base_score: int
    bonus_points: int
    multiplier: int
    flip_7_bonus: int
    final_score: int
    has_flip_7: bool
    number_card_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "base_score": self.base_score,
            "bonus_points": self.bonus_points,
            "multiplier": self.multiplier,
            "flip_7_bonus": self.flip_7_bonus,
            "final_score": self.final_score,
            "has_flip_7": self.has_flip_7,
            "number_card_count": self.number_card_count
        }


# ============================================================================
# Player State
# ============================================================================

@dataclass
class PlayerState:
    """
    Tracks the state of a single player during the game.

    This includes their current cards, scores, and status flags.

    Attributes:
        player_id: Unique identifier for this player
        name: Player's display name
        cards_in_hand: Cards currently held (for the current round)
        total_score: Cumulative score across all rounds
        round_score: Score for the current round only
        has_stayed: Whether the player has chosen to stay this round
        is_busted: Whether the player's total score exceeds 200
        has_second_chance: Whether the player currently holds a Second Chance card
        flip_three_active: Whether the player is under Flip Three effect (must take 3 cards)
        flip_three_count: How many cards remaining in Flip Three (0-3)
    """
    player_id: str
    name: str
    cards_in_hand: List[Card] = field(default_factory=list)
    total_score: int = 0
    round_score: int = 0
    has_stayed: bool = False
    is_busted: bool = False
    has_second_chance: bool = False
    flip_three_active: bool = False
    flip_three_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "cards_in_hand": [card.to_dict() for card in self.cards_in_hand],
            "total_score": self.total_score,
            "round_score": self.round_score,
            "has_stayed": self.has_stayed,
            "is_busted": self.is_busted,
            "has_second_chance": self.has_second_chance,
            "flip_three_active": self.flip_three_active,
            "flip_three_count": self.flip_three_count
        }


# ============================================================================
# Round State
# ============================================================================

@dataclass
class RoundState:
    """
    Tracks the state of a single round.

    Attributes:
        round_number: Which round this is (starting from 1)
        dealer_id: ID of the player who is dealer for this round
        player_states: Current state of each player in this round
        cards_remaining_in_deck: How many cards are left to deal
        is_complete: Whether this round has ended
        end_reason: Why the round ended (if complete)
        winner_ids: IDs of players who won this round (if multiple tied)
    """
    round_number: int
    dealer_id: str
    player_states: Dict[str, PlayerState] = field(default_factory=dict)
    cards_remaining_in_deck: int = 0
    is_complete: bool = False
    end_reason: Optional[RoundEndReason] = None
    winner_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "round_number": self.round_number,
            "dealer_id": self.dealer_id,
            "player_states": {pid: ps.to_dict() for pid, ps in self.player_states.items()},
            "cards_remaining_in_deck": self.cards_remaining_in_deck,
            "is_complete": self.is_complete,
            "end_reason": self.end_reason.value if self.end_reason else None,
            "winner_ids": self.winner_ids
        }


# ============================================================================
# Game State
# ============================================================================

@dataclass
class PlayerInfo:
    """
    Basic player information (immutable).

    Attributes:
        player_id: Unique identifier
        name: Player's display name
    """
    player_id: str
    name: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "name": self.name
        }


@dataclass
class GameState:
    """
    Tracks the complete state of a Flip 7 game.

    This is the top-level state object that contains all information
    about the game including players, current round, and history.

    Attributes:
        game_id: Unique identifier for this game
        created_at: When the game was created
        players: List of players in the game (immutable once started)
        current_round: The round currently in progress
        round_history: All completed rounds
        is_complete: Whether the game has ended
        winner_id: ID of the winning player (if complete)
        game_metadata: Optional additional data (e.g., location, notes)
        deck: The current deck of cards (persistent across rounds)
        discard_pile: Cards that have been played (reshuffled when deck is empty)
    """
    game_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    players: List[PlayerInfo] = field(default_factory=list)
    current_round: Optional[RoundState] = None
    round_history: List[RoundState] = field(default_factory=list)
    is_complete: bool = False
    winner_id: Optional[str] = None
    game_metadata: Dict[str, str] = field(default_factory=dict)
    deck: List[Card] = field(default_factory=list)
    discard_pile: List[Card] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "game_id": self.game_id,
            "created_at": self.created_at.isoformat(),
            "players": [p.to_dict() for p in self.players],
            "current_round": self.current_round.to_dict() if self.current_round else None,
            "round_history": [r.to_dict() for r in self.round_history],
            "is_complete": self.is_complete,
            "winner_id": self.winner_id,
            "game_metadata": self.game_metadata,
            "deck": [card.to_dict() for card in self.deck],
            "discard_pile": [card.to_dict() for card in self.discard_pile]
        }