"""
Event logging system for Flip 7.

This module provides event tracking for all game actions, enabling:
- Complete game history and replay
- Statistical analysis
- Debugging and validation
- Audit trails for manual game logging
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4

from flip_7.data.models import Card, ActionType, RoundEndReason


# ============================================================================
# Event Types
# ============================================================================

class EventType(Enum):
    """Types of events that can occur during a game."""
    GAME_STARTED = "game_started"
    ROUND_STARTED = "round_started"
    CARD_DEALT = "card_dealt"
    PLAYER_HIT = "player_hit"
    PLAYER_STAYED = "player_stayed"
    PLAYER_BUSTED = "player_busted"
    ACTION_CARD_APPLIED = "action_card_applied"
    SECOND_CHANCE_USED = "second_chance_used"
    DECK_RESHUFFLED = "deck_reshuffled"
    ROUND_ENDED = "round_ended"
    GAME_ENDED = "game_ended"


# ============================================================================
# Base Event
# ============================================================================

@dataclass
class GameEvent:
    """
    Base class for all game events.

    Attributes:
        event_id: Unique identifier for this event
        event_type: The type of event
        timestamp: When the event occurred
        game_id: ID of the game this event belongs to
    """
    event_type: EventType
    game_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "game_id": self.game_id
        }


# ============================================================================
# Specific Event Types
# ============================================================================

@dataclass
class GameStartedEvent(GameEvent):
    """
    Event fired when a new game starts.

    Attributes:
        player_names: Names of all players in the game
        player_ids: IDs of all players
    """
    player_names: List[str] = field(default_factory=list)
    player_ids: List[str] = field(default_factory=list)
    event_type: EventType = field(default=EventType.GAME_STARTED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_names"] = self.player_names
        d["player_ids"] = self.player_ids
        return d


@dataclass
class RoundStartedEvent(GameEvent):
    """
    Event fired when a new round starts.

    Attributes:
        round_number: The round number (1-indexed)
        dealer_id: ID of the dealer for this round
        dealer_name: Name of the dealer
    """
    round_number: int = 0
    dealer_id: str = ""
    dealer_name: str = ""
    event_type: EventType = field(default=EventType.ROUND_STARTED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["round_number"] = self.round_number
        d["dealer_id"] = self.dealer_id
        d["dealer_name"] = self.dealer_name
        return d


@dataclass
class CardDealtEvent(GameEvent):
    """
    Event fired when a card is dealt to a player.

    Attributes:
        player_id: ID of the player receiving the card
        player_name: Name of the player
        card: The card that was dealt
        cards_in_hand_count: Total cards in player's hand after this deal
    """
    player_id: str = ""
    player_name: str = ""
    card: Optional[Card] = None
    cards_in_hand_count: int = 0
    event_type: EventType = field(default=EventType.CARD_DEALT, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_id"] = self.player_id
        d["player_name"] = self.player_name
        d["card"] = self.card.to_dict() if self.card else None
        d["cards_in_hand_count"] = self.cards_in_hand_count
        return d


@dataclass
class PlayerHitEvent(GameEvent):
    """
    Event fired when a player chooses to hit (take another card).

    Attributes:
        player_id: ID of the player
        player_name: Name of the player
        round_number: Current round number
    """
    player_id: str = ""
    player_name: str = ""
    round_number: int = 0
    event_type: EventType = field(default=EventType.PLAYER_HIT, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_id"] = self.player_id
        d["player_name"] = self.player_name
        d["round_number"] = self.round_number
        return d


@dataclass
class PlayerStayedEvent(GameEvent):
    """
    Event fired when a player chooses to stay.

    Attributes:
        player_id: ID of the player
        player_name: Name of the player
        round_number: Current round number
        round_score: The player's score for this round
        total_score: The player's total score after this round
        has_flip_7: Whether the player achieved Flip 7
    """
    player_id: str = ""
    player_name: str = ""
    round_number: int = 0
    round_score: int = 0
    total_score: int = 0
    has_flip_7: bool = False
    event_type: EventType = field(default=EventType.PLAYER_STAYED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_id"] = self.player_id
        d["player_name"] = self.player_name
        d["round_number"] = self.round_number
        d["round_score"] = self.round_score
        d["total_score"] = self.total_score
        d["has_flip_7"] = self.has_flip_7
        return d


@dataclass
class PlayerBustedEvent(GameEvent):
    """
    Event fired when a player busts (exceeds 200 total points).

    Attributes:
        player_id: ID of the player
        player_name: Name of the player
        round_number: Current round number
        total_score: The player's total score when they busted
    """
    player_id: str = ""
    player_name: str = ""
    round_number: int = 0
    total_score: int = 0
    event_type: EventType = field(default=EventType.PLAYER_BUSTED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_id"] = self.player_id
        d["player_name"] = self.player_name
        d["round_number"] = self.round_number
        d["total_score"] = self.total_score
        return d


@dataclass
class ActionCardAppliedEvent(GameEvent):
    """
    Event fired when an action card effect is applied.

    Attributes:
        player_id: ID of the player receiving the action
        player_name: Name of the player
        action_type: Type of action card
        effect_description: Human-readable description of what happened
    """
    player_id: str = ""
    player_name: str = ""
    action_type: Optional[ActionType] = None
    effect_description: str = ""
    event_type: EventType = field(default=EventType.ACTION_CARD_APPLIED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_id"] = self.player_id
        d["player_name"] = self.player_name
        d["action_type"] = self.action_type.value if self.action_type else None
        d["effect_description"] = self.effect_description
        return d


@dataclass
class SecondChanceUsedEvent(GameEvent):
    """
    Event fired when a player uses Second Chance card.

    Attributes:
        player_id: ID of the player
        player_name: Name of the player
        discarded_card_value: Value of the number card discarded
        round_number: Current round number
    """
    player_id: str = ""
    player_name: str = ""
    discarded_card_value: int = 0
    round_number: int = 0
    event_type: EventType = field(default=EventType.SECOND_CHANCE_USED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["player_id"] = self.player_id
        d["player_name"] = self.player_name
        d["discarded_card_value"] = self.discarded_card_value
        d["round_number"] = self.round_number
        return d


@dataclass
class DeckReshuffledEvent(GameEvent):
    """
    Event fired when the deck is exhausted and reshuffled.

    Attributes:
        round_number: Current round number when reshuffle occurred
        cards_reshuffled: Number of cards from discard pile shuffled back in
    """
    round_number: int = 0
    cards_reshuffled: int = 0
    event_type: EventType = field(default=EventType.DECK_RESHUFFLED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["round_number"] = self.round_number
        d["cards_reshuffled"] = self.cards_reshuffled
        return d


@dataclass
class RoundEndedEvent(GameEvent):
    """
    Event fired when a round ends.

    Attributes:
        round_number: The round number that ended
        end_reason: Why the round ended
        player_scores: Map of player_id to round score
        winner_ids: IDs of players who won the round
    """
    round_number: int = 0
    end_reason: Optional[RoundEndReason] = None
    player_scores: Dict[str, int] = field(default_factory=dict)
    winner_ids: List[str] = field(default_factory=list)
    event_type: EventType = field(default=EventType.ROUND_ENDED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["round_number"] = self.round_number
        d["end_reason"] = self.end_reason.value if self.end_reason else None
        d["player_scores"] = self.player_scores
        d["winner_ids"] = self.winner_ids
        return d


@dataclass
class GameEndedEvent(GameEvent):
    """
    Event fired when the game ends.

    Attributes:
        winner_id: ID of the winning player
        winner_name: Name of the winning player
        final_scores: Map of player_id to final total score
        total_rounds: Total number of rounds played
    """
    winner_id: str = ""
    winner_name: str = ""
    final_scores: Dict[str, int] = field(default_factory=dict)
    total_rounds: int = 0
    event_type: EventType = field(default=EventType.GAME_ENDED, init=False)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["winner_id"] = self.winner_id
        d["winner_name"] = self.winner_name
        d["final_scores"] = self.final_scores
        d["total_rounds"] = self.total_rounds
        return d


# ============================================================================
# Event Logger
# ============================================================================

class EventLogger:
    """
    Logs and manages game events.

    This class maintains a chronological log of all events in a game,
    and provides methods to query and filter events.

    Attributes:
        events: List of all events in chronological order
        game_id: ID of the game being logged
    """

    def __init__(self, game_id: str):
        """
        Initialize a new event logger.

        Args:
            game_id: ID of the game to log events for
        """
        self.game_id = game_id
        self.events: List[GameEvent] = []

    def log_event(self, event: GameEvent) -> None:
        """
        Log a game event.

        Args:
            event: The event to log
        """
        # Ensure event has the correct game_id
        if event.game_id != self.game_id:
            event = dataclass.replace(event, game_id=self.game_id)

        self.events.append(event)

    def get_events(
        self,
        event_type: Optional[EventType] = None,
        player_id: Optional[str] = None,
        round_number: Optional[int] = None
    ) -> List[GameEvent]:
        """
        Get events matching the specified filters.

        Args:
            event_type: Filter by event type
            player_id: Filter by player ID
            round_number: Filter by round number

        Returns:
            List of matching events in chronological order
        """
        filtered_events = self.events

        if event_type is not None:
            filtered_events = [
                e for e in filtered_events
                if e.event_type == event_type
            ]

        if player_id is not None:
            filtered_events = [
                e for e in filtered_events
                if hasattr(e, 'player_id') and e.player_id == player_id
            ]

        if round_number is not None:
            filtered_events = [
                e for e in filtered_events
                if hasattr(e, 'round_number') and e.round_number == round_number
            ]

        return filtered_events

    def get_event_count(self, event_type: Optional[EventType] = None) -> int:
        """
        Get count of events, optionally filtered by type.

        Args:
            event_type: Optional event type to filter by

        Returns:
            Count of matching events
        """
        if event_type is None:
            return len(self.events)

        return len([e for e in self.events if e.event_type == event_type])

    def get_player_events(self, player_id: str) -> List[GameEvent]:
        """
        Get all events involving a specific player.

        Args:
            player_id: The player's ID

        Returns:
            List of events involving this player
        """
        return self.get_events(player_id=player_id)

    def get_round_events(self, round_number: int) -> List[GameEvent]:
        """
        Get all events for a specific round.

        Args:
            round_number: The round number

        Returns:
            List of events in this round
        """
        return self.get_events(round_number=round_number)

    def to_dict(self) -> dict:
        """
        Convert event log to dictionary for serialization.

        Returns:
            Dictionary with game_id and all events
        """
        return {
            "game_id": self.game_id,
            "events": [event.to_dict() for event in self.events]
        }

    def clear(self) -> None:
        """Clear all logged events."""
        self.events = []
