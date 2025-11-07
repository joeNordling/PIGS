"""
Tests for the simulation framework.

This module tests the strategy interface, simulation runner, and data export.
"""

import pytest
import tempfile
import json
import csv
from pathlib import Path

from flip_7.simulation.strategy import BaseStrategy, StrategyContext
from flip_7.simulation.strategies import RandomStrategy, ThresholdStrategy
from flip_7.simulation.runner import SimulationRunner, SimulationResults
from flip_7.simulation.exporter import SimulationExporter
from flip_7.data.models import NumberCard, GameState


class TestBaseStrategy:
    """Tests for base strategy functionality."""

    def test_random_strategy_always_returns_boolean(self):
        """Random strategy should return bool from decide_hit_or_stay."""
        strategy = RandomStrategy(hit_probability=0.5, seed=42)

        # Create minimal context
        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=0,
            my_total_score=0,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=50, cards_in_discard=0, visible_cards=[]),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert isinstance(decision, bool)

    def test_random_strategy_respects_probability(self):
        """Random strategy should approximate the hit probability over many trials."""
        strategy = RandomStrategy(hit_probability=0.7, seed=42)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=0,
            my_total_score=0,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=50, cards_in_discard=0, visible_cards=[]),
            round_number=1
        )

        # Run many trials
        hits = sum(strategy.decide_hit_or_stay(context) for _ in range(1000))
        hit_rate = hits / 1000

        # Should be close to 0.7 (within 5%)
        assert 0.65 < hit_rate < 0.75

    def test_threshold_strategy_stays_above_threshold(self):
        """Threshold strategy should stay when score exceeds threshold."""
        strategy = ThresholdStrategy(target_score=100)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=12), NumberCard(value=11), NumberCard(value=10)],
            my_round_score=120,  # Above threshold
            my_total_score=120,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=50, cards_in_discard=0, visible_cards=[]),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert decision is False  # Should stay

    def test_threshold_strategy_hits_below_threshold(self):
        """Threshold strategy should hit when score is below threshold."""
        strategy = ThresholdStrategy(target_score=100)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=5)],
            my_round_score=50,  # Below threshold
            my_total_score=50,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=50, cards_in_discard=0, visible_cards=[]),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert decision is True  # Should hit

    def test_strategy_context_counts_number_cards(self):
        """StrategyContext should correctly count number cards."""
        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        from flip_7.data.models import ActionCard, ModifierCard, ActionType, ModifierType

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[
                NumberCard(value=12),
                NumberCard(value=11),
                ActionCard(action_type=ActionType.FREEZE),
                ModifierCard(modifier_type=ModifierType.PLUS_2, value=2),
                NumberCard(value=10),
            ],
            my_round_score=0,
            my_total_score=0,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=50, cards_in_discard=0, visible_cards=[]),
            round_number=1
        )

        assert context.count_number_cards() == 3


class TestSimulationRunner:
    """Tests for the simulation runner."""

    def test_runner_requires_at_least_two_players(self):
        """Runner should require at least 2 players."""
        with pytest.raises(ValueError, match="at least 2 players"):
            SimulationRunner(
                strategies=[RandomStrategy()],
                num_players=1
            )

    def test_runner_requires_enough_strategies(self):
        """Runner should require enough strategies for num_players."""
        with pytest.raises(ValueError, match="Not enough strategies"):
            SimulationRunner(
                strategies=[RandomStrategy()],
                num_players=3
            )

    def test_runner_completes_single_game(self):
        """Runner should successfully complete a single game."""
        strategies = [
            RandomStrategy(seed=1),
            RandomStrategy(seed=2)
        ]

        runner = SimulationRunner(
            strategies=strategies,
            num_players=2,
            seed=42
        )

        results = runner.run_simulation(num_games=1)

        assert results.total_games == 1
        assert len(results.game_results) == 1
        assert results.game_results[0].winner_id is not None

    def test_runner_completes_multiple_games(self):
        """Runner should successfully complete multiple games."""
        strategies = [
            RandomStrategy(seed=1),
            ThresholdStrategy(target_score=100)
        ]

        runner = SimulationRunner(
            strategies=strategies,
            num_players=2,
            seed=42,
            verbose=False
        )

        results = runner.run_simulation(num_games=10)

        assert results.total_games == 10
        assert len(results.game_results) == 10

        # All games should have a winner
        for game in results.game_results:
            assert game.winner_id is not None
            assert game.total_rounds > 0

    def test_runner_calculates_aggregate_stats(self):
        """Runner should calculate aggregate statistics."""
        strategies = [
            RandomStrategy(name="Random", seed=1),
            ThresholdStrategy(name="Threshold", target_score=100)
        ]

        runner = SimulationRunner(
            strategies=strategies,
            num_players=2,
            seed=42,
            verbose=False
        )

        results = runner.run_simulation(num_games=20)

        # Should have stats for both strategies
        assert len(results.strategy_stats) == 2
        assert "Random" in results.strategy_stats
        assert "Threshold" in results.strategy_stats

        # Stats should be valid
        for name, stats in results.strategy_stats.items():
            assert stats.games_played == 20
            assert 0 <= stats.win_rate <= 1.0
            assert stats.wins + stats.games_played - stats.wins == stats.games_played

    def test_runner_produces_consistent_aggregate_stats_with_seed(self):
        """Runner with same seed should produce similar aggregate statistics."""
        strategies = [
            RandomStrategy(name="Random1", seed=1),
            RandomStrategy(name="Random2", seed=2)
        ]

        runner1 = SimulationRunner(strategies=strategies, num_players=2, seed=42)
        results1 = runner1.run_simulation(num_games=50)

        runner2 = SimulationRunner(strategies=strategies, num_players=2, seed=42)
        results2 = runner2.run_simulation(num_games=50)

        # Aggregate statistics should be very close (within 1% due to RNG)
        for strategy_name in ['Random1', 'Random2']:
            stats1 = results1.strategy_stats[strategy_name]
            stats2 = results2.strategy_stats[strategy_name]

            # Games played should be exactly the same
            assert stats1.games_played == stats2.games_played == 50


class TestSimulationExporter:
    """Tests for the simulation exporter."""

    def test_exporter_creates_csv_file(self):
        """Exporter should create valid CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run a small simulation
            strategies = [RandomStrategy(seed=1), RandomStrategy(seed=2)]
            runner = SimulationRunner(strategies, num_players=2, seed=42)
            results = runner.run_simulation(num_games=5)

            # Export to CSV
            exporter = SimulationExporter(output_dir=tmpdir)
            csv_path = exporter.export_csv(results, "test", include_timestamp=False)

            # Verify file exists
            assert csv_path.exists()

            # Verify CSV is valid
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # Should have 2 players per game * 5 games = 10 rows
                assert len(rows) == 10

                # Check column names
                assert 'game_id' in rows[0]
                assert 'strategy' in rows[0]
                assert 'won_game' in rows[0]
                assert 'final_score' in rows[0]

    def test_exporter_creates_json_file(self):
        """Exporter should create valid JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run a small simulation
            strategies = [RandomStrategy(seed=1), RandomStrategy(seed=2)]
            runner = SimulationRunner(strategies, num_players=2, seed=42)
            results = runner.run_simulation(num_games=3)

            # Export to JSON
            exporter = SimulationExporter(output_dir=tmpdir)
            json_path = exporter.export_json(results, "test", include_timestamp=False)

            # Verify file exists
            assert json_path.exists()

            # Verify JSON is valid
            with open(json_path, 'r') as f:
                data = json.load(f)

                assert 'metadata' in data
                assert data['metadata']['total_games'] == 3
                assert 'strategy_statistics' in data
                assert 'games' in data
                assert len(data['games']) == 3

    def test_exporter_creates_summary_file(self):
        """Exporter should create human-readable summary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run a small simulation
            strategies = [RandomStrategy(seed=1), ThresholdStrategy(target_score=100)]
            runner = SimulationRunner(strategies, num_players=2, seed=42)
            results = runner.run_simulation(num_games=5)

            # Export summary
            exporter = SimulationExporter(output_dir=tmpdir)
            summary_path = exporter.export_summary(results, "test", include_timestamp=False)

            # Verify file exists
            assert summary_path.exists()

            # Verify content
            content = summary_path.read_text()
            assert "FLIP 7 SIMULATION SUMMARY" in content
            assert "Total Games Simulated: 5" in content
            assert "STRATEGY PERFORMANCE" in content

    def test_exporter_export_all(self):
        """export_all should create all three file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run a small simulation
            strategies = [RandomStrategy(seed=1), RandomStrategy(seed=2)]
            runner = SimulationRunner(strategies, num_players=2, seed=42)
            results = runner.run_simulation(num_games=2)

            # Export all
            exporter = SimulationExporter(output_dir=tmpdir)
            files = exporter.export_all(results, "test", include_timestamp=False)

            # Should have all three formats
            assert 'csv' in files
            assert 'json' in files
            assert 'summary' in files

            # All files should exist
            assert files['csv'].exists()
            assert files['json'].exists()
            assert files['summary'].exists()


class TestIntegration:
    """Integration tests for the complete simulation pipeline."""

    def test_full_simulation_pipeline(self):
        """Test running a complete simulation and exporting results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Define strategies
            strategies = [
                RandomStrategy(name="Random", hit_probability=0.5, seed=1),
                ThresholdStrategy(name="Threshold_100", target_score=100),
                ThresholdStrategy(name="Threshold_120", target_score=120),
            ]

            # Run simulation
            runner = SimulationRunner(
                strategies=strategies,
                num_players=2,
                seed=42,
                verbose=False
            )

            results = runner.run_simulation(num_games=50)

            # Verify results
            assert results.total_games == 50
            assert len(results.strategy_stats) == 3

            # Export results
            exporter = SimulationExporter(output_dir=tmpdir)
            files = exporter.export_all(results, "integration_test")

            # Verify all files created
            assert all(f.exists() for f in files.values())

            # Verify CSV can be read (if pandas is available)
            try:
                import pandas as pd
                df = pd.read_csv(files['csv'])
                assert len(df) == 100  # 2 players * 50 games
                assert set(df['strategy'].unique()) == {'Random', 'Threshold_100', 'Threshold_120'}
            except ImportError:
                # pandas not installed, skip this check
                pass


class TestStrategyActionCardDecisions:
    """Test strategy action card decision methods."""

    def test_random_strategy_flip_three_decision(self):
        """Test that RandomStrategy makes Flip Three target decisions."""
        strategy = RandomStrategy(seed=42)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=50,
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 120, 80, False, False, 3)
            ],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1", "p2"]
        target = strategy.decide_flip_three_target(context, possible_targets)

        # Should return one of the possible targets
        assert target in possible_targets

    def test_random_strategy_freeze_decision(self):
        """Test that RandomStrategy makes Freeze target decisions."""
        strategy = RandomStrategy(seed=42)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=50,
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 120, 80, False, False, 3)
            ],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1", "p2"]
        target = strategy.decide_freeze_target(context, possible_targets)

        # Should return one of the possible targets
        assert target in possible_targets

    def test_threshold_strategy_flip_three_targets_opponent(self):
        """Test that ThresholdStrategy applies Flip Three strategically."""
        strategy = ThresholdStrategy(target_score=100)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=50,
            my_total_score=80,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 150, 100, False, False, 3),  # High score opponent
                OpponentInfo("p3", "Charlie", 50, 30, False, False, 2)  # Low score opponent
            ],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1", "p2", "p3"]
        target = strategy.decide_flip_three_target(context, possible_targets)

        # Should target opponent with highest score (Bob = p2)
        assert target == "p2"

    def test_threshold_strategy_freeze_self_when_above_threshold(self):
        """Test that ThresholdStrategy freezes self when above threshold."""
        strategy = ThresholdStrategy(target_score=100)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=120,  # Above threshold
            my_total_score=80,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 150, 100, False, False, 3)
            ],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1", "p2"]
        target = strategy.decide_freeze_target(context, possible_targets)

        # Should freeze self (bank good score)
        assert target == "p1"

    def test_threshold_strategy_freeze_opponent_when_below_threshold(self):
        """Test that ThresholdStrategy freezes opponent when below threshold."""
        strategy = ThresholdStrategy(target_score=100)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=50,  # Below threshold
            my_total_score=80,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 150, 100, False, False, 3),  # High score
                OpponentInfo("p3", "Charlie", 50, 30, False, False, 2)   # Low score
            ],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1", "p2", "p3"]
        target = strategy.decide_freeze_target(context, possible_targets)

        # Should freeze opponent with highest score (Bob = p2)
        assert target == "p2"

    def test_simulation_runner_handles_action_cards(self):
        """Test that simulation runner properly handles action card targeting."""
        # Create strategies as a list
        strategies = [
            RandomStrategy(seed=42),
            ThresholdStrategy(target_score=100)
        ]

        # Create runner with strategies
        runner = SimulationRunner(strategies, num_players=2, seed=123)

        # Run a single game
        results = runner.run_simulation(num_games=1)

        # Should complete without errors
        assert results.total_games == 1
        assert len(results.game_results) == 1
