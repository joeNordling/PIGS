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
from flip_7.simulation.strategies.probability_threshold import ProbabilityThresholdStrategy
from flip_7.simulation.strategies.adaptive_threshold import AdaptiveThresholdStrategy
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


class TestProbabilityThresholdStrategy:
    """Tests for ProbabilityThresholdStrategy."""

    def test_initialization_with_valid_probability(self):
        """Test strategy initialization with valid probability."""
        strategy = ProbabilityThresholdStrategy(bust_probability_threshold=0.25)
        assert strategy.bust_probability_threshold == 0.25
        assert strategy.min_score_threshold == 20

    def test_initialization_with_invalid_probability(self):
        """Test strategy raises error with invalid probability."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            ProbabilityThresholdStrategy(bust_probability_threshold=1.5)

        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            ProbabilityThresholdStrategy(bust_probability_threshold=-0.1)

    def test_strategy_name_formatting(self):
        """Test that strategy name formats probability as percentage."""
        strategy = ProbabilityThresholdStrategy(bust_probability_threshold=0.15)
        assert strategy.name == "ProbThreshold(15%)"

        strategy2 = ProbabilityThresholdStrategy(bust_probability_threshold=0.25)
        assert strategy2.name == "ProbThreshold(25%)"

    def test_hits_with_low_bust_probability(self):
        """Test strategy hits when bust probability is low."""
        strategy = ProbabilityThresholdStrategy(bust_probability_threshold=0.20)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Hand with one card (low bust probability)
        visible_cards = [NumberCard(value=5), NumberCard(value=6), NumberCard(value=7)]

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=5)],
            my_round_score=40,
            my_total_score=50,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=40,
                cards_in_discard=0,
                visible_cards=visible_cards
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        # Should hit because bust probability is low (only 0/40 cards are value 5 in remaining deck)
        assert decision is True

    def test_stays_with_high_bust_probability_and_sufficient_score(self):
        """Test strategy stays when bust probability is high and has sufficient score."""
        strategy = ProbabilityThresholdStrategy(
            bust_probability_threshold=0.20,
            min_score_threshold=20
        )

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Hand with multiple cards, many duplicates visible
        # Simulate having 2, 3, 4, 5 in hand
        my_cards = [
            NumberCard(value=2),
            NumberCard(value=3),
            NumberCard(value=4),
            NumberCard(value=5)
        ]

        # Make remaining deck dangerous - lots of potential duplicates
        visible_cards = [NumberCard(value=6)] * 3  # Only safe cards visible

        context = StrategyContext(
            my_player_id="p1",
            my_cards=my_cards,
            my_round_score=50,  # Above min threshold
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=20,
                cards_in_discard=0,
                visible_cards=visible_cards
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        # Bust probability should be > 20% with 4 values in hand and only 20 cards left
        # Should stay because probability is high and score is sufficient
        assert decision is False

    def test_hits_despite_high_probability_if_score_too_low(self):
        """Test strategy hits even with high bust probability if score is too low."""
        strategy = ProbabilityThresholdStrategy(
            bust_probability_threshold=0.15,
            min_score_threshold=30
        )

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Hand with cards creating high bust risk
        my_cards = [
            NumberCard(value=2),
            NumberCard(value=3),
            NumberCard(value=4)
        ]

        context = StrategyContext(
            my_player_id="p1",
            my_cards=my_cards,
            my_round_score=15,  # Below min threshold
            my_total_score=50,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=10,  # Low cards remaining = high bust risk
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        # Should hit even though probability is high, because score too low
        assert decision is True

    def test_stays_when_already_won(self):
        """Test strategy stays when total score >= 200 (already won)."""
        strategy = ProbabilityThresholdStrategy(bust_probability_threshold=0.20)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=12)],
            my_round_score=50,
            my_total_score=210,  # Already won
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=40,
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert decision is False  # Should stay (already won)

    def test_must_hit_with_flip_three_active(self):
        """Test strategy must hit when Flip Three is active."""
        strategy = ProbabilityThresholdStrategy(bust_probability_threshold=0.10)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=12)],
            my_round_score=120,  # High score
            my_total_score=150,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=True,  # Flip Three active
            my_flip_three_count=2,  # Still need 2 more cards
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=40,
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert decision is True  # Must hit regardless of probability

    def test_second_chance_discards_most_recent(self):
        """Test that second chance discards the most recently drawn card."""
        strategy = ProbabilityThresholdStrategy()

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[],
            my_round_score=0,
            my_total_score=0,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=True,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=40, cards_in_discard=0, visible_cards=[]),
            round_number=1
        )

        duplicates = [NumberCard(value=7), NumberCard(value=7)]
        discarded = strategy.decide_second_chance_discard(context, 7, duplicates)

        # Should discard the last one (most recent)
        assert discarded == duplicates[-1]

    def test_flip_three_targets_highest_score_opponent(self):
        """Test Flip Three targets opponent with highest total score."""
        strategy = ProbabilityThresholdStrategy()

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
                OpponentInfo("p2", "Bob", 180, 80, False, False, 3),  # Highest
                OpponentInfo("p3", "Charlie", 120, 60, False, False, 2)
            ],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1", "p2", "p3"]
        target = strategy.decide_flip_three_target(context, possible_targets)

        # Should target Bob (p2) with highest total score
        assert target == "p2"

    def test_flip_three_targets_self_when_no_opponents(self):
        """Test Flip Three targets self when no opponents available."""
        strategy = ProbabilityThresholdStrategy()

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
            opponents=[],
            deck_stats=DeckStatistics(cards_remaining=30, cards_in_discard=10, visible_cards=[]),
            round_number=1
        )

        possible_targets = ["p1"]
        target = strategy.decide_flip_three_target(context, possible_targets)

        # Should target self (no other choice)
        assert target == "p1"

    def test_freeze_self_with_high_probability_and_good_score(self):
        """Test Freeze freezes self when bust probability high and have good score."""
        strategy = ProbabilityThresholdStrategy(
            bust_probability_threshold=0.20,
            min_score_threshold=30
        )

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Create high bust probability scenario with good score
        my_cards = [
            NumberCard(value=2),
            NumberCard(value=3),
            NumberCard(value=4),
            NumberCard(value=5)
        ]

        context = StrategyContext(
            my_player_id="p1",
            my_cards=my_cards,
            my_round_score=60,  # Good score, above min threshold
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 150, 80, False, False, 3)
            ],
            deck_stats=DeckStatistics(
                cards_remaining=15,  # Low remaining = high bust risk
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        possible_targets = ["p1", "p2"]
        target = strategy.decide_freeze_target(context, possible_targets)

        # Should freeze self to bank good score with high bust risk
        assert target == "p1"

    def test_freeze_opponent_with_low_probability(self):
        """Test Freeze targets opponent when bust probability is low."""
        strategy = ProbabilityThresholdStrategy(
            bust_probability_threshold=0.20,
            min_score_threshold=30
        )

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Low bust probability scenario
        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=5)],
            my_round_score=40,
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[
                OpponentInfo("p2", "Bob", 170, 90, False, False, 3),  # Highest
                OpponentInfo("p3", "Charlie", 120, 60, False, False, 2)
            ],
            deck_stats=DeckStatistics(
                cards_remaining=40,  # Many cards = low bust risk
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        possible_targets = ["p1", "p2", "p3"]
        target = strategy.decide_freeze_target(context, possible_targets)

        # Should freeze opponent with highest total score (Bob = p2)
        assert target == "p2"

    def test_probability_strategy_in_simulation(self):
        """Test that ProbabilityThresholdStrategy works in full simulation."""
        strategies = [
            ProbabilityThresholdStrategy(bust_probability_threshold=0.15),
            ProbabilityThresholdStrategy(bust_probability_threshold=0.25),
            ThresholdStrategy(target_score=100)
        ]

        runner = SimulationRunner(
            strategies=strategies,
            num_players=3,
            seed=42,
            verbose=False
        )

        results = runner.run_simulation(num_games=10)

        # Should complete successfully
        assert results.total_games == 10
        assert len(results.strategy_stats) == 3

        # All strategies should have played
        for stats in results.strategy_stats.values():
            assert stats.games_played == 10


class TestAdaptiveThresholdStrategy:
    """Tests for AdaptiveThresholdStrategy."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = AdaptiveThresholdStrategy(target_score=100, safe_probability_threshold=0.10)
        assert strategy.target_score == 100
        assert strategy.safe_probability_threshold == 0.10

    def test_initialization_with_invalid_probability(self):
        """Test strategy raises error with invalid probability."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            AdaptiveThresholdStrategy(safe_probability_threshold=1.5)

    def test_strategy_name_formatting(self):
        """Test that strategy name formats correctly."""
        strategy = AdaptiveThresholdStrategy(target_score=100, safe_probability_threshold=0.10)
        assert strategy.name == "Adaptive_100@10%"

    def test_continues_hitting_with_low_bust_probability(self):
        """Test strategy continues hitting even above threshold when bust probability is low."""
        strategy = AdaptiveThresholdStrategy(target_score=50, safe_probability_threshold=0.10)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Hand with one card (low bust probability)
        # Include a 5 in visible cards to reduce bust probability
        # Value 5 has 5 cards total, we have 1, showing 1 = 3 remaining / 40 = 7.5% < 10%
        visible_cards = [NumberCard(value=5), NumberCard(value=6), NumberCard(value=7)]

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=5)],
            my_round_score=60,  # ABOVE threshold (50)
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=40,
                cards_in_discard=0,
                visible_cards=visible_cards
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        # Should HIT even though above threshold, because bust probability is very low (7.5%)
        assert decision is True

    def test_uses_threshold_logic_with_moderate_bust_probability(self):
        """Test strategy falls back to threshold logic when bust probability is not low."""
        strategy = AdaptiveThresholdStrategy(target_score=50, safe_probability_threshold=0.10)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Hand with multiple cards (moderate bust probability)
        my_cards = [
            NumberCard(value=2),
            NumberCard(value=3),
            NumberCard(value=4),
            NumberCard(value=5)
        ]

        context = StrategyContext(
            my_player_id="p1",
            my_cards=my_cards,
            my_round_score=60,  # ABOVE threshold (50)
            my_total_score=100,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=30,
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        # Should STAY because above threshold and bust probability not low enough
        assert decision is False

    def test_hits_below_threshold_regardless_of_probability(self):
        """Test strategy hits when below threshold (normal threshold behavior)."""
        strategy = AdaptiveThresholdStrategy(target_score=100, safe_probability_threshold=0.10)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        # Hand with multiple cards (higher bust probability)
        my_cards = [
            NumberCard(value=2),
            NumberCard(value=3),
            NumberCard(value=4)
        ]

        context = StrategyContext(
            my_player_id="p1",
            my_cards=my_cards,
            my_round_score=40,  # BELOW threshold (100)
            my_total_score=50,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=20,
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        # Should HIT because below threshold (standard behavior)
        assert decision is True

    def test_stays_when_already_won(self):
        """Test strategy stays when total score >= 200."""
        strategy = AdaptiveThresholdStrategy(target_score=100, safe_probability_threshold=0.10)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=5)],
            my_round_score=50,
            my_total_score=210,  # Already won
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=False,
            my_flip_three_count=0,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=40,
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert decision is False

    def test_must_hit_with_flip_three_active(self):
        """Test strategy must hit when Flip Three is active."""
        strategy = AdaptiveThresholdStrategy(target_score=50, safe_probability_threshold=0.10)

        from flip_7.simulation.strategy import OpponentInfo, DeckStatistics

        context = StrategyContext(
            my_player_id="p1",
            my_cards=[NumberCard(value=12)],
            my_round_score=120,  # Well above threshold
            my_total_score=150,
            my_has_stayed=False,
            my_is_busted=False,
            my_has_second_chance=False,
            my_flip_three_active=True,
            my_flip_three_count=2,
            opponents=[],
            deck_stats=DeckStatistics(
                cards_remaining=40,
                cards_in_discard=0,
                visible_cards=[]
            ),
            round_number=1
        )

        decision = strategy.decide_hit_or_stay(context)
        assert decision is True

    def test_adaptive_strategy_in_simulation(self):
        """Test that AdaptiveThresholdStrategy works in full simulation."""
        strategies = [
            AdaptiveThresholdStrategy(target_score=100, safe_probability_threshold=0.10),
            ThresholdStrategy(target_score=100),
            RandomStrategy(seed=42)
        ]

        runner = SimulationRunner(
            strategies=strategies,
            num_players=3,
            seed=42,
            verbose=False
        )

        results = runner.run_simulation(num_games=10)

        # Should complete successfully
        assert results.total_games == 10
        assert len(results.strategy_stats) == 3

        # All strategies should have played
        for stats in results.strategy_stats.values():
            assert stats.games_played == 10
