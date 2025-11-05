"""
Game engine for Flip 7.

This module implements the core game flow logic, managing state transitions,
validating actions, and coordinating between rules, events, and state.
"""

from copy import deepcopy
from typing import List, Optional, Tuple
from uuid import uuid4

from flip_7.data.models import (
    GameState, RoundState, PlayerState, PlayerInfo,
    Card, NumberCard, ActionCard, ModifierCard,
    ActionType, RoundEndReason,
)
from flip_7.data.events import (
    EventLogger, GameStartedEvent, RoundStartedEvent,
    CardDealtEvent, PlayerHitEvent, PlayerStayedEvent,
    PlayerBustedEvent, ActionCardAppliedEvent,
    SecondChanceUsedEvent, DeckReshuffledEvent, RoundEndedEvent, GameEndedEvent
)
from flip_7.core.rules import (
    calculate_score, check_bust, check_win_condition,
    check_for_duplicate_cards, validate_player_can_stay, validate_player_can_hit,
    validate_second_chance_usage, check_round_end_condition,
    determine_round_end_reason, get_round_winners,
    ValidationResult
)
from flip_7.core.deck import create_deck, shuffle_deck


# ============================================================================
# Game Engine
# ============================================================================

class GameEngine:
    """
    Main game engine for Flip 7.

    This class manages the complete game lifecycle and enforces all rules.
    It uses an event logger to track all actions for replay and analysis.

    The engine is designed to work with both:
    - Manual game logging (user specifies cards)
    - Automated simulation (deck manager provides cards)

    Attributes:
        game_state: Current state of the game
        event_logger: Logger for tracking all game events
    """

    def __init__(self, game_state: Optional[GameState] = None, event_logger: Optional[EventLogger] = None):
        """
        Initialize the game engine.

        Args:
            game_state: Optional existing game state (for resuming games)
            event_logger: Optional existing event logger (for resuming games)
        """
        self.game_state = game_state
        self.event_logger = event_logger

    def start_new_game(self, player_names: List[str]) -> GameState:
        """
        Start a new game with the specified players.

        Args:
            player_names: Names of players (2-6 players recommended)

        Returns:
            The initialized game state

        Raises:
            ValueError: If invalid number of players or duplicate names
        """
        if len(player_names) < 2:
            raise ValueError("Need at least 2 players to start a game")

        if len(player_names) != len(set(player_names)):
            raise ValueError("Player names must be unique")

        # Create player info
        players = [PlayerInfo(player_id=str(uuid4()), name=name) for name in player_names]

        # Create and shuffle the deck (persists across rounds)
        deck = create_deck()
        deck = shuffle_deck(deck)

        # Create new game state
        game_id = str(uuid4())
        self.game_state = GameState(
            game_id=game_id,
            players=players,
            deck=deck,
            discard_pile=[]
        )

        # Initialize event logger
        self.event_logger = EventLogger(game_id)

        # Log game started event
        self.event_logger.log_event(GameStartedEvent(
            game_id=game_id,
            player_names=player_names,
            player_ids=[p.player_id for p in players]
        ))

        return self.game_state

    def start_new_round(self) -> RoundState:
        """
        Start a new round.

        The dealer rotates to the next player each round.

        Returns:
            The new round state

        Raises:
            ValueError: If game hasn't been started or is already complete
        """
        if self.game_state is None:
            raise ValueError("Game has not been started")

        if self.game_state.is_complete:
            raise ValueError("Game is already complete")

        # Determine round number
        round_number = len(self.game_state.round_history) + 1

        # Determine dealer (rotates each round)
        dealer_index = (round_number - 1) % len(self.game_state.players)
        dealer = self.game_state.players[dealer_index]

        # Create player states for this round
        player_states = {
            p.player_id: PlayerState(player_id=p.player_id, name=p.name)
            for p in self.game_state.players
        }

        # If not the first round, carry over total scores
        if self.game_state.round_history:
            last_round = self.game_state.round_history[-1]
            for player_id, last_ps in last_round.player_states.items():
                if player_id in player_states:
                    player_states[player_id].total_score = last_ps.total_score

        # Create round state
        round_state = RoundState(
            round_number=round_number,
            dealer_id=dealer.player_id,
            player_states=player_states,
            cards_remaining_in_deck=len(self.game_state.deck)  # Use persistent deck
        )

        self.game_state.current_round = round_state

        # Log round started event
        self.event_logger.log_event(RoundStartedEvent(
            game_id=self.game_state.game_id,
            round_number=round_number,
            dealer_id=dealer.player_id,
            dealer_name=dealer.name
        ))

        return round_state

    def deal_card_to_player(self, player_id: str, card: Card) -> None:
        """
        Deal a specific card to a player.

        This method is for manual game logging where the user specifies
        which card was dealt. For simulations, use a DeckManager to draw cards.

        Args:
            player_id: ID of the player receiving the card
            card: The card to deal

        Raises:
            ValueError: If invalid player or game state
        """
        if self.game_state is None or self.game_state.current_round is None:
            raise ValueError("No active round")

        current_round = self.game_state.current_round
        if player_id not in current_round.player_states:
            raise ValueError(f"Player {player_id} not in game")

        player_state = current_round.player_states[player_id]

        # Validate player can receive a card
        validation = validate_player_can_hit(player_state, current_round)
        if not validation.is_valid:
            raise ValueError(validation.error_message)

        # Find and remove a matching card from the deck
        # For manual logging, we match by card type and value, not ID
        card_from_deck = self._remove_card_from_deck(card)
        if card_from_deck is None:
            # If exact card not in deck, use the provided card (for manual override)
            card_from_deck = card

        # Add card to player's hand
        player_state.cards_in_hand.append(card_from_deck)

        # Update deck count
        current_round.cards_remaining_in_deck = len(self.game_state.deck)

        # Check if deck is empty and reshuffle if needed
        if len(self.game_state.deck) == 0 and len(self.game_state.discard_pile) > 0:
            self._reshuffle_deck()
            current_round.cards_remaining_in_deck = len(self.game_state.deck)

        # Handle action cards
        if isinstance(card_from_deck, ActionCard):
            self._apply_action_card(player_id, card_from_deck)

        # Update scores
        self._update_player_score(player_id)

        # Log card dealt event
        player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)
        self.event_logger.log_event(CardDealtEvent(
            game_id=self.game_state.game_id,
            player_id=player_id,
            player_name=player_name,
            card=card,
            cards_in_hand_count=len(player_state.cards_in_hand)
        ))

        # Check for bust
        if player_state.is_busted:
            self._handle_player_bust(player_id)

        # Handle Flip Three counter
        if player_state.flip_three_active and player_state.flip_three_count > 0:
            player_state.flip_three_count -= 1
            if player_state.flip_three_count == 0:
                player_state.flip_three_active = False

    def player_hit(self, player_id: str) -> None:
        """
        Record that a player chose to hit (take another card).

        Note: This doesn't deal the card itself - use deal_card_to_player()
        for that. This method just logs the decision.

        Args:
            player_id: ID of the player

        Raises:
            ValueError: If invalid action
        """
        if self.game_state is None or self.game_state.current_round is None:
            raise ValueError("No active round")

        player_state = self.game_state.current_round.player_states[player_id]
        validation = validate_player_can_hit(player_state, self.game_state.current_round)

        if not validation.is_valid:
            raise ValueError(validation.error_message)

        # Log the hit decision
        player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)
        self.event_logger.log_event(PlayerHitEvent(
            game_id=self.game_state.game_id,
            player_id=player_id,
            player_name=player_name,
            round_number=self.game_state.current_round.round_number
        ))

    def player_stay(self, player_id: str) -> None:
        """
        Record that a player chose to stay (end their turn).

        Args:
            player_id: ID of the player

        Raises:
            ValueError: If invalid action
        """
        if self.game_state is None or self.game_state.current_round is None:
            raise ValueError("No active round")

        current_round = self.game_state.current_round
        player_state = current_round.player_states[player_id]

        # Validate player can stay
        validation = validate_player_can_stay(player_state, current_round)
        if not validation.is_valid:
            raise ValueError(validation.error_message)

        # Mark player as stayed
        player_state.has_stayed = True

        # Calculate and record final score
        score_breakdown = calculate_score(player_state.cards_in_hand)
        player_state.round_score = score_breakdown.final_score
        player_state.total_score += player_state.round_score

        # Log stayed event
        player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)
        self.event_logger.log_event(PlayerStayedEvent(
            game_id=self.game_state.game_id,
            player_id=player_id,
            player_name=player_name,
            round_number=current_round.round_number,
            round_score=player_state.round_score,
            total_score=player_state.total_score,
            has_flip_7=score_breakdown.has_flip_7
        ))

        # Check if round should end
        if check_round_end_condition(current_round):
            self.end_round()

    def use_second_chance(self, player_id: str, card_to_discard: NumberCard) -> None:
        """
        Use a Second Chance card to discard a duplicate number card.

        Args:
            player_id: ID of the player
            card_to_discard: The duplicate number card to discard

        Raises:
            ValueError: If invalid action
        """
        if self.game_state is None or self.game_state.current_round is None:
            raise ValueError("No active round")

        player_state = self.game_state.current_round.player_states[player_id]

        # Validate Second Chance usage
        validation = validate_second_chance_usage(player_state, card_to_discard)
        if not validation.is_valid:
            raise ValueError(validation.error_message)

        # Remove the duplicate card and the Second Chance card
        player_state.cards_in_hand.remove(card_to_discard)

        # Find and remove Second Chance action card
        second_chance_card = next(
            c for c in player_state.cards_in_hand
            if isinstance(c, ActionCard) and c.action_type == ActionType.SECOND_CHANCE
        )
        player_state.cards_in_hand.remove(second_chance_card)

        # Update flag
        player_state.has_second_chance = False

        # Recalculate score
        self._update_player_score(player_id)

        # Log event
        player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)
        self.event_logger.log_event(SecondChanceUsedEvent(
            game_id=self.game_state.game_id,
            player_id=player_id,
            player_name=player_name,
            discarded_card_value=card_to_discard.value,
            round_number=self.game_state.current_round.round_number
        ))

    def end_round(self) -> RoundState:
        """
        End the current round and update scores.

        Returns:
            The completed round state

        Raises:
            ValueError: If no active round
        """
        if self.game_state is None or self.game_state.current_round is None:
            raise ValueError("No active round")

        current_round = self.game_state.current_round

        # Mark round as complete
        current_round.is_complete = True
        current_round.end_reason = determine_round_end_reason(current_round)

        # Determine round winners
        current_round.winner_ids = get_round_winners(current_round)

        # Calculate final scores for any players who didn't stay
        for player_id, player_state in current_round.player_states.items():
            if not player_state.has_stayed and not player_state.is_busted:
                score_breakdown = calculate_score(player_state.cards_in_hand)
                player_state.round_score = score_breakdown.final_score
                player_state.total_score += player_state.round_score

        # Log round ended event
        player_scores = {
            pid: ps.round_score
            for pid, ps in current_round.player_states.items()
        }
        self.event_logger.log_event(RoundEndedEvent(
            game_id=self.game_state.game_id,
            round_number=current_round.round_number,
            end_reason=current_round.end_reason,
            player_scores=player_scores,
            winner_ids=current_round.winner_ids
        ))

        # Move all cards from this round to the discard pile
        for player_state in current_round.player_states.values():
            self.game_state.discard_pile.extend(player_state.cards_in_hand)

        # Move round to history
        self.game_state.round_history.append(current_round)
        self.game_state.current_round = None

        # Check for game end
        self._check_game_end()

        return current_round

    def _apply_action_card(self, player_id: str, card: ActionCard) -> None:
        """
        Apply the effect of an action card.

        Args:
            player_id: ID of the player receiving the action
            card: The action card
        """
        player_state = self.game_state.current_round.player_states[player_id]
        player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)

        if card.action_type == ActionType.FREEZE:
            # Player banks points and must stay
            player_state.has_stayed = True
            score_breakdown = calculate_score(player_state.cards_in_hand)
            player_state.round_score = score_breakdown.final_score
            player_state.total_score += player_state.round_score

            self.event_logger.log_event(ActionCardAppliedEvent(
                game_id=self.game_state.game_id,
                player_id=player_id,
                player_name=player_name,
                action_type=ActionType.FREEZE,
                effect_description=f"{player_name} was frozen and banked {player_state.round_score} points"
            ))

            # Check if round should end (fixes softlock when last player gets frozen)
            if check_round_end_condition(self.game_state.current_round):
                self.end_round()

        elif card.action_type == ActionType.FLIP_THREE:
            # Player must take next 3 cards
            player_state.flip_three_active = True
            player_state.flip_three_count = 3

            self.event_logger.log_event(ActionCardAppliedEvent(
                game_id=self.game_state.game_id,
                player_id=player_id,
                player_name=player_name,
                action_type=ActionType.FLIP_THREE,
                effect_description=f"{player_name} must accept the next 3 cards"
            ))

        elif card.action_type == ActionType.SECOND_CHANCE:
            # Player can hold this card to use later
            # Only one Second Chance allowed at a time
            if not player_state.has_second_chance:
                player_state.has_second_chance = True

                self.event_logger.log_event(ActionCardAppliedEvent(
                    game_id=self.game_state.game_id,
                    player_id=player_id,
                    player_name=player_name,
                    action_type=ActionType.SECOND_CHANCE,
                    effect_description=f"{player_name} received a Second Chance card"
                ))

    def _update_player_score(self, player_id: str) -> None:
        """
        Update a player's current score and check for bust.

        Bust conditions:
        1. Having duplicate number cards (same value twice) - UNLESS player has Second Chance
        2. Reaching 200+ total points means the player WINS (not busts)

        Args:
            player_id: ID of the player
        """
        player_state = self.game_state.current_round.player_states[player_id]

        # Check for duplicate number cards (immediate bust unless Second Chance available)
        has_duplicates = check_for_duplicate_cards(player_state.cards_in_hand)

        if has_duplicates and not player_state.has_second_chance:
            # Player has duplicates and no Second Chance - they bust!
            player_state.is_busted = True
            player_state.round_score = 0  # Bust means zero points for the round
            return

        # Calculate current round score (only if not busted)
        score_breakdown = calculate_score(player_state.cards_in_hand)
        player_state.round_score = score_breakdown.final_score

        # Check if player reached winning score (200+)
        # This is a WIN, not a bust!
        potential_total = player_state.total_score + score_breakdown.final_score

        if potential_total >= 200:
            # Player is close to or at winning - this isn't a bust
            # They can choose to stay to lock in their score
            pass

    def _handle_player_bust(self, player_id: str) -> None:
        """
        Handle a player busting.

        Args:
            player_id: ID of the player who busted
        """
        player_state = self.game_state.current_round.player_states[player_id]
        player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)

        # Log bust event
        self.event_logger.log_event(PlayerBustedEvent(
            game_id=self.game_state.game_id,
            player_id=player_id,
            player_name=player_name,
            round_number=self.game_state.current_round.round_number,
            total_score=player_state.total_score + player_state.round_score
        ))

        # Check if round should end
        if check_round_end_condition(self.game_state.current_round):
            self.end_round()

    def _check_game_end(self) -> None:
        """Check if the game should end and handle game completion."""
        # Get current total scores from last completed round
        if not self.game_state.round_history:
            return

        last_round = self.game_state.round_history[-1]
        player_states = last_round.player_states

        # Check win condition
        winner_id = check_win_condition(player_states)

        if winner_id is not None:
            self.game_state.is_complete = True
            self.game_state.winner_id = winner_id

            winner = next(p for p in self.game_state.players if p.player_id == winner_id)
            final_scores = {
                pid: ps.total_score
                for pid, ps in player_states.items()
            }

            # Log game ended event
            self.event_logger.log_event(GameEndedEvent(
                game_id=self.game_state.game_id,
                winner_id=winner_id,
                winner_name=winner.name,
                final_scores=final_scores,
                total_rounds=len(self.game_state.round_history)
            ))

    def _remove_card_from_deck(self, card: Card) -> Optional[Card]:
        """
        Find and remove a matching card from the deck.

        For manual logging, we match cards by type and value, not ID.

        Args:
            card: The card to match and remove

        Returns:
            The removed card from deck, or None if not found
        """
        for i, deck_card in enumerate(self.game_state.deck):
            if self._cards_match(card, deck_card):
                return self.game_state.deck.pop(i)
        return None

    def _cards_match(self, card1: Card, card2: Card) -> bool:
        """
        Check if two cards match (same type and value).

        Args:
            card1: First card
            card2: Second card

        Returns:
            True if cards match, False otherwise
        """
        if type(card1) != type(card2):
            return False

        if isinstance(card1, NumberCard) and isinstance(card2, NumberCard):
            return card1.value == card2.value
        elif isinstance(card1, ModifierCard) and isinstance(card2, ModifierCard):
            return card1.modifier_type == card2.modifier_type
        elif isinstance(card1, ActionCard) and isinstance(card2, ActionCard):
            return card1.action_type == card2.action_type

        return False

    def _reshuffle_deck(self) -> None:
        """
        Reshuffle the discard pile into the deck when deck is exhausted.

        This happens mid-game when the deck runs out of cards.
        """
        if len(self.game_state.discard_pile) == 0:
            return

        # Shuffle discard pile
        shuffled_discard = shuffle_deck(self.game_state.discard_pile)

        # Add to deck
        self.game_state.deck = shuffled_discard
        self.game_state.discard_pile = []

        # Log reshuffle event
        round_number = self.game_state.current_round.round_number if self.game_state.current_round else 0

        self.event_logger.log_event(DeckReshuffledEvent(
            game_id=self.game_state.game_id,
            round_number=round_number,
            cards_reshuffled=len(self.game_state.deck)
        ))

    def get_game_state(self) -> GameState:
        """
        Get the current game state.

        Returns:
            The current game state

        Raises:
            ValueError: If game hasn't been started
        """
        if self.game_state is None:
            raise ValueError("Game has not been started")

        return self.game_state

    def get_event_logger(self) -> EventLogger:
        """
        Get the event logger.

        Returns:
            The event logger

        Raises:
            ValueError: If game hasn't been started
        """
        if self.event_logger is None:
            raise ValueError("Game has not been started")

        return self.event_logger
