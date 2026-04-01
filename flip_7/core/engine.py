"""
Game engine for Flip 7.

This module implements the core game flow logic, managing state transitions,
validating actions, and coordinating between rules, events, and state.
"""

import random
from copy import deepcopy
from typing import List, Optional, Tuple
from uuid import uuid4

from flip_7.data.models import (
    GameState, RoundState, PlayerState, PlayerInfo,
    Card, NumberCard, ActionCard, ModifierCard,
    ActionType, RoundEndReason, PendingEffect,
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

    def start_new_game(
        self,
        player_names: List[str],
        player_ids: Optional[List[str]] = None,
    ) -> GameState:
        """
        Start a new game with the specified players.

        Args:
            player_names: Names of players (2-6 players recommended)
            player_ids: Optional pre-assigned player IDs. If omitted, UUIDs are
                generated automatically. When provided, must be the same length
                as player_names with no duplicates.

        Returns:
            The initialized game state

        Raises:
            ValueError: If invalid number of players or duplicate names/IDs
        """
        if len(player_names) < 2:
            raise ValueError("Need at least 2 players to start a game")

        if len(player_names) != len(set(player_names)):
            raise ValueError("Player names must be unique")

        if player_ids is not None:
            if len(player_ids) != len(player_names):
                raise ValueError("player_ids must be the same length as player_names")
            if len(player_ids) != len(set(player_ids)):
                raise ValueError("player_ids must be unique")
        else:
            player_ids = [str(uuid4()) for _ in player_names]

        # Create player info
        players = [
            PlayerInfo(player_id=pid, name=name)
            for pid, name in zip(player_ids, player_names)
        ]

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

        # Create round state — dealer goes first, and rotates each round
        round_state = RoundState(
            round_number=round_number,
            dealer_id=dealer.player_id,
            current_player_id=dealer.player_id,
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

    def deal_card_to_player(self, player_id: str, card: Optional[Card] = None) -> Card:
        """
        Deal a card to a player.

        If no card is specified, one is drawn randomly from the deck (the normal
        game flow). If a card is specified, that specific card is dealt (used by
        tests and simulation engines).

        Args:
            player_id: ID of the player receiving the card
            card: Optional specific card to deal; if None, draws randomly

        Returns:
            The card that was dealt

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

        if card is None:
            # Random draw from the deck
            card_from_deck = self._draw_random_card()
            if card_from_deck is None:
                raise ValueError("No cards remaining in deck")
        else:
            # Find and remove a matching card from the deck.
            # For manual / test use, we match by card type and value, not ID.
            card_from_deck = self._remove_card_from_deck(card)
            if card_from_deck is None:
                # Card not in deck — use the provided card directly (manual override)
                card_from_deck = card

        # Check if flip_three was active BEFORE dealing this card
        # This ensures the FLIP_THREE card itself doesn't count toward the 3
        flip_three_was_active = player_state.flip_three_active

        # Add card to player's hand
        player_state.cards_in_hand.append(card_from_deck)

        # Update deck count
        current_round.cards_remaining_in_deck = len(self.game_state.deck)

        # Check if deck is empty and reshuffle if needed
        if len(self.game_state.deck) == 0 and len(self.game_state.discard_pile) > 0:
            self._reshuffle_deck()
            current_round.cards_remaining_in_deck = len(self.game_state.deck)

        # NOTE: Action cards are NO LONGER automatically applied here
        # The caller must now call apply_action_card_effect() after dealing
        # to specify the target for the action card effect.
        # This allows for strategic targeting of Flip Three and Freeze cards.

        # Check if round ended due to action card (e.g., FREEZE on last player)
        # If so, skip remaining processing as round is already complete
        if self.game_state.current_round is None:
            return

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

        # Check for Flip 7 — player collected 7 unique number cards, round ends immediately
        if (
            self.game_state.current_round is not None
            and not player_state.is_busted
            and check_round_end_condition(self.game_state.current_round)
        ):
            # Bank the Flip 7 player's score before ending (they didn't explicitly stay)
            score_breakdown = calculate_score(player_state.cards_in_hand)
            player_state.round_score = score_breakdown.final_score
            player_state.total_score += player_state.round_score
            self.end_round()
            return card_from_deck

        # Handle Flip Three counter - only decrement for non-action cards
        # Only check counter if flip_three was ALREADY active before this card
        if flip_three_was_active and player_state.flip_three_count > 0:
            # Only decrement if the card dealt was NOT an action card
            if not isinstance(card_from_deck, ActionCard):
                player_state.flip_three_count -= 1
                if player_state.flip_three_count == 0:
                    player_state.flip_three_active = False

        # Advance the turn for non-action cards.
        # Action cards advance the turn only after apply_action_card_effect() is called,
        # because the effect (and therefore target selection) hasn't happened yet.
        if not isinstance(card_from_deck, ActionCard) and self.game_state.current_round is not None:
            self._advance_turn()

        return card_from_deck

    def apply_action_card_effect(
        self,
        card: ActionCard,
        target_player_id: str,
        original_player_id: Optional[str] = None
    ) -> None:
        """
        Apply an action card's effect to a target player.

        This method must be called after dealing an action card via deal_card_to_player().
        It allows the caller to specify who should receive the effect.

        Args:
            card: The action card to apply
            target_player_id: ID of the player who receives the effect
            original_player_id: Optional ID of the player who drew the card (for logging)

        Raises:
            ValueError: If invalid game state or target player

        Example:
            # Deal a Freeze card to player1
            engine.deal_card_to_player("player1", freeze_card)

            # Apply the freeze effect to player2 (opponent)
            engine.apply_action_card_effect(freeze_card, "player2", "player1")
        """
        if self.game_state is None or self.game_state.current_round is None:
            raise ValueError("No active round")

        if target_player_id not in self.game_state.current_round.player_states:
            raise ValueError(f"Player {target_player_id} not in game")

        # Validate target player can receive effect (must be active, not stayed)
        target_state = self.game_state.current_round.player_states[target_player_id]
        if target_state.has_stayed and card.action_type in [ActionType.FREEZE, ActionType.FLIP_THREE]:
            raise ValueError(f"Cannot apply {card.action_type.value} to {target_player_id} - player has already stayed")

        # Special validation for Second Chance
        if card.action_type == ActionType.SECOND_CHANCE:
            # If original player already has Second Chance, cannot give second one to self
            if original_player_id and original_player_id == target_player_id:
                original_state = self.game_state.current_round.player_states[original_player_id]
                if original_state.has_second_chance:
                    raise ValueError(
                        f"Player {original_player_id} already has a Second Chance card. "
                        "Second one must be given to an opponent."
                    )

        # Apply the effect
        self._apply_action_card(target_player_id, card, original_player_id)

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

        # Check if round should end; otherwise advance to the next player
        if check_round_end_condition(current_round):
            self.end_round()
        else:
            self._advance_turn()

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

    def _apply_action_card(
        self,
        target_player_id: str,
        card: ActionCard,
        original_player_id: Optional[str] = None
    ) -> None:
        """
        Apply the effect of an action card to a target player.

        Args:
            target_player_id: ID of the player receiving the effect
            card: The action card
            original_player_id: ID of the player who drew the card (for logging)
        """
        target_state = self.game_state.current_round.player_states[target_player_id]
        target_name = next(p.name for p in self.game_state.players if p.player_id == target_player_id)

        # Get original player name if provided
        if original_player_id and original_player_id != target_player_id:
            original_name = next(p.name for p in self.game_state.players if p.player_id == original_player_id)
        else:
            original_name = None

        if card.action_type == ActionType.FREEZE:
            # Target player banks points and must stay
            target_state.has_stayed = True
            score_breakdown = calculate_score(target_state.cards_in_hand)
            target_state.round_score = score_breakdown.final_score
            target_state.total_score += target_state.round_score

            # Create description based on whether it was applied to self or opponent
            if original_name and original_name != target_name:
                description = f"{original_name} froze {target_name} who banked {target_state.round_score} points"
            else:
                description = f"{target_name} was frozen and banked {target_state.round_score} points"

            self.event_logger.log_event(ActionCardAppliedEvent(
                game_id=self.game_state.game_id,
                player_id=target_player_id,
                player_name=target_name,
                action_type=ActionType.FREEZE,
                effect_description=description
            ))

            # Check if round should end (fixes softlock when last player gets frozen)
            if check_round_end_condition(self.game_state.current_round):
                self.end_round()

        elif card.action_type == ActionType.FLIP_THREE:
            # Target player must take next 3 cards
            target_state.flip_three_active = True
            target_state.flip_three_count = 3

            # If the target is not the current player, push to the effect stack so
            # _advance_turn() will interrupt normal rotation and give them the turn next.
            current_player_id = self.game_state.current_round.current_player_id
            if target_player_id != current_player_id:
                self.game_state.current_round.effect_stack.insert(
                    0, PendingEffect(effect_type="flip_three", target_id=target_player_id)
                )

            # Create description based on whether it was applied to self or opponent
            if original_name and original_name != target_name:
                description = f"{original_name} applied Flip Three to {target_name} who must accept the next 3 cards"
            else:
                description = f"{target_name} must accept the next 3 cards"

            self.event_logger.log_event(ActionCardAppliedEvent(
                game_id=self.game_state.game_id,
                player_id=target_player_id,
                player_name=target_name,
                action_type=ActionType.FLIP_THREE,
                effect_description=description
            ))

        elif card.action_type == ActionType.SECOND_CHANCE:
            # Target player can hold this card to use later
            # Only one Second Chance allowed at a time
            if not target_state.has_second_chance:
                target_state.has_second_chance = True

                # If card was given to someone else, move it from original player's hand to target's hand
                if original_player_id and original_player_id != target_player_id:
                    original_state = self.game_state.current_round.player_states[original_player_id]
                    # Find the Second Chance card in original player's hand
                    sc_card_in_hand = next(
                        (c for c in original_state.cards_in_hand
                         if isinstance(c, ActionCard) and c.action_type == ActionType.SECOND_CHANCE),
                        None
                    )
                    if sc_card_in_hand:
                        # Remove from original player's hand and add to target's hand
                        original_state.cards_in_hand.remove(sc_card_in_hand)
                        target_state.cards_in_hand.append(sc_card_in_hand)

                # Create description based on whether it was applied to self or opponent
                if original_name and original_name != target_name:
                    description = f"{original_name} gave Second Chance to {target_name}"
                else:
                    description = f"{target_name} received a Second Chance card"

                self.event_logger.log_event(ActionCardAppliedEvent(
                    game_id=self.game_state.game_id,
                    player_id=target_player_id,
                    player_name=target_name,
                    action_type=ActionType.SECOND_CHANCE,
                    effect_description=description
                ))

        # Advance the turn after the action card's effect has been applied.
        # _advance_turn() handles all cases: Freeze (target stayed → skip them), Flip Three
        # (either current player stays put if self-targeted, or opponent becomes next via stack),
        # Second Chance (drawing player's turn is done).
        if self.game_state.current_round is not None:
            self._advance_turn()

    def _advance_turn(self) -> None:
        """
        Advance current_player_id to the next player who needs to act.

        Resolution order:
        1. If the current player is still in forced-draw mode (flip_three_count > 0),
           stay on them — they haven't finished their mandatory draws yet.
        2. Check the effect_stack for any pending interrupts (e.g. Flip Three applied
           to an opponent). If found and the target is still active, make them current.
        3. Otherwise, advance to the next active player in rotation order (skipping
           anyone who has stayed or busted).
        """
        current_round = self.game_state.current_round
        if current_round is None:
            return

        current_id = current_round.current_player_id
        if current_id is None:
            return

        # 1. Current player still has forced draws remaining — keep their turn.
        #    Exception: if they busted, always advance (bust clears their obligation).
        current_state = current_round.player_states.get(current_id)
        if current_state and not current_state.is_busted and current_state.flip_three_active and current_state.flip_three_count > 0:
            return

        # 2. Check the effect stack for pending interrupts.
        while current_round.effect_stack:
            effect = current_round.effect_stack.pop(0)
            target_state = current_round.player_states.get(effect.target_id)
            if target_state and not target_state.has_stayed and not target_state.is_busted:
                current_round.current_player_id = effect.target_id
                return
            # Target is already done — discard this effect and keep looking.

        # 3. Normal rotation: find the next active player after the current one.
        players = self.game_state.players
        current_index = next(
            (i for i, p in enumerate(players) if p.player_id == current_id), 0
        )

        num_players = len(players)
        for offset in range(1, num_players + 1):
            next_index = (current_index + offset) % num_players
            next_player = players[next_index]
            next_state = current_round.player_states[next_player.player_id]
            if not next_state.has_stayed and not next_state.is_busted:
                current_round.current_player_id = next_player.player_id
                return

        # All players are done — round should end via check_round_end_condition.
        current_round.current_player_id = None

    def _draw_random_card(self) -> Optional[Card]:
        """
        Draw a random card from the top of the (pre-shuffled) deck.

        Reshuffles the discard pile into the deck automatically if the deck
        is empty. Returns None only if both deck and discard pile are empty.
        """
        if len(self.game_state.deck) == 0:
            if len(self.game_state.discard_pile) > 0:
                self._reshuffle_deck()
            else:
                return None
        return self.game_state.deck.pop(0)

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

        if has_duplicates and player_state.has_second_chance:
            # Auto-use Second Chance: find and discard one copy of the duplicate,
            # then consume the Second Chance card. The player has no choice here —
            # holding a Second Chance obligates its use to avoid the bust.
            number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]
            card_values = [c.value for c in number_cards]
            duplicate_value = next(v for v in card_values if card_values.count(v) > 1)
            card_to_discard = next(c for c in number_cards if c.value == duplicate_value)
            player_state.cards_in_hand.remove(card_to_discard)

            second_chance_card = next(
                c for c in player_state.cards_in_hand
                if isinstance(c, ActionCard) and c.action_type == ActionType.SECOND_CHANCE
            )
            player_state.cards_in_hand.remove(second_chance_card)
            player_state.has_second_chance = False

            player_name = next(p.name for p in self.game_state.players if p.player_id == player_id)
            self.event_logger.log_event(SecondChanceUsedEvent(
                game_id=self.game_state.game_id,
                player_id=player_id,
                player_name=player_name,
                discarded_card_value=duplicate_value,
                round_number=self.game_state.current_round.round_number
            ))

        # Calculate current round score (only if not busted)
        score_breakdown = calculate_score(player_state.cards_in_hand)
        player_state.round_score = score_breakdown.final_score

        # Note: Reaching or exceeding 200 is WINNING, not busting!
        # The only way to bust is duplicate cards (checked above)

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
