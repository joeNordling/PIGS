"""
JSON persistence layer for Flip 7.

This module handles serialization and deserialization of game states
and events to/from JSON files for persistent storage.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from flip_7.data.models import (
    Card, NumberCard, ActionCard, ModifierCard,
    PlayerState, RoundState, GameState, PlayerInfo,
    CardType, ActionType, ModifierType, RoundEndReason
)
from flip_7.data.events import (
    EventLogger, GameEvent, EventType,
    GameStartedEvent, RoundStartedEvent, CardDealtEvent,
    PlayerHitEvent, PlayerStayedEvent, PlayerBustedEvent,
    ActionCardAppliedEvent, SecondChanceUsedEvent, DeckReshuffledEvent,
    RoundEndedEvent, GameEndedEvent
)


# ============================================================================
# Card Serialization
# ============================================================================

def serialize_card(card: Card) -> dict:
    """
    Serialize a card to a dictionary.

    Args:
        card: The card to serialize

    Returns:
        Dictionary representation of the card
    """
    return card.to_dict()


def deserialize_card(data: dict) -> Card:
    """
    Deserialize a card from a dictionary.

    Args:
        data: Dictionary representation of a card

    Returns:
        The deserialized Card object
    """
    card_type = CardType(data["card_type"])
    card_id = data["card_id"]

    if card_type == CardType.NUMBER:
        return NumberCard(value=data["value"], card_id=card_id)
    elif card_type == CardType.ACTION:
        return ActionCard(
            action_type=ActionType(data["action_type"]),
            card_id=card_id
        )
    elif card_type == CardType.MODIFIER:
        return ModifierCard(
            modifier_type=ModifierType(data["modifier_type"]),
            value=data["value"],
            card_id=card_id
        )
    else:
        raise ValueError(f"Unknown card type: {card_type}")


# ============================================================================
# Game State Serialization
# ============================================================================

class GameStateSerializer:
    """Handles serialization and deserialization of GameState objects."""

    @staticmethod
    def serialize(game_state: GameState) -> dict:
        """
        Serialize a GameState to a dictionary.

        Args:
            game_state: The game state to serialize

        Returns:
            Dictionary representation
        """
        return game_state.to_dict()

    @staticmethod
    def deserialize(data: dict) -> GameState:
        """
        Deserialize a GameState from a dictionary.

        Args:
            data: Dictionary representation of game state

        Returns:
            The deserialized GameState object
        """
        # Deserialize players
        players = [
            PlayerInfo(
                player_id=p["player_id"],
                name=p["name"]
            )
            for p in data["players"]
        ]

        # Deserialize round history
        round_history = [
            GameStateSerializer._deserialize_round(r)
            for r in data["round_history"]
        ]

        # Deserialize current round if exists
        current_round = None
        if data.get("current_round"):
            current_round = GameStateSerializer._deserialize_round(data["current_round"])

        # Deserialize deck and discard pile
        deck = [deserialize_card(c) for c in data.get("deck", [])]
        discard_pile = [deserialize_card(c) for c in data.get("discard_pile", [])]

        # Create game state
        return GameState(
            game_id=data["game_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            players=players,
            current_round=current_round,
            round_history=round_history,
            is_complete=data["is_complete"],
            winner_id=data.get("winner_id"),
            game_metadata=data.get("game_metadata", {}),
            deck=deck,
            discard_pile=discard_pile
        )

    @staticmethod
    def _deserialize_round(data: dict) -> RoundState:
        """Deserialize a RoundState from dictionary."""
        # Deserialize player states
        player_states = {
            pid: GameStateSerializer._deserialize_player_state(ps)
            for pid, ps in data["player_states"].items()
        }

        return RoundState(
            round_number=data["round_number"],
            dealer_id=data["dealer_id"],
            player_states=player_states,
            cards_remaining_in_deck=data["cards_remaining_in_deck"],
            is_complete=data["is_complete"],
            end_reason=RoundEndReason(data["end_reason"]) if data.get("end_reason") else None,
            winner_ids=data.get("winner_ids", [])
        )

    @staticmethod
    def _deserialize_player_state(data: dict) -> PlayerState:
        """Deserialize a PlayerState from dictionary."""
        cards_in_hand = [
            deserialize_card(c) for c in data["cards_in_hand"]
        ]

        return PlayerState(
            player_id=data["player_id"],
            name=data["name"],
            cards_in_hand=cards_in_hand,
            total_score=data["total_score"],
            round_score=data["round_score"],
            has_stayed=data["has_stayed"],
            is_busted=data["is_busted"],
            has_second_chance=data["has_second_chance"],
            flip_three_active=data["flip_three_active"],
            flip_three_count=data["flip_three_count"]
        )

    @staticmethod
    def save_to_file(game_state: GameState, filepath: Path) -> None:
        """
        Save a GameState to a JSON file.

        Args:
            game_state: The game state to save
            filepath: Path to save the file
        """
        data = GameStateSerializer.serialize(game_state)

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_from_file(filepath: Path) -> GameState:
        """
        Load a GameState from a JSON file.

        Args:
            filepath: Path to the file

        Returns:
            The loaded GameState
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        return GameStateSerializer.deserialize(data)


# ============================================================================
# Event Log Serialization
# ============================================================================

class EventLogSerializer:
    """Handles serialization and deserialization of event logs."""

    @staticmethod
    def serialize(event_logger: EventLogger) -> dict:
        """
        Serialize an EventLogger to a dictionary.

        Args:
            event_logger: The event logger to serialize

        Returns:
            Dictionary representation
        """
        return event_logger.to_dict()

    @staticmethod
    def deserialize(data: dict) -> EventLogger:
        """
        Deserialize an EventLogger from a dictionary.

        Args:
            data: Dictionary representation

        Returns:
            The deserialized EventLogger
        """
        event_logger = EventLogger(game_id=data["game_id"])

        for event_data in data["events"]:
            event = EventLogSerializer._deserialize_event(event_data)
            event_logger.events.append(event)

        return event_logger

    @staticmethod
    def _deserialize_event(data: dict) -> GameEvent:
        """Deserialize a single event from dictionary."""
        event_type = EventType(data["event_type"])
        game_id = data["game_id"]
        timestamp = datetime.fromisoformat(data["timestamp"])
        event_id = data["event_id"]

        # Create the appropriate event type
        if event_type == EventType.GAME_STARTED:
            return GameStartedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_names=data["player_names"],
                player_ids=data["player_ids"]
            )
        elif event_type == EventType.ROUND_STARTED:
            return RoundStartedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                round_number=data["round_number"],
                dealer_id=data["dealer_id"],
                dealer_name=data["dealer_name"]
            )
        elif event_type == EventType.CARD_DEALT:
            card = deserialize_card(data["card"]) if data["card"] else None
            return CardDealtEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_id=data["player_id"],
                player_name=data["player_name"],
                card=card,
                cards_in_hand_count=data["cards_in_hand_count"]
            )
        elif event_type == EventType.PLAYER_HIT:
            return PlayerHitEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_id=data["player_id"],
                player_name=data["player_name"],
                round_number=data["round_number"]
            )
        elif event_type == EventType.PLAYER_STAYED:
            return PlayerStayedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_id=data["player_id"],
                player_name=data["player_name"],
                round_number=data["round_number"],
                round_score=data["round_score"],
                total_score=data["total_score"],
                has_flip_7=data["has_flip_7"]
            )
        elif event_type == EventType.PLAYER_BUSTED:
            return PlayerBustedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_id=data["player_id"],
                player_name=data["player_name"],
                round_number=data["round_number"],
                total_score=data["total_score"]
            )
        elif event_type == EventType.ACTION_CARD_APPLIED:
            action_type = ActionType(data["action_type"]) if data["action_type"] else None
            return ActionCardAppliedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_id=data["player_id"],
                player_name=data["player_name"],
                action_type=action_type,
                effect_description=data["effect_description"]
            )
        elif event_type == EventType.SECOND_CHANCE_USED:
            return SecondChanceUsedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                player_id=data["player_id"],
                player_name=data["player_name"],
                discarded_card_value=data["discarded_card_value"],
                round_number=data["round_number"]
            )
        elif event_type == EventType.DECK_RESHUFFLED:
            return DeckReshuffledEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                round_number=data["round_number"],
                cards_reshuffled=data["cards_reshuffled"]
            )
        elif event_type == EventType.ROUND_ENDED:
            end_reason = RoundEndReason(data["end_reason"]) if data["end_reason"] else None
            return RoundEndedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                round_number=data["round_number"],
                end_reason=end_reason,
                player_scores=data["player_scores"],
                winner_ids=data["winner_ids"]
            )
        elif event_type == EventType.GAME_ENDED:
            return GameEndedEvent(
                game_id=game_id,
                timestamp=timestamp,
                event_id=event_id,
                winner_id=data["winner_id"],
                winner_name=data["winner_name"],
                final_scores=data["final_scores"],
                total_rounds=data["total_rounds"]
            )
        else:
            raise ValueError(f"Unknown event type: {event_type}")

    @staticmethod
    def save_to_file(event_logger: EventLogger, filepath: Path) -> None:
        """
        Save an EventLogger to a JSON file.

        Args:
            event_logger: The event logger to save
            filepath: Path to save the file
        """
        data = EventLogSerializer.serialize(event_logger)

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_from_file(filepath: Path) -> EventLogger:
        """
        Load an EventLogger from a JSON file.

        Args:
            filepath: Path to the file

        Returns:
            The loaded EventLogger
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        return EventLogSerializer.deserialize(data)


# ============================================================================
# Game Repository
# ============================================================================

@dataclass
class GameMetadata:
    """Metadata about a saved game."""
    game_id: str
    created_at: datetime
    player_names: List[str]
    is_complete: bool
    winner_name: Optional[str]
    total_rounds: int


class GameRepository:
    """
    Manages storage and retrieval of multiple games.

    Games are stored as JSON files in a specified directory structure:
    {base_dir}/{game_id}/game_state.json
    {base_dir}/{game_id}/events.json
    """

    def __init__(self, base_dir: Path = Path("flip7_games")):
        """
        Initialize the game repository.

        Args:
            base_dir: Base directory for storing game files
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_game(
        self,
        game_state: GameState,
        event_logger: EventLogger
    ) -> None:
        """
        Save a game (state and events) to disk.

        Args:
            game_state: The game state to save
            event_logger: The event logger to save
        """
        game_dir = self.base_dir / game_state.game_id
        game_dir.mkdir(parents=True, exist_ok=True)

        # Save game state
        GameStateSerializer.save_to_file(
            game_state,
            game_dir / "game_state.json"
        )

        # Save events
        EventLogSerializer.save_to_file(
            event_logger,
            game_dir / "events.json"
        )

    def load_game(self, game_id: str) -> Tuple[GameState, EventLogger]:
        """
        Load a game from disk.

        Args:
            game_id: ID of the game to load

        Returns:
            Tuple of (GameState, EventLogger)

        Raises:
            FileNotFoundError: If game not found
        """
        game_dir = self.base_dir / game_id

        if not game_dir.exists():
            raise FileNotFoundError(f"Game {game_id} not found")

        game_state = GameStateSerializer.load_from_file(
            game_dir / "game_state.json"
        )

        event_logger = EventLogSerializer.load_from_file(
            game_dir / "events.json"
        )

        return game_state, event_logger

    def list_games(self) -> List[GameMetadata]:
        """
        List all saved games with their metadata.

        Returns:
            List of GameMetadata for all saved games
        """
        games = []

        for game_dir in self.base_dir.iterdir():
            if not game_dir.is_dir():
                continue

            try:
                game_state = GameStateSerializer.load_from_file(
                    game_dir / "game_state.json"
                )

                winner_name = None
                if game_state.winner_id:
                    winner = next(
                        p for p in game_state.players
                        if p.player_id == game_state.winner_id
                    )
                    winner_name = winner.name

                metadata = GameMetadata(
                    game_id=game_state.game_id,
                    created_at=game_state.created_at,
                    player_names=[p.name for p in game_state.players],
                    is_complete=game_state.is_complete,
                    winner_name=winner_name,
                    total_rounds=len(game_state.round_history)
                )

                games.append(metadata)

            except Exception:
                # Skip games that can't be loaded
                continue

        # Sort by creation time (newest first)
        games.sort(key=lambda g: g.created_at, reverse=True)

        return games

    def get_all_completed_games(self) -> List[GameState]:
        """
        Load all completed games (for statistics).

        Returns:
            List of completed GameState objects
        """
        completed_games = []

        for metadata in self.list_games():
            if metadata.is_complete:
                try:
                    game_state, _ = self.load_game(metadata.game_id)
                    completed_games.append(game_state)
                except Exception:
                    continue

        return completed_games

    def delete_game(self, game_id: str) -> None:
        """
        Delete a saved game.

        Args:
            game_id: ID of the game to delete
        """
        game_dir = self.base_dir / game_id

        if game_dir.exists():
            import shutil
            shutil.rmtree(game_dir)
