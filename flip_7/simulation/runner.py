"""
Simulation runner for automated flip_7 gameplay.

This module orchestrates large-scale game simulations with different strategies.
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from flip_7.core.engine import GameEngine
from flip_7.core.rules import check_for_duplicate_cards
from flip_7.data.models import (
    GameState, PlayerState, NumberCard, ActionCard,
    ActionType, Card
)
from flip_7.simulation.strategy import (
    BaseStrategy, StrategyContext, OpponentInfo, DeckStatistics
)


@dataclass
class GameResult:
    """
    Results from a single simulated game.

    Attributes:
        game_id: Unique game identifier
        winner_id: ID of winning player
        winner_strategy: Name of winning strategy
        total_rounds: Number of rounds played
        player_results: Per-player statistics
        final_scores: Final scores for each player
    """
    game_id: str
    winner_id: str
    winner_strategy: str
    total_rounds: int
    player_results: Dict[str, 'PlayerResult']
    final_scores: Dict[str, int]


@dataclass
class PlayerResult:
    """
    Results for a single player in a game.

    Attributes:
        player_id: Player identifier
        player_name: Player name
        strategy_name: Strategy used
        final_score: Final total score
        rounds_played: Number of rounds
        rounds_won: Number of rounds won
        flip_7_count: Times achieved Flip 7 bonus
        bust_count: Times busted
        cards_drawn: Total cards drawn
        avg_round_score: Average score per round
    """
    player_id: str
    player_name: str
    strategy_name: str
    final_score: int
    rounds_played: int
    rounds_won: int
    flip_7_count: int
    bust_count: int
    cards_drawn: int
    avg_round_score: float


@dataclass
class SimulationResults:
    """
    Aggregate results from multiple games.

    Attributes:
        total_games: Number of games simulated
        game_results: List of individual game results
        strategy_stats: Performance statistics per strategy
    """
    total_games: int
    game_results: List[GameResult]
    strategy_stats: Dict[str, 'StrategyStats'] = field(default_factory=dict)


@dataclass
class StrategyStats:
    """
    Aggregate statistics for a strategy across multiple games.

    Attributes:
        strategy_name: Name of the strategy
        games_played: Total games
        wins: Number of wins
        win_rate: Percentage of games won
        avg_score: Average final score
        avg_rounds: Average rounds per game
        total_flip_7s: Total Flip 7 bonuses achieved
        total_busts: Total busts
    """
    strategy_name: str
    games_played: int = 0
    wins: int = 0
    win_rate: float = 0.0
    avg_score: float = 0.0
    avg_rounds: float = 0.0
    total_flip_7s: int = 0
    total_busts: int = 0


class SimulationRunner:
    """
    Orchestrates automated flip_7 game simulations with AI strategies.

    This class manages the complete simulation pipeline:
    - Initializing games with strategy assignments
    - Running game loops with automated decision-making
    - Collecting statistics from completed games
    - Supporting batch execution of hundreds of thousands of games

    Example usage:
        strategies = [RandomStrategy(), ThresholdStrategy(target_score=100)]
        runner = SimulationRunner(strategies, num_players=2)
        results = runner.run_simulation(num_games=10000)
        print(f"Win rate: {results.strategy_stats['Random'].win_rate:.1%}")
    """

    def __init__(
        self,
        strategies: List[BaseStrategy],
        num_players: Optional[int] = None,
        seed: Optional[int] = None,
        verbose: bool = False
    ):
        """
        Initialize simulation runner.

        Args:
            strategies: List of strategies to test
            num_players: Number of players per game (default: len(strategies))
            seed: Random seed for reproducibility
            verbose: Print progress during simulation
        """
        self.strategies = strategies
        self.num_players = num_players or len(strategies)
        self.seed = seed
        self.verbose = verbose
        self.rng = random.Random(seed)

        if self.num_players < 2:
            raise ValueError("Need at least 2 players")

        if self.num_players > len(strategies):
            raise ValueError(
                f"Not enough strategies ({len(strategies)}) for "
                f"{self.num_players} players"
            )

    def run_simulation(
        self,
        num_games: int,
        progress_callback: Optional[callable] = None,
        show_progress: bool = False
    ) -> SimulationResults:
        """
        Run a batch of simulated games.

        Args:
            num_games: Number of games to simulate
            progress_callback: Optional callback(current, total) for progress tracking
            show_progress: If True, display a tqdm progress bar (requires tqdm)

        Returns:
            Aggregate results from all games
        """
        game_results = []

        # Set up progress bar if requested
        pbar = None
        if show_progress:
            try:
                # Try to import tqdm.notebook first (for Jupyter)
                try:
                    from tqdm.notebook import tqdm
                except ImportError:
                    # Fall back to regular tqdm
                    from tqdm import tqdm
                pbar = tqdm(total=num_games, desc="Simulating games")
            except ImportError:
                print("Warning: tqdm not installed. Install with: pip install tqdm")
                show_progress = False

        for i in range(num_games):
            result = self._run_single_game()
            game_results.append(result)

            if self.verbose and (i + 1) % 100 == 0:
                print(f"Completed {i + 1}/{num_games} games...")

            if progress_callback:
                progress_callback(i + 1, num_games)

            if pbar:
                pbar.update(1)

        if pbar:
            pbar.close()

        # Calculate aggregate statistics
        results = SimulationResults(
            total_games=num_games,
            game_results=game_results
        )
        results.strategy_stats = self._calculate_aggregate_stats(game_results)

        return results

    def _run_single_game(self) -> GameResult:
        """
        Run a single automated game.

        Returns:
            Results from the completed game
        """
        # Select strategies for this game (random assignment if more strategies than players)
        selected_strategies = self.rng.sample(self.strategies, self.num_players)

        # Create player names with strategy names
        player_names = [
            f"Player_{i+1}_{strat.name}"
            for i, strat in enumerate(selected_strategies)
        ]

        # Map player IDs to strategies (will be set after game start)
        strategy_map: Dict[str, BaseStrategy] = {}

        # Initialize game
        engine = GameEngine()
        game_state = engine.start_new_game(player_names)

        # Map players to strategies
        for player, strategy in zip(game_state.players, selected_strategies):
            strategy_map[player.player_id] = strategy
            strategy.on_game_start(game_state, player.player_id)

        # Play until game ends
        while not game_state.is_complete:
            # Start new round
            engine.start_new_round()

            # Notify strategies of round start
            for player in game_state.players:
                strategy_map[player.player_id].on_round_start(
                    game_state,
                    player.player_id
                )

            # Play the round
            self._play_round(engine, game_state, strategy_map)

        # Collect results
        return self._collect_game_results(game_state, strategy_map)

    def _play_round(
        self,
        engine: GameEngine,
        game_state: GameState,
        strategy_map: Dict[str, BaseStrategy]
    ) -> None:
        """
        Play a single round with automated strategy decisions.

        Args:
            engine: Game engine
            game_state: Current game state
            strategy_map: Mapping of player IDs to strategies
        """
        round_state = game_state.current_round
        if round_state is None:
            return

        # Continue until round ends
        max_iterations = 1000  # Safety limit to prevent infinite loops
        iteration = 0

        while not round_state.is_complete and iteration < max_iterations:
            iteration += 1

            # Check each player for their turn
            for player in game_state.players:
                player_id = player.player_id
                player_state = round_state.player_states[player_id]

                # Skip if player has stayed or busted
                if player_state.has_stayed or player_state.is_busted:
                    continue

                # Get strategy for this player
                strategy = strategy_map[player_id]

                # Check if player must hit (flip_three active)
                must_hit = (
                    player_state.flip_three_active and
                    player_state.flip_three_count > 0
                )

                # Ask strategy for decision (if not forced to hit)
                if not must_hit:
                    context = self._create_strategy_context(
                        game_state,
                        player_id
                    )
                    should_hit = strategy.decide_hit_or_stay(context)

                    if not should_hit:
                        # Player chooses to stay
                        engine.player_stay(player_id)
                        continue

                # Draw a card from the deck
                if len(game_state.deck) == 0:
                    # No cards left, round must end
                    if not round_state.is_complete:
                        engine.end_round()
                    break

                card = game_state.deck[0]  # Peek at next card

                # Deal the card
                engine.deal_card_to_player(player_id, card)

                # Handle action cards - let strategy decide target
                if isinstance(card, ActionCard):
                    # Refresh game state reference after dealing
                    game_state = engine.game_state

                    # Check if round ended
                    if game_state.current_round is None:
                        # Round ended (e.g., freeze applied)
                        break

                    # Get fresh references
                    round_state = game_state.current_round
                    dealer_state = round_state.player_states[player_id]

                    # Get list of active players who can receive action card effects
                    possible_targets = [
                        pid for pid, pstate in round_state.player_states.items()
                        if not pstate.has_stayed
                    ]

                    target_id = None

                    if card.action_type == ActionType.SECOND_CHANCE:
                        # Second Chance logic:
                        # First one: auto-keep
                        # Second one (while holding first): must give to opponent
                        if not dealer_state.has_second_chance:
                            # First Second Chance: automatically keep it
                            target_id = player_id
                        else:
                            # Already has one: must give to opponent
                            opponent_targets = [pid for pid in possible_targets if pid != player_id]
                            if opponent_targets:
                                # Give to first available opponent (could make this strategic)
                                target_id = opponent_targets[0]
                            else:
                                # No opponents available - can't apply this Second Chance
                                # This can happen if all opponents have already stayed/busted
                                # Just skip applying it (card stays in hand but has no effect)
                                target_id = None

                    elif card.action_type == ActionType.FLIP_THREE:
                        # Ask strategy who should receive Flip Three
                        context = self._create_strategy_context(game_state, player_id)
                        target_id = strategy.decide_flip_three_target(context, possible_targets)

                    elif card.action_type == ActionType.FREEZE:
                        # Ask strategy who should be frozen
                        context = self._create_strategy_context(game_state, player_id)
                        target_id = strategy.decide_freeze_target(context, possible_targets)

                    # Apply the action card effect to the chosen target
                    if target_id:
                        engine.apply_action_card_effect(card, target_id, original_player_id=player_id)

                # Refresh player state after card dealt
                if game_state.current_round is None:
                    # Round ended (e.g., freeze applied)
                    break

                player_state = game_state.current_round.player_states[player_id]

                # Check if Second Chance is needed
                if check_for_duplicate_cards(player_state.cards_in_hand):
                    if player_state.has_second_chance:
                        # Ask strategy which duplicate to discard
                        duplicates = self._find_duplicate_cards(
                            player_state.cards_in_hand
                        )

                        if duplicates:
                            duplicate_value, duplicate_cards = duplicates[0]
                            context = self._create_strategy_context(
                                game_state,
                                player_id
                            )

                            card_to_discard = strategy.decide_second_chance_discard(
                                context,
                                duplicate_value,
                                duplicate_cards
                            )

                            engine.use_second_chance(player_id, card_to_discard)

            # Check if round should end
            if round_state.is_complete:
                break

        # If round didn't naturally end, force it to end
        if not round_state.is_complete:
            engine.end_round()

        # Notify strategies of round end
        for player in game_state.players:
            strategy_map[player.player_id].on_round_end(
                game_state,
                player.player_id
            )

    def _create_strategy_context(
        self,
        game_state: GameState,
        player_id: str
    ) -> StrategyContext:
        """
        Create a strategy context for decision-making.

        Args:
            game_state: Current game state
            player_id: ID of player making decision

        Returns:
            Context object with all decision-making information
        """
        round_state = game_state.current_round
        player_state = round_state.player_states[player_id]

        # Gather opponent information
        opponents = []
        for pid, ps in round_state.player_states.items():
            if pid != player_id:
                opponents.append(OpponentInfo(
                    player_id=pid,
                    name=ps.name,
                    total_score=ps.total_score,
                    round_score=ps.round_score,
                    has_stayed=ps.has_stayed,
                    is_busted=ps.is_busted,
                    card_count=len(ps.cards_in_hand)
                ))

        # Gather visible cards (all cards that have been played)
        visible_cards = []

        # Cards in discard pile
        visible_cards.extend(game_state.discard_pile)

        # Cards in all players' hands (full visibility for simulation)
        for ps in round_state.player_states.values():
            visible_cards.extend(ps.cards_in_hand)

        # Create deck statistics
        deck_stats = DeckStatistics(
            cards_remaining=len(game_state.deck),
            cards_in_discard=len(game_state.discard_pile),
            visible_cards=visible_cards
        )

        # Create context
        return StrategyContext(
            my_player_id=player_id,
            my_cards=player_state.cards_in_hand.copy(),
            my_round_score=player_state.round_score,
            my_total_score=player_state.total_score,
            my_has_stayed=player_state.has_stayed,
            my_is_busted=player_state.is_busted,
            my_has_second_chance=player_state.has_second_chance,
            my_flip_three_active=player_state.flip_three_active,
            my_flip_three_count=player_state.flip_three_count,
            opponents=opponents,
            deck_stats=deck_stats,
            round_number=round_state.round_number
        )

    def _find_duplicate_cards(
        self,
        cards: List[Card]
    ) -> List[Tuple[int, List[NumberCard]]]:
        """
        Find duplicate number cards in hand.

        Args:
            cards: List of cards to check

        Returns:
            List of (value, [duplicate_cards]) tuples
        """
        number_cards = [c for c in cards if isinstance(c, NumberCard)]
        value_groups = defaultdict(list)

        for card in number_cards:
            value_groups[card.value].append(card)

        duplicates = [
            (value, cards)
            for value, cards in value_groups.items()
            if len(cards) >= 2
        ]

        return duplicates

    def _collect_game_results(
        self,
        game_state: GameState,
        strategy_map: Dict[str, BaseStrategy]
    ) -> GameResult:
        """
        Collect results from a completed game.

        Args:
            game_state: Final game state
            strategy_map: Player ID to strategy mapping

        Returns:
            Game result summary
        """
        # Get final round
        last_round = game_state.round_history[-1]

        # Collect per-player results
        player_results = {}

        for player in game_state.players:
            player_id = player.player_id
            strategy = strategy_map[player_id]

            # Calculate statistics across all rounds
            total_flip_7s = 0
            total_busts = 0
            total_cards = 0
            rounds_won = 0
            round_scores = []

            for round_state in game_state.round_history:
                ps = round_state.player_states[player_id]

                # Count stats
                total_cards += len(ps.cards_in_hand)
                if ps.is_busted:
                    total_busts += 1
                if player_id in round_state.winner_ids:
                    rounds_won += 1

                round_scores.append(ps.round_score)

                # Check for flip 7 (would need score breakdown, approximate for now)
                num_cards = sum(
                    1 for c in ps.cards_in_hand if isinstance(c, NumberCard)
                )
                if num_cards == 7:
                    total_flip_7s += 1

            final_score = last_round.player_states[player_id].total_score
            avg_round_score = (
                sum(round_scores) / len(round_scores) if round_scores else 0
            )

            player_results[player_id] = PlayerResult(
                player_id=player_id,
                player_name=player.name,
                strategy_name=strategy.name,
                final_score=final_score,
                rounds_played=len(game_state.round_history),
                rounds_won=rounds_won,
                flip_7_count=total_flip_7s,
                bust_count=total_busts,
                cards_drawn=total_cards,
                avg_round_score=avg_round_score
            )

        # Get winner
        winner_id = game_state.winner_id
        winner_strategy = strategy_map[winner_id].name

        final_scores = {
            pid: ps.total_score
            for pid, ps in last_round.player_states.items()
        }

        return GameResult(
            game_id=game_state.game_id,
            winner_id=winner_id,
            winner_strategy=winner_strategy,
            total_rounds=len(game_state.round_history),
            player_results=player_results,
            final_scores=final_scores
        )

    def _calculate_aggregate_stats(
        self,
        game_results: List[GameResult]
    ) -> Dict[str, StrategyStats]:
        """
        Calculate aggregate statistics across all games.

        Args:
            game_results: List of game results

        Returns:
            Dictionary mapping strategy names to their statistics
        """
        stats_by_strategy = defaultdict(lambda: StrategyStats(strategy_name=""))

        # Collect stats per strategy
        for game in game_results:
            for player_result in game.player_results.values():
                strategy_name = player_result.strategy_name
                stats = stats_by_strategy[strategy_name]

                stats.strategy_name = strategy_name
                stats.games_played += 1

                if player_result.player_id == game.winner_id:
                    stats.wins += 1

                stats.avg_score += player_result.final_score
                stats.avg_rounds += player_result.rounds_played
                stats.total_flip_7s += player_result.flip_7_count
                stats.total_busts += player_result.bust_count

        # Calculate averages
        for strategy_name, stats in stats_by_strategy.items():
            if stats.games_played > 0:
                stats.win_rate = stats.wins / stats.games_played
                stats.avg_score /= stats.games_played
                stats.avg_rounds /= stats.games_played

        return dict(stats_by_strategy)
