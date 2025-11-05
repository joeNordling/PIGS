"""
Statistics view component for displaying game statistics and leaderboards.
"""

import streamlit as st
from flip_7.data.persistence import GameRepository
from flip_7.data.statistics import StatisticsCalculator


def show():
    """Show the statistics view."""
    st.title("📊 Statistics & Leaderboards")

    # Load all games
    repo = GameRepository()
    all_games = repo.get_all_completed_games()

    if not all_games:
        st.info("No completed games yet. Complete some games to see statistics!")
        if st.button("🏠 Return Home"):
            st.session_state.page = 'home'
            st.rerun()
        return

    calc = StatisticsCalculator()

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["🏆 Leaderboard", "📈 Historical Stats", "👤 Player Details"])

    with tab1:
        _show_leaderboard(all_games, calc)

    with tab2:
        _show_historical_stats(all_games, calc)

    with tab3:
        _show_player_details(all_games, calc)


def _show_leaderboard(games, calc):
    """Show the player leaderboard."""
    st.markdown("### 🏆 Player Leaderboard")

    leaderboard = calc.get_leaderboard(games)

    if not leaderboard:
        st.info("No player statistics available yet.")
        return

    # Display as table
    st.markdown("#### Top Players by Win Rate")

    for i, stats in enumerate(leaderboard, 1):
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])

            with col1:
                icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                st.markdown(f"### {icon}")

            with col2:
                st.markdown(f"### {stats.player_name}")

            with col3:
                st.metric("Win Rate", f"{stats.win_rate:.1f}%")

            with col4:
                st.metric("Games Won", f"{stats.games_won}/{stats.games_played}")

            with col5:
                st.metric("Avg Score", f"{stats.average_score_per_game:.0f}")

            # Additional stats in expander
            with st.expander("📊 Detailed Stats"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Total Rounds", stats.total_rounds)
                    st.metric("Avg Round Score", f"{stats.average_score_per_round:.1f}")

                with col2:
                    st.metric("Flip 7 Count", stats.flip_7_count)
                    st.metric("Flip 7 Rate", f"{stats.flip_7_rate:.1f}%")

                with col3:
                    st.metric("Bust Count", stats.bust_count)
                    st.metric("Bust Rate", f"{stats.bust_rate:.1f}%")

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Highest Round Score", stats.highest_round_score)

                with col2:
                    st.metric("Highest Game Score", stats.highest_game_score)

            st.markdown("---")


def _show_historical_stats(games, calc):
    """Show historical aggregate statistics."""
    st.markdown("### 📈 Historical Statistics")

    hist_stats = calc.calculate_historical_stats(games)

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Games", hist_stats.total_games)

    with col2:
        st.metric("Total Rounds", hist_stats.total_rounds)

    with col3:
        st.metric("Avg Rounds/Game", f"{hist_stats.average_rounds_per_game:.1f}")

    with col4:
        st.metric("Total Cards Dealt", hist_stats.total_cards_dealt)

    st.markdown("---")

    # Special achievements
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 🎉 Flip 7 Statistics")
        st.metric("Total Flip 7s", hist_stats.flip_7_total)
        st.metric("Flip 7 Rate", f"{hist_stats.flip_7_percentage:.1f}%")

    with col2:
        st.markdown("#### 💥 Bust Statistics")
        st.metric("Total Busts", hist_stats.bust_total)
        st.metric("Bust Rate", f"{hist_stats.bust_percentage:.1f}%")

    with col3:
        st.markdown("#### 🏆 Records")
        if hist_stats.most_common_winner:
            st.metric("Most Wins", hist_stats.most_common_winner)
        st.metric("Highest Score Ever", hist_stats.highest_score_ever)

    # Card distribution
    if hist_stats.card_distribution:
        st.markdown("---")
        st.markdown("### 🎴 Card Distribution")

        st.caption("Frequency of cards dealt across all games")

        # Group by card type
        number_cards = {k: v for k, v in hist_stats.card_distribution.items() if k.startswith("Number")}
        modifier_cards = {k: v for k, v in hist_stats.card_distribution.items() if k.startswith("Modifier")}
        action_cards = {k: v for k, v in hist_stats.card_distribution.items() if k.startswith("Action")}

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Number Cards**")
            for card, count in sorted(number_cards.items()):
                st.caption(f"{card}: {count}")

        with col2:
            st.markdown("**Modifier Cards**")
            for card, count in sorted(modifier_cards.items()):
                st.caption(f"{card}: {count}")

        with col3:
            st.markdown("**Action Cards**")
            for card, count in sorted(action_cards.items()):
                st.caption(f"{card}: {count}")


def _show_player_details(games, calc):
    """Show detailed stats for a selected player."""
    st.markdown("### 👤 Player Details")

    # Get all unique player names
    player_names = set()
    for game in games:
        for player in game.players:
            player_names.add(player.name)

    if not player_names:
        st.info("No players found.")
        return

    selected_player = st.selectbox(
        "Select a player to view detailed statistics",
        sorted(player_names)
    )

    if selected_player:
        stats = calc.calculate_player_stats(selected_player, games)

        # Header
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Games Played", stats.games_played)
            st.metric("Games Won", stats.games_won)

        with col2:
            st.metric("Win Rate", f"{stats.win_rate:.1f}%")
            st.metric("Total Rounds", stats.total_rounds)

        with col3:
            st.metric("Avg Score/Game", f"{stats.average_score_per_game:.1f}")
            st.metric("Avg Score/Round", f"{stats.average_score_per_round:.1f}")

        st.markdown("---")

        # Performance metrics
        st.markdown("### 📊 Performance Metrics")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🎉 Flip 7 Stats")
            st.metric("Flip 7 Count", stats.flip_7_count)
            st.metric("Flip 7 Rate", f"{stats.flip_7_rate:.1f}%")

            st.markdown("#### 🏆 Records")
            st.metric("Highest Round Score", stats.highest_round_score)
            st.metric("Highest Game Score", stats.highest_game_score)

        with col2:
            st.markdown("#### 💥 Bust Stats")
            st.metric("Bust Count", stats.bust_count)
            st.metric("Bust Rate", f"{stats.bust_rate:.1f}%")

        # Game history for this player
        st.markdown("---")
        st.markdown("### 🎮 Game History")

        player_games = [g for g in games if any(p.name == selected_player for p in g.players)]

        for game in player_games[:10]:  # Show last 10 games
            player_info = next(p for p in game.players if p.name == selected_player)

            if game.round_history:
                last_round = game.round_history[-1]
                player_state = last_round.player_states[player_info.player_id]
                final_score = player_state.total_score

                is_winner = game.winner_id == player_info.player_id
                status_icon = "👑" if is_winner else "📊"

                with st.expander(
                    f"{status_icon} {game.created_at.strftime('%Y-%m-%d %H:%M')} - "
                    f"{final_score} points ({len(game.round_history)} rounds)"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Players:** {', '.join([p.name for p in game.players])}")
                        st.write(f"**Your Score:** {final_score}")

                    with col2:
                        st.write(f"**Rounds Played:** {len(game.round_history)}")
                        if is_winner:
                            st.success("🏆 Winner!")
                        else:
                            winner = next((p for p in game.players if p.player_id == game.winner_id), None)
                            if winner:
                                st.write(f"**Winner:** {winner.name}")
