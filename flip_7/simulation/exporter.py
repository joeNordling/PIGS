"""
Data export functionality for simulation results.

This module provides export capabilities for simulation data in both
CSV (for quick statistical analysis) and JSON (for detailed exploration).
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from flip_7.simulation.runner import SimulationResults, GameResult, PlayerResult


class SimulationExporter:
    """
    Exports simulation results to CSV and JSON formats.

    CSV format is optimized for pandas DataFrame loading and quick statistical
    analysis. JSON format preserves full game details for deep exploration.

    Example usage:
        exporter = SimulationExporter(output_dir="simulation_results")
        exporter.export_csv(results, "baseline_comparison")
        exporter.export_json(results, "baseline_comparison")
    """

    def __init__(self, output_dir: str = "simulation_results"):
        """
        Initialize exporter.

        Args:
            output_dir: Directory for output files (created if doesn't exist)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(
        self,
        results: SimulationResults,
        filename_prefix: str,
        include_timestamp: bool = True
    ) -> Path:
        """
        Export simulation results to CSV format.

        Creates a flattened CSV with one row per player per game,
        suitable for pandas analysis.

        Args:
            results: Simulation results to export
            filename_prefix: Prefix for filename
            include_timestamp: Whether to append timestamp to filename

        Returns:
            Path to created CSV file
        """
        # Build filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if include_timestamp:
            filename = f"{filename_prefix}_{timestamp}.csv"
        else:
            filename = f"{filename_prefix}.csv"

        filepath = self.output_dir / filename

        # Prepare rows (one per player per game)
        rows = []

        for game in results.game_results:
            for player_id, player_result in game.player_results.items():
                row = {
                    # Game identifiers
                    "game_id": game.game_id,
                    "total_rounds": game.total_rounds,

                    # Player identifiers
                    "player_id": player_id,
                    "player_name": player_result.player_name,
                    "strategy": player_result.strategy_name,

                    # Outcomes
                    "won_game": 1 if player_id == game.winner_id else 0,
                    "final_score": player_result.final_score,

                    # Performance metrics
                    "rounds_played": player_result.rounds_played,
                    "rounds_won": player_result.rounds_won,
                    "flip_7_count": player_result.flip_7_count,
                    "bust_count": player_result.bust_count,
                    "cards_drawn": player_result.cards_drawn,
                    "avg_round_score": round(player_result.avg_round_score, 2),

                    # Winner info (for convenience)
                    "winning_strategy": game.winner_strategy,
                }
                rows.append(row)

        # Write CSV
        if rows:
            fieldnames = rows[0].keys()
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        return filepath

    def export_json(
        self,
        results: SimulationResults,
        filename_prefix: str,
        include_timestamp: bool = True,
        pretty: bool = True
    ) -> Path:
        """
        Export simulation results to JSON format.

        Creates a detailed JSON file with complete game information,
        suitable for deep analysis and debugging.

        Args:
            results: Simulation results to export
            filename_prefix: Prefix for filename
            include_timestamp: Whether to append timestamp to filename
            pretty: Whether to pretty-print JSON (readable but larger)

        Returns:
            Path to created JSON file
        """
        # Build filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if include_timestamp:
            filename = f"{filename_prefix}_{timestamp}.json"
        else:
            filename = f"{filename_prefix}.json"

        filepath = self.output_dir / filename

        # Convert results to JSON-serializable format
        data = {
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "total_games": results.total_games,
            },

            "strategy_statistics": {
                name: {
                    "strategy_name": stats.strategy_name,
                    "games_played": stats.games_played,
                    "wins": stats.wins,
                    "win_rate": round(stats.win_rate, 4),
                    "avg_score": round(stats.avg_score, 2),
                    "avg_rounds": round(stats.avg_rounds, 2),
                    "total_flip_7s": stats.total_flip_7s,
                    "total_busts": stats.total_busts,
                }
                for name, stats in results.strategy_stats.items()
            },

            "games": [
                {
                    "game_id": game.game_id,
                    "winner_id": game.winner_id,
                    "winner_strategy": game.winner_strategy,
                    "total_rounds": game.total_rounds,
                    "final_scores": game.final_scores,

                    "players": {
                        player_id: {
                            "player_name": pr.player_name,
                            "strategy_name": pr.strategy_name,
                            "final_score": pr.final_score,
                            "rounds_played": pr.rounds_played,
                            "rounds_won": pr.rounds_won,
                            "flip_7_count": pr.flip_7_count,
                            "bust_count": pr.bust_count,
                            "cards_drawn": pr.cards_drawn,
                            "avg_round_score": round(pr.avg_round_score, 2),
                        }
                        for player_id, pr in game.player_results.items()
                    }
                }
                for game in results.game_results
            ]
        }

        # Write JSON
        with open(filepath, 'w') as f:
            if pretty:
                json.dump(data, f, indent=2)
            else:
                json.dump(data, f)

        return filepath

    def export_summary(
        self,
        results: SimulationResults,
        filename_prefix: str = "summary",
        include_timestamp: bool = True
    ) -> Path:
        """
        Export a human-readable summary of simulation results.

        Creates a text file with aggregate statistics and performance
        comparisons between strategies.

        Args:
            results: Simulation results to export
            filename_prefix: Prefix for filename
            include_timestamp: Whether to append timestamp to filename

        Returns:
            Path to created summary file
        """
        # Build filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if include_timestamp:
            filename = f"{filename_prefix}_{timestamp}.txt"
        else:
            filename = f"{filename_prefix}.txt"

        filepath = self.output_dir / filename

        # Build summary content
        lines = []
        lines.append("=" * 70)
        lines.append(f"FLIP 7 SIMULATION SUMMARY")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"Total Games Simulated: {results.total_games:,}")
        lines.append("")

        # Strategy performance table
        lines.append("STRATEGY PERFORMANCE")
        lines.append("-" * 70)
        lines.append(
            f"{'Strategy':<25} {'Games':>8} {'Wins':>8} {'Win Rate':>10} "
            f"{'Avg Score':>10}"
        )
        lines.append("-" * 70)

        # Sort strategies by win rate
        sorted_stats = sorted(
            results.strategy_stats.values(),
            key=lambda s: s.win_rate,
            reverse=True
        )

        for stats in sorted_stats:
            lines.append(
                f"{stats.strategy_name:<25} "
                f"{stats.games_played:>8,} "
                f"{stats.wins:>8,} "
                f"{stats.win_rate:>9.1%} "
                f"{stats.avg_score:>10.1f}"
            )

        lines.append("-" * 70)
        lines.append("")

        # Additional metrics
        lines.append("DETAILED METRICS")
        lines.append("-" * 70)
        lines.append(
            f"{'Strategy':<25} {'Avg Rounds':>12} "
            f"{'Flip 7s':>10} {'Busts':>8}"
        )
        lines.append("-" * 70)

        for stats in sorted_stats:
            lines.append(
                f"{stats.strategy_name:<25} "
                f"{stats.avg_rounds:>12.1f} "
                f"{stats.total_flip_7s:>10,} "
                f"{stats.total_busts:>8,}"
            )

        lines.append("-" * 70)
        lines.append("")

        # Head-to-head comparison (if 2 strategies)
        if len(results.strategy_stats) == 2:
            lines.append("HEAD-TO-HEAD COMPARISON")
            lines.append("-" * 70)

            strat_names = list(results.strategy_stats.keys())
            stats_a = results.strategy_stats[strat_names[0]]
            stats_b = results.strategy_stats[strat_names[1]]

            lines.append(f"{stats_a.strategy_name} vs {stats_b.strategy_name}")
            lines.append(f"  Win Rate: {stats_a.win_rate:.1%} vs {stats_b.win_rate:.1%}")
            lines.append(f"  Avg Score: {stats_a.avg_score:.1f} vs {stats_b.avg_score:.1f}")
            lines.append(f"  Flip 7 Rate: {stats_a.total_flip_7s/stats_a.games_played:.2f} vs "
                        f"{stats_b.total_flip_7s/stats_b.games_played:.2f} per game")
            lines.append(f"  Bust Rate: {stats_a.total_busts/stats_a.games_played:.2f} vs "
                        f"{stats_b.total_busts/stats_b.games_played:.2f} per game")
            lines.append("")

        lines.append("=" * 70)

        # Write summary
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))

        return filepath

    def export_all(
        self,
        results: SimulationResults,
        filename_prefix: str,
        include_timestamp: bool = True
    ) -> Dict[str, Path]:
        """
        Export results to all formats (CSV, JSON, summary).

        Args:
            results: Simulation results to export
            filename_prefix: Prefix for filenames
            include_timestamp: Whether to append timestamp to filenames

        Returns:
            Dictionary mapping format names to file paths
        """
        return {
            "csv": self.export_csv(results, filename_prefix, include_timestamp),
            "json": self.export_json(results, filename_prefix, include_timestamp),
            "summary": self.export_summary(results, filename_prefix, include_timestamp),
        }
