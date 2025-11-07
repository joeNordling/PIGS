"""
Threshold-based strategy for flip_7 simulation.

This strategy hits until reaching a target score, then stays.
"""

from typing import List, Optional

from flip_7.data.models import NumberCard
from flip_7.simulation.strategy import BaseStrategy, StrategyContext


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
        target_score: int = 100
    ):
        """
        Initialize threshold strategy.

        Args:
            name: Optional custom name
            target_score: Score to reach before staying (default: 100)
        """
        if name is None:
            name = f"Threshold({target_score})"

        super().__init__(name)
        self.target_score = target_score

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
        return context.my_round_score < self.target_score

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
