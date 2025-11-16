"""
Threshold-based strategy for flip_7 simulation.

This strategy hits until reaching a target score, then stays.
"""

from typing import List, Optional

from flip_7.data.models import NumberCard
from flip_7.simulation.strategy import BaseStrategy, StrategyContext, OpponentInfo


class ThresholdStrategy(BaseStrategy):
    """
    Strategy that hits until reaching a score threshold, then stays.

    This is a simple strategy that hits until the round score reaches
    the target, then stays to bank the points.

    Attributes:
        target_score: Score threshold to reach before staying
    """

    def __init__(
        self,
        name: Optional[str] = None,
        target_score: int = 100,
        distance_from_200: int = 0
    ):
        """
        Initialize threshold strategy.

        Args:
            name: Optional custom name
            target_score: Score to reach before staying (default: 100)
            distance_from_200: If an opponent is within this distance from 200, then you will hit (default: 0)
        """
        super().__init__(name or f"Threshold({target_score})")
        self.target_score = target_score
        self.distance_from_200 = distance_from_200

    def decide_hit_or_stay(self, context: StrategyContext) -> bool:
        """
        Decide whether to hit or stay based on threshold.

        Decision logic:
        1. If flip_three active, must hit (no choice)
        2. If below target_score, hit
        3. Otherwise, stay

        Args:
            context: Complete game context

        Returns:
            True to HIT, False to STAY
        """
        # If flip_three is active, must hit
        if context.my_flip_three_active and context.my_flip_three_count > 0:
            return True

        # Hit if below threshold, otherwise stay
        return context.my_round_score < self.target_score or self.opponent_can_win(context)

    def decide_second_chance_discard(
        self,
        context: StrategyContext,
        duplicate_value: int,
        duplicate_cards: List[NumberCard]
    ) -> NumberCard:
        """
        Decide which duplicate to discard when using Second Chance.

        Strategy: Discard the most recently drawn card (last in list).
        This is equivalent for most purposes since both cards have the same value.

        Args:
            context: Game context
            duplicate_value: The duplicated value
            duplicate_cards: List of duplicate cards (exactly 2)

        Returns:
            The most recently drawn duplicate card
        """
        # Discard the most recently drawn (last in list)
        return duplicate_cards[-1]

    def decide_flip_three_target(
        self,
        context: StrategyContext,
        possible_targets: List[str]
    ) -> str:
        """
        Decide who receives the Flip Three effect.

        Strategy:
        - If no opponents available, apply to self
        - Otherwise, apply to opponent with highest total score (force them to risk)

        Args:
            context: Game context
            possible_targets: List of eligible player IDs

        Returns:
            Player ID to receive Flip Three effect
        """
        # Filter to get only opponents (not self)
        opponent_ids = [
            opp.player_id for opp in context.opponents
            if opp.player_id in possible_targets
        ]

        # If no opponents available, must apply to self
        if not opponent_ids:
            return context.my_player_id

        # Apply to opponent with highest total score
        opponent_scores = {
            opp.player_id: opp.total_score
            for opp in context.opponents
            if opp.player_id in opponent_ids
        }
        return max(opponent_scores.keys(), key=lambda pid: opponent_scores[pid])

    def decide_freeze_target(
        self,
        context: StrategyContext,
        possible_targets: List[str]
    ) -> str:
        """
        Decide who gets frozen.

        Strategy:
        - If my round score >= target threshold, freeze self (bank good score)
        - Otherwise, freeze opponent with highest total score (prevent improvement)

        Args:
            context: Game context
            possible_targets: List of eligible player IDs

        Returns:
            Player ID to freeze
        """
        # If I have a good score, freeze myself to bank it
        if context.my_round_score >= self.target_score:
            return context.my_player_id

        # Otherwise, freeze opponent with highest total score
        opponent_ids = [
            opp.player_id for opp in context.opponents
            if opp.player_id in possible_targets
        ]

        # If no opponents available, freeze self
        if not opponent_ids:
            return context.my_player_id

        # Freeze opponent with highest total score
        opponent_scores = {
            opp.player_id: opp.total_score
            for opp in context.opponents
            if opp.player_id in opponent_ids
        }
        return max(opponent_scores.keys(), key=lambda pid: opponent_scores[pid])
    
    
    def opponent_can_win(self, context: StrategyContext) -> bool:
        """
        Look at opponent scores and decide whether this affects whether to hit or stay

        Strategy:
        - If an opponent is at 200+ then you should always hit
        - If an opponent is within your defined distance from 200 (and is active), then you will hit
            - This distance will default to 0 so if you don't specify it, then you will not have any effect from this
        
        Args:
            context: Complete game context

        Returns:
            True to HIT, False to STAY
        """

        for opponent in context.opponents:
            if opponent.total_score >= 200:
                return True
            if (not (opponent.has_stayed or opponent.is_busted)) and (opponent.total_score + opponent.round_score >= (200 - self.distance_from_200)):
                return True
        return False



