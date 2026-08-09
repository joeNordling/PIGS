"""
Probability-based threshold strategy for flip_7 simulation.

This strategy makes decisions based on calculated bust probability
rather than fixed score thresholds.
"""

from typing import List, Optional

from flip_7.data.models import NumberCard
from flip_7.simulation.strategy import BaseStrategy, StrategyContext


class ProbabilityThresholdStrategy(BaseStrategy):
    """
    Strategy that hits based on bust probability threshold.

    This strategy calculates the probability of busting (drawing a duplicate)
    on the next card, and only hits if the probability is below a threshold.
    More sophisticated than fixed score thresholds as it adapts to game state.

    Attributes:
        bust_probability_threshold: Maximum acceptable bust probability (0.0-1.0)
        min_score_threshold: Minimum round score before bust risk alone is
            enough to stay/freeze self — below this, keep hitting regardless
            of risk since there's not much worth banking yet.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        bust_probability_threshold: float = 0.20,
        min_score_threshold: int = 20
    ):
        """
        Initialize probability threshold strategy.

        Args:
            name: Optional custom name
            bust_probability_threshold: Max bust probability to accept (default: 0.20 = 20%)
            min_score_threshold: Minimum round score to consider banking at (default: 20)

        Raises:
            ValueError: If bust_probability_threshold not in [0.0, 1.0]
        """
        if not 0.0 <= bust_probability_threshold <= 1.0:
            raise ValueError(
                f"bust_probability_threshold must be between 0.0 and 1.0, "
                f"got {bust_probability_threshold}"
            )

        if name is None:
            # Format as percentage for readability
            pct = int(bust_probability_threshold * 100)
            name = f"ProbThreshold({pct}%)"

        super().__init__(name)
        self.bust_probability_threshold = bust_probability_threshold
        self.min_score_threshold = min_score_threshold

    def decide_hit_or_stay(self, context: StrategyContext) -> bool:
        """
        Decide whether to hit or stay based on bust probability.

        Decision logic:
        1. If flip_three active, must hit (no choice)
        2. If already won (total_score >= 200), stay
        3. Calculate bust probability using visible cards
        4. Hit if bust_probability < threshold AND haven't reached min_score
        5. Otherwise, stay

        Args:
            context: Complete game context

        Returns:
            True to HIT, False to STAY
        """
        # If flip_three is active, must hit
        if context.my_flip_three_active and context.my_flip_three_count > 0:
            return True

        # If already won, stay
        if context.my_total_score >= 200:
            return False

        # Calculate bust probability
        bust_probability = self._calculate_bust_probability(context)

        # Only stay if the risk is high AND there's a worthwhile score to bank —
        # otherwise keep hitting even under high risk, since there's nothing to protect yet.
        should_stay = (
            bust_probability >= self.bust_probability_threshold
            and context.my_round_score >= self.min_score_threshold
        )
        return not should_stay

    def _calculate_bust_probability(self, context: StrategyContext) -> float:
        """
        Calculate probability of busting on next card draw.

        Uses the context's helper method to calculate duplicate probabilities
        for each number value in hand, then returns the maximum probability
        (worst case for any single value).

        Args:
            context: Game context with visible cards and hand information

        Returns:
            Maximum bust probability across all number values in hand (0.0-1.0)
        """
        # Get duplicate probabilities for each value in hand
        dup_probs = context.calculate_duplicate_probability()

        # If no probabilities (no number cards in hand), bust probability is 0
        if not dup_probs:
            return 0.0

        # Return maximum probability (worst case)
        # This is conservative - we consider the highest risk
        return max(dup_probs.values())

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
        - If my bust probability is high AND I have decent score, freeze self (bank it)
        - Otherwise, freeze opponent with highest total score (prevent improvement)

        Args:
            context: Game context
            possible_targets: List of eligible player IDs

        Returns:
            Player ID to freeze
        """
        # Calculate current bust probability
        bust_prob = self._calculate_bust_probability(context)

        # If we have high bust risk and a worthwhile score to protect, freeze ourselves
        if bust_prob >= self.bust_probability_threshold and context.my_round_score >= self.min_score_threshold:
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
