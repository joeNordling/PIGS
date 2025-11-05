"""
Game browser component for loading and managing saved games.
"""

import streamlit as st
from flip_7.data.persistence import GameRepository
from flip_7.core.engine import GameEngine


def show():
    """Show the game browser page."""
    st.title("📂 Game Browser")

    st.markdown("""
    Browse and load your saved Flip 7 games.
    """)

    repo = GameRepository()
    games = repo.list_games()

    if not games:
        st.info("No saved games found. Start a new game to create your first save!")

        if st.button("🎮 Start New Game", type="primary"):
            st.session_state.page = 'setup'
            st.rerun()

        return

    # Filter options
    col1, col2 = st.columns(2)

    with col1:
        filter_status = st.selectbox(
            "Filter by Status",
            ["All Games", "In Progress", "Completed"]
        )

    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Most Recent", "Oldest First", "Most Rounds"]
        )

    # Apply filters
    filtered_games = games

    if filter_status == "In Progress":
        filtered_games = [g for g in games if not g.is_complete]
    elif filter_status == "Completed":
        filtered_games = [g for g in games if g.is_complete]

    # Apply sorting
    if sort_by == "Most Recent":
        filtered_games.sort(key=lambda g: g.created_at, reverse=True)
    elif sort_by == "Oldest First":
        filtered_games.sort(key=lambda g: g.created_at)
    elif sort_by == "Most Rounds":
        filtered_games.sort(key=lambda g: g.total_rounds, reverse=True)

    st.markdown(f"### Games ({len(filtered_games)})")

    # Display games
    for game_meta in filtered_games:
        _show_game_card(game_meta, repo)


def _show_game_card(game_meta, repo):
    """Show a single game card."""
    # Status icon
    if game_meta.is_complete:
        status_icon = "✅"
        status_text = "Complete"
        status_color = "green"
    else:
        status_icon = "⏸️"
        status_text = "In Progress"
        status_color = "blue"

    with st.container():
        col1, col2, col3, col4 = st.columns([3, 2, 1, 2])

        with col1:
            st.markdown(f"### {status_icon} {', '.join(game_meta.player_names)}")
            st.caption(game_meta.created_at.strftime('%Y-%m-%d %H:%M:%S'))

        with col2:
            st.markdown(f"**Status:** :{status_color}[{status_text}]")
            if game_meta.winner_name:
                st.markdown(f"**Winner:** {game_meta.winner_name}")

        with col3:
            st.metric("Rounds", game_meta.total_rounds)

        with col4:
            # Action buttons
            if st.button("📂 Load", key=f"load_{game_meta.game_id}", use_container_width=True, type="primary"):
                _load_game(game_meta.game_id, repo)

            if st.button("🗑️ Delete", key=f"delete_{game_meta.game_id}", use_container_width=True):
                st.session_state[f'confirm_delete_{game_meta.game_id}'] = True
                st.rerun()

        # Delete confirmation
        if st.session_state.get(f'confirm_delete_{game_meta.game_id}', False):
            st.warning(f"⚠️ Are you sure you want to delete this game?")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ Yes, Delete", key=f"confirm_yes_{game_meta.game_id}"):
                    repo.delete_game(game_meta.game_id)
                    st.session_state[f'confirm_delete_{game_meta.game_id}'] = False
                    st.success("Game deleted!")
                    st.rerun()

            with col2:
                if st.button("❌ Cancel", key=f"confirm_no_{game_meta.game_id}"):
                    st.session_state[f'confirm_delete_{game_meta.game_id}'] = False
                    st.rerun()

        # Game details in expander
        with st.expander("📊 Game Details"):
            try:
                game_state, event_logger = repo.load_game(game_meta.game_id)

                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Game ID:** `{game_meta.game_id[:8]}...`")
                    st.write(f"**Players:** {len(game_meta.player_names)}")
                    st.write(f"**Total Rounds:** {game_meta.total_rounds}")

                with col2:
                    st.write(f"**Status:** {status_text}")
                    if game_meta.winner_name:
                        st.write(f"**Winner:** {game_meta.winner_name}")
                    st.write(f"**Events Logged:** {len(event_logger.events)}")

                # Show round history
                if game_state.round_history:
                    st.markdown("**Round History:**")

                    for round_state in game_state.round_history:
                        dealer = next(p for p in game_state.players if p.player_id == round_state.dealer_id)

                        # Round scores
                        scores = [(p.name, round_state.player_states[p.player_id].round_score)
                                  for p in game_state.players]
                        scores.sort(key=lambda x: x[1], reverse=True)

                        winner_names = [
                            next(p.name for p in game_state.players if p.player_id == wid)
                            for wid in round_state.winner_ids
                        ]

                        score_text = ", ".join([f"{name}: {score}" for name, score in scores])

                        st.caption(
                            f"Round {round_state.round_number} (Dealer: {dealer.name}) - "
                            f"{score_text} | Winner: {', '.join(winner_names)}"
                        )

            except Exception as e:
                st.error(f"Error loading game details: {e}")

        st.markdown("---")


def _load_game(game_id, repo):
    """Load a game and navigate to the game play screen."""
    try:
        game_state, event_logger = repo.load_game(game_id)

        # Create engine with loaded state
        engine = GameEngine(game_state, event_logger)

        # Store in session state
        st.session_state.game_engine = engine
        st.session_state.game_state = game_state
        st.session_state.event_logger = event_logger
        st.session_state.game_saved = game_state.is_complete  # Already saved if complete

        # Navigate to game play
        st.session_state.page = 'play'
        st.success(f"Loaded game successfully!")
        st.rerun()

    except Exception as e:
        st.error(f"Error loading game: {e}")
