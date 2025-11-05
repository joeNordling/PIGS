"""
Statistics calculation and tracking for Flip 7.

This module provides rich analytics on game data including:
- Per-player statistics
- Game-wide metrics
- Historical trends
- Leaderboards
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict, Counter

from flip_7.data.models import (
    GameState, RoundState, PlayerState,
    NumberCard, ActionCard, ModifierCard,
    CardType
)
from flip_7.data.events import EventLogger, EventType


# ============================================================================
# Statistics Data Classes
# ============================================================================

@dataclass
class PlayerStatistics:
    """
    Statistics for a single player across multiple games.

    Attributes:
        player_name: Name of the player
        games_played: Total games participated in
        games_won: Total games won
        win_rate: Percentage of games won (0-100)
        total_rounds: Total rounds played
        average_score_per_round: Average score per round
        average_score_per_game: Average final score per game
        flip_7_count: Number of times Flip 7 was achieved
        flip_7_rate: Percentage of rounds with Flip 7 (0-100)
        bust_count: Number of times busted
        bust_rate: Percentage of rounds busted (0-100)
        highest_round_score: Highest score in a single round
        highest_game_score: Highest final score in a game
    """
    player_name: str
    games_played: int = 0
    games_won: int = 0
    win_rate: float = 0.0
    total_rounds: int = 0
    average_score_per_round: float = 0.0
    average_score_per_game: float = 0.0
    flip_7_count: int = 0
    flip_7_rate: float = 0.0
    bust_count: int = 0
    bust_rate: float = 0.0
    highest_round_score: int = 0
    highest_game_score: int = 0


@dataclass
class GameStatistics:
    """
    Statistics for a single game.

    Attributes:
        game_id: ID of the game
        total_rounds: Number of rounds played
        total_cards_dealt: Total cards dealt across all rounds
        flip_7_count: Number of Flip 7s achieved
        bust_count: Number of busts
        winner_name: Name of the winner
        winner_score: Final score of the winner
        average_round_score: Average score per round across all players
        card_frequency: Count of each type of card dealt
    """
    game_id: str
    total_rounds: int = 0
    total_cards_dealt: int = 0
    flip_7_count: int = 0
    bust_count: int = 0
    winner_name: str = ""
    winner_score: int = 0
    average_round_score: float = 0.0
    card_frequency: Dict[str, int] = field(default_factory=dict)


@dataclass
class HistoricalStatistics:
    """
    Aggregate statistics across all games.

    Attributes:
        total_games: Total number of games
        total_rounds: Total number of rounds across all games
        total_cards_dealt: Total cards dealt
        average_rounds_per_game: Average number of rounds per game
        average_game_duration: Average number of rounds to complete a game
        flip_7_total: Total Flip 7 achievements
        flip_7_percentage: Percentage of rounds with Flip 7
        bust_total: Total busts
        bust_percentage: Percentage of rounds with busts
        most_common_winner: Player with most wins
        highest_score_ever: Highest final score achieved
        card_distribution: Frequency of each card type dealt
    """
    total_games: int = 0
    total_rounds: int = 0
    total_cards_dealt: int = 0
    average_rounds_per_game: float = 0.0
    flip_7_total: int = 0
    flip_7_percentage: float = 0.0
    bust_total: int = 0
    bust_percentage: float = 0.0
    most_common_winner: str = ""
    highest_score_ever: int = 0
    card_distribution: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# Statistics Calculator
# ============================================================================

class StatisticsCalculator:
    """
    Calculates statistics from game data.

    This class provides methods to analyze single games, player performance,
    and historical trends.
    """

    @staticmethod
    def calculate_game_stats(game_state: GameState) -> GameStatistics:
        """
        Calculate statistics for a single game.

        Args:
            game_state: The game to analyze

        Returns:
            GameStatistics for the game
        """
        if not game_state.is_complete:
            raise ValueError("Game must be complete to calculate full statistics")

        stats = GameStatistics(game_id=game_state.game_id)
        stats.total_rounds = len(game_state.round_history)

        # Analyze all rounds
        total_round_scores = []
        all_cards = []

        for round_state in game_state.round_history:
            for player_state in round_state.player_states.values():
                total_round_scores.append(player_state.round_score)
                all_cards.extend(player_state.cards_in_hand)

                # Count Flip 7s
                number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]
                if len(number_cards) == 7:
                    stats.flip_7_count += 1

                # Count busts
                if player_state.is_busted:
                    stats.bust_count += 1

        stats.total_cards_dealt = len(all_cards)
        stats.average_round_score = (
            sum(total_round_scores) / len(total_round_scores)
            if total_round_scores else 0.0
        )

        # Card frequency
        card_type_counts = Counter()
        for card in all_cards:
            if isinstance(card, NumberCard):
                card_type_counts[f"Number {card.value}"] += 1
            elif isinstance(card, ActionCard):
                card_type_counts[f"Action: {card.action_type.value}"] += 1
            elif isinstance(card, ModifierCard):
                card_type_counts[f"Modifier: {card.modifier_type.value}"] += 1

        stats.card_frequency = dict(card_type_counts)

        # Winner info
        if game_state.winner_id:
            winner = next(p for p in game_state.players if p.player_id == game_state.winner_id)
            stats.winner_name = winner.name

            # Get winner's final score from last round
            last_round = game_state.round_history[-1]
            winner_state = last_round.player_states[game_state.winner_id]
            stats.winner_score = winner_state.total_score

        return stats

    @staticmethod
    def calculate_player_stats(
        player_name: str,
        games: List[GameState]
    ) -> PlayerStatistics:
        """
        Calculate statistics for a specific player across multiple games.

        Args:
            player_name: Name of the player to analyze
            games: List of completed games to analyze

        Returns:
            PlayerStatistics for the player
        """
        stats = PlayerStatistics(player_name=player_name)

        round_scores = []
        game_scores = []
        flip_7_rounds = 0
        total_rounds = 0
        bust_count = 0

        for game in games:
            if not game.is_complete:
                continue

            # Find this player in the game
            player = next((p for p in game.players if p.name == player_name), None)
            if not player:
                continue

            stats.games_played += 1

            # Check if won
            if game.winner_id == player.player_id:
                stats.games_won += 1

            # Analyze all rounds
            for round_state in game.round_history:
                if player.player_id not in round_state.player_states:
                    continue

                player_state = round_state.player_states[player.player_id]
                total_rounds += 1

                round_scores.append(player_state.round_score)

                # Check Flip 7
                number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]
                if len(number_cards) == 7:
                    flip_7_rounds += 1

                # Check bust
                if player_state.is_busted:
                    bust_count += 1

                # Track highest round score
                if player_state.round_score > stats.highest_round_score:
                    stats.highest_round_score = player_state.round_score

            # Get final game score
            if game.round_history:
                last_round = game.round_history[-1]
                if player.player_id in last_round.player_states:
                    final_score = last_round.player_states[player.player_id].total_score
                    game_scores.append(final_score)

                    if final_score > stats.highest_game_score:
                        stats.highest_game_score = final_score

        # Calculate rates and averages
        stats.total_rounds = total_rounds
        stats.flip_7_count = flip_7_rounds
        stats.bust_count = bust_count

        if stats.games_played > 0:
            stats.win_rate = (stats.games_won / stats.games_played) * 100

        if total_rounds > 0:
            stats.average_score_per_round = sum(round_scores) / len(round_scores) if round_scores else 0.0
            stats.flip_7_rate = (flip_7_rounds / total_rounds) * 100
            stats.bust_rate = (bust_count / total_rounds) * 100

        if game_scores:
            stats.average_score_per_game = sum(game_scores) / len(game_scores)

        return stats

    @staticmethod
    def calculate_historical_stats(games: List[GameState]) -> HistoricalStatistics:
        """
        Calculate aggregate statistics across all games.

        Args:
            games: List of completed games to analyze

        Returns:
            HistoricalStatistics across all games
        """
        stats = HistoricalStatistics()

        completed_games = [g for g in games if g.is_complete]
        stats.total_games = len(completed_games)

        if stats.total_games == 0:
            return stats

        winner_counts = Counter()
        total_rounds = 0
        total_cards = 0
        flip_7_count = 0
        bust_count = 0
        total_player_rounds = 0
        all_card_types = Counter()

        for game in completed_games:
            total_rounds += len(game.round_history)

            # Count winner
            if game.winner_id:
                winner = next(p for p in game.players if p.player_id == game.winner_id)
                winner_counts[winner.name] += 1

            # Analyze rounds
            for round_state in game.round_history:
                for player_state in round_state.player_states.values():
                    total_player_rounds += 1
                    total_cards += len(player_state.cards_in_hand)

                    # Count Flip 7
                    number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]
                    if len(number_cards) == 7:
                        flip_7_count += 1

                    # Count bust
                    if player_state.is_busted:
                        bust_count += 1

                    # Track highest score
                    if player_state.total_score > stats.highest_score_ever:
                        stats.highest_score_ever = player_state.total_score

                    # Count card types
                    for card in player_state.cards_in_hand:
                        if isinstance(card, NumberCard):
                            all_card_types[f"Number {card.value}"] += 1
                        elif isinstance(card, ActionCard):
                            all_card_types[f"Action: {card.action_type.value}"] += 1
                        elif isinstance(card, ModifierCard):
                            all_card_types[f"Modifier: {card.modifier_type.value}"] += 1

        stats.total_rounds = total_rounds
        stats.total_cards_dealt = total_cards
        stats.average_rounds_per_game = total_rounds / stats.total_games
        stats.flip_7_total = flip_7_count
        stats.bust_total = bust_count

        if total_player_rounds > 0:
            stats.flip_7_percentage = (flip_7_count / total_player_rounds) * 100
            stats.bust_percentage = (bust_count / total_player_rounds) * 100

        if winner_counts:
            stats.most_common_winner = winner_counts.most_common(1)[0][0]

        stats.card_distribution = dict(all_card_types)

        return stats

    @staticmethod
    def get_leaderboard(games: List[GameState]) -> List[PlayerStatistics]:
        """
        Generate a leaderboard of all players sorted by win rate.

        Args:
            games: List of completed games

        Returns:
            List of PlayerStatistics sorted by win rate (descending)
        """
        # Collect all unique player names
        player_names = set()
        for game in games:
            for player in game.players:
                player_names.add(player.name)

        # Calculate stats for each player
        leaderboard = []
        for name in player_names:
            stats = StatisticsCalculator.calculate_player_stats(name, games)
            leaderboard.append(stats)

        # Sort by win rate (descending), then by games won
        leaderboard.sort(
            key=lambda s: (s.win_rate, s.games_won),
            reverse=True
        )

        return leaderboard

    @staticmethod
    def analyze_event_log(event_logger: EventLogger) -> Dict[str, any]:
        """
        Analyze an event log to extract insights.

        Args:
            event_logger: The event log to analyze

        Returns:
            Dictionary with event-based insights
        """
        insights = {
            "total_events": len(event_logger.events),
            "event_type_counts": {},
            "cards_dealt": 0,
            "player_actions": defaultdict(int),
            "action_cards_triggered": 0
        }

        event_type_counts = Counter()

        for event in event_logger.events:
            event_type_counts[event.event_type.value] += 1

            if event.event_type == EventType.CARD_DEALT:
                insights["cards_dealt"] += 1

            if event.event_type == EventType.ACTION_CARD_APPLIED:
                insights["action_cards_triggered"] += 1

            if hasattr(event, 'player_name'):
                insights["player_actions"][event.player_name] += 1

        insights["event_type_counts"] = dict(event_type_counts)

        return insights
