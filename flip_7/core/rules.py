"""
Game rules and validation logic for Flip 7.

This module implements all game rules including:
- Score calculation with modifiers and bonuses
- Flip 7 detection
- Bust checking
- Win condition validation
- Action validation
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from flip_7.data.models import (
    Card, NumberCard, ActionCard, ModifierCard,
    PlayerState, GameState, RoundState,
    ScoreBreakdown, ModifierType, ActionType,
    PlayerDecision
)


# ============================================================================
# Constants
# ============================================================================

WINNING_SCORE = 200  # Score needed to win the game
FLIP_7_BONUS_POINTS = 15  # Bonus points for achieving Flip 7
FLIP_7_REQUIRED_CARDS = 7  # Number of cards needed for Flip 7


# ============================================================================
# Score Calculation
# ============================================================================

def calculate_score(cards: List[Card]) -> ScoreBreakdown:
    """
    Calculate the score for a set of cards following Flip 7 rules.

    Scoring rules:
    1. Add up all Number card values (base_score)
    2. Add bonus points from PLUS_X modifier cards (bonus_points)
    3. If x2 modifier card present, double BOTH base_score AND bonus_points
    4. If player has exactly 7 Number cards, add 15 bonus points (after multiplier)

    Final formula: (base_score + bonus_points) * multiplier + flip_7_bonus

    Args:
        cards: List of cards to score

    Returns:
        ScoreBreakdown with detailed calculation
    """
    number_cards = [c for c in cards if isinstance(c, NumberCard)]
    modifier_cards = [c for c in cards if isinstance(c, ModifierCard)]

    # Step 1: Calculate base score from number cards
    base_score = sum(card.value for card in number_cards)

    # Step 2: Calculate bonus points from PLUS_X modifiers
    bonus_points = 0
    for modifier in modifier_cards:
        if modifier.modifier_type != ModifierType.MULTIPLY_2:
            bonus_points += modifier.value

    # Step 3: Check for multiplier
    has_multiplier = any(
        m.modifier_type == ModifierType.MULTIPLY_2
        for m in modifier_cards
    )
    multiplier = 2 if has_multiplier else 1

    # Step 4: Check for Flip 7
    has_flip_7 = len(number_cards) == FLIP_7_REQUIRED_CARDS
    flip_7_bonus = FLIP_7_BONUS_POINTS if has_flip_7 else 0

    # Calculate final score
    # Formula: (base_score + bonus_points) * multiplier + flip_7_bonus
    # Note: Multiplier applies to both base cards AND bonus points
    final_score = (base_score + bonus_points) * multiplier + flip_7_bonus

    return ScoreBreakdown(
        base_score=base_score,
        bonus_points=bonus_points,
        multiplier=multiplier,
        flip_7_bonus=flip_7_bonus,
        final_score=final_score,
        has_flip_7=has_flip_7,
        number_card_count=len(number_cards)
    )


def check_flip_7(cards: List[Card]) -> bool:
    """
    Check if a set of cards achieves Flip 7.

    Flip 7 is achieved when a player has exactly 7 Number cards.

    Args:
        cards: List of cards to check

    Returns:
        True if Flip 7 is achieved, False otherwise
    """
    number_cards = [c for c in cards if isinstance(c, NumberCard)]
    return len(number_cards) == FLIP_7_REQUIRED_CARDS


def check_for_duplicate_cards(cards: List[Card]) -> bool:
    """
    Check if a player has duplicate number cards (same value twice).

    Having duplicate number cards causes an immediate bust - player gets zero points for the round.

    Args:
        cards: List of cards to check

    Returns:
        True if there are duplicate number cards, False otherwise
    """
    number_cards = [c for c in cards if isinstance(c, NumberCard)]
    card_values = [c.value for c in number_cards]

    # Check if any value appears more than once
    return len(card_values) != len(set(card_values))


def check_bust(total_score: int) -> bool:
    """
    Check if a player has reached the winning score.

    NOTE: This function name is misleading - reaching 200+ is WINNING, not busting!
    The only way to bust in Flip 7 is to get duplicate number cards (see check_for_duplicate_cards).

    Args:
        total_score: The player's total score across all rounds

    Returns:
        True if score is at or above 200 (winning threshold)
    """
    return total_score >= WINNING_SCORE


# ============================================================================
# Win Condition Checking
# ============================================================================

def check_win_condition(player_states: Dict[str, PlayerState]) -> Optional[str]:
    """
    Check if the game has a winner.

    Win condition: At least one player has reached or exceeded 200 points,
    and the player with the highest score wins.

    Args:
        player_states: Current state of all players

    Returns:
        The player_id of the winner, or None if no winner yet
    """
    # Check if any player has reached 200+
    max_score = max(ps.total_score for ps in player_states.values())

    if max_score >= WINNING_SCORE:
        # Find the player(s) with the highest score
        winners = [
            pid for pid, ps in player_states.items()
            if ps.total_score == max_score
        ]

        # Return the winner (or first if there's a tie)
        return winners[0] if winners else None

    return None


def get_round_winners(round_state: RoundState) -> List[str]:
    """
    Determine the winner(s) of a round.

    The round winner is the player with the highest round score
    who didn't bust.

    Args:
        round_state: The completed round

    Returns:
        List of player IDs who won the round (can be multiple if tied)
    """
    if not round_state.is_complete:
        return []

    # Only consider players who haven't busted
    active_players = {
        pid: ps for pid, ps in round_state.player_states.items()
        if not ps.is_busted
    }

    if not active_players:
        return []

    # Find the maximum score
    max_score = max(ps.round_score for ps in active_players.values())

    # Return all players with the max score
    return [
        pid for pid, ps in active_players.items()
        if ps.round_score == max_score
    ]


# ============================================================================
# Validation
# ============================================================================

@dataclass
class ValidationResult:
    """
    Result of validating a game action.

    Attributes:
        is_valid: Whether the action is valid
        error_message: Explanation if invalid, None if valid
    """
    is_valid: bool
    error_message: Optional[str] = None


def validate_player_can_stay(
    player_state: PlayerState,
    round_state: RoundState
) -> ValidationResult:
    """
    Validate that a player can choose to stay.

    Rules:
    - Player cannot stay if they've already stayed
    - Player cannot stay if they're busted
    - Player cannot stay if Flip Three is active (must take all 3 cards first)
    - Special case: Player CAN stay if they have Flip 7, regardless of turn order

    Args:
        player_state: The player's current state
        round_state: The current round state

    Returns:
        ValidationResult indicating if the action is valid
    """
    if player_state.has_stayed:
        return ValidationResult(False, "Player has already stayed")

    if player_state.is_busted:
        return ValidationResult(False, "Player is busted and cannot stay")

    if player_state.flip_three_active and player_state.flip_three_count > 0:
        return ValidationResult(
            False,
            f"Player must accept {player_state.flip_three_count} more cards (Flip Three active)"
        )

    # Valid to stay
    return ValidationResult(True)


def validate_player_can_hit(
    player_state: PlayerState,
    round_state: RoundState
) -> ValidationResult:
    """
    Validate that a player can choose to hit (take another card).

    Rules:
    - Player cannot hit if they've already stayed
    - Player cannot hit if they're busted
    - Player cannot hit if deck is empty

    Args:
        player_state: The player's current state
        round_state: The current round state

    Returns:
        ValidationResult indicating if the action is valid
    """
    if player_state.has_stayed:
        return ValidationResult(False, "Player has already stayed")

    if player_state.is_busted:
        return ValidationResult(False, "Player is busted and cannot take more cards")

    if round_state.cards_remaining_in_deck <= 0:
        return ValidationResult(False, "Deck is empty")

    # Valid to hit
    return ValidationResult(True)


def validate_second_chance_usage(
    player_state: PlayerState,
    card_to_discard: NumberCard
) -> ValidationResult:
    """
    Validate that a player can use Second Chance to discard a duplicate.

    Rules:
    - Player must have a Second Chance card
    - The card to discard must be a NumberCard
    - The card to discard must be in the player's hand
    - There must be at least 2 cards with the same value in hand

    Args:
        player_state: The player's current state
        card_to_discard: The card the player wants to discard

    Returns:
        ValidationResult indicating if the action is valid
    """
    if not player_state.has_second_chance:
        return ValidationResult(False, "Player does not have Second Chance card")

    # Check if card is in hand
    if card_to_discard not in player_state.cards_in_hand:
        return ValidationResult(False, "Card to discard is not in player's hand")

    # Check if there are duplicates
    number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]
    duplicate_count = sum(1 for c in number_cards if c.value == card_to_discard.value)

    if duplicate_count < 2:
        return ValidationResult(
            False,
            f"No duplicate found for card value {card_to_discard.value}"
        )

    # Valid Second Chance usage
    return ValidationResult(True)


def check_round_end_condition(round_state: RoundState) -> bool:
    """
    Check if the round should end.

    Round ends when:
    1. All players have stayed or busted, OR
    2. Deck is exhausted

    Args:
        round_state: The current round state

    Returns:
        True if round should end, False otherwise
    """
    # Check if all players have either stayed or busted
    all_done = all(
        ps.has_stayed or ps.is_busted
        for ps in round_state.player_states.values()
    )

    if all_done:
        return True

    # Check if deck is empty
    if round_state.cards_remaining_in_deck <= 0:
        return True

    return False


def determine_round_end_reason(round_state: RoundState) -> Optional['RoundEndReason']:
    """
    Determine why a round ended.

    Args:
        round_state: The completed round

    Returns:
        The reason the round ended
    """
    from flip_7.data.models import RoundEndReason

    # Check for bust
    if any(ps.is_busted for ps in round_state.player_states.values()):
        return RoundEndReason.PLAYER_BUSTED

    # Check if all stayed
    if all(ps.has_stayed or ps.is_busted for ps in round_state.player_states.values()):
        return RoundEndReason.ALL_STAYED

    # Check if deck exhausted
    if round_state.cards_remaining_in_deck <= 0:
        return RoundEndReason.DECK_EXHAUSTED

    return None
