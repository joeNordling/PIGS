"""
Random strategy for flip_7 simulation.

This strategy makes random decisions and serves as a baseline for comparison.
"""

import random
from typing import List, Optional

from flip_7.data.models import NumberCard
from flip_7.simulation.strategy import BaseStrategy, StrategyContext


class RandomStrategy(BaseStrategy):
    """
    Strategy that makes random hit/stay decisions.

    This serves as a baseline for comparing other strategies. It makes
    completely random choices without considering game state.

    Attributes:
        hit_probability: Probability of choosing HIT (0.0 to 1.0)
        seed: Optional random seed for reproducibility
    """

    def __init__(
        self,
        name: Optional[str] = None,
        hit_probability: float = 0.5,
        seed: Optional[int] = None
    ):
        """
        Initialize random strategy.

        Args:
            name: Optional custom name for this strategy
            hit_probability: Probability of hitting (default 0.5 = 50%)
            seed: Optional random seed for reproducibility
        """
        super().__init__(name or f"Random({hit_probability:.0%})")
        self.hit_probability = hit_probability
        self.rng = random.Random(seed)

    def decide_hit_or_stay(self, context: StrategyContext) -> bool:
        """
        Make a random hit/stay decision.

        Args:
            context: Game context (not used for random decisions)

        Returns:
            True to HIT with probability=hit_probability, False to STAY otherwise
        """
        # If flip_three is active, must hit (no choice)
        if context.my_flip_three_active and context.my_flip_three_count > 0:
            return True

        # Random decision based on hit_probability
        return self.rng.random() < self.hit_probability

    def decide_second_chance_discard(
        self,
        context: StrategyContext,
        duplicate_value: int,
        duplicate_cards: List[NumberCard]
    ) -> NumberCard:
        """
        Randomly choose which duplicate to discard.

        Args:
            context: Game context (not used)
            duplicate_value: The duplicated value
            duplicate_cards: List of duplicate cards (should be exactly 2)

        Returns:
            Randomly selected card from duplicate_cards
        """
        return self.rng.choice(duplicate_cards)

    def decide_flip_three_target(
        self,
        context: StrategyContext,
        possible_targets: List[str]
    ) -> str:
        """
        Randomly choose who receives the Flip Three effect.

        Args:
            context: Game context (not used)
            possible_targets: List of eligible player IDs

        Returns:
            Randomly selected player ID from possible_targets
        """
        return self.rng.choice(possible_targets)

    def decide_freeze_target(
        self,
        context: StrategyContext,
        possible_targets: List[str]
    ) -> str:
        """
        Randomly choose who gets frozen.

        Args:
            context: Game context (not used)
            possible_targets: List of eligible player IDs

        Returns:
            Randomly selected player ID from possible_targets
        """
        return self.rng.choice(possible_targets)
