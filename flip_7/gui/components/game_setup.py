"""
Game setup component for creating a new Flip 7 game.
"""

import streamlit as st
from flip_7.core.engine import GameEngine


def show():
    """Show the game setup page."""
    st.title("🎮 New Game Setup")

    st.markdown("""
    Set up a new Flip 7 game by adding players below. You need at least 2 players to start.
    """)

    # Initialize player list in session state if not exists
    if 'setup_players' not in st.session_state:
        st.session_state.setup_players = []

    # Player input form
    st.markdown("### Add Players")

    col1, col2 = st.columns([3, 1])

    with col1:
        new_player_name = st.text_input(
            "Player Name",
            key="new_player_input",
            placeholder="Enter player name...",
            label_visibility="collapsed"
        )

    with col2:
        add_button = st.button("➕ Add Player", use_container_width=True, type="primary")

    if add_button and new_player_name:
        if new_player_name in st.session_state.setup_players:
            st.error(f"Player '{new_player_name}' already added!")
        elif len(new_player_name.strip()) == 0:
            st.error("Player name cannot be empty!")
        else:
            st.session_state.setup_players.append(new_player_name)
            st.rerun()

    # Show current players
    st.markdown("### Players")

    if len(st.session_state.setup_players) == 0:
        st.info("No players added yet. Add at least 2 players to start the game.")
    else:
        # Display players as cards
        for i, player_name in enumerate(st.session_state.setup_players):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{i+1}.** {player_name}")
            with col2:
                if st.button("🗑️", key=f"remove_{i}", help=f"Remove {player_name}"):
                    st.session_state.setup_players.pop(i)
                    st.rerun()

        st.markdown(f"**Total Players:** {len(st.session_state.setup_players)}")

    # Start game button
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🏠 Cancel", use_container_width=True):
            st.session_state.setup_players = []
            st.session_state.page = 'home'
            st.rerun()

    with col2:
        can_start = len(st.session_state.setup_players) >= 2

        if st.button(
            "🎯 Start Game",
            use_container_width=True,
            disabled=not can_start,
            type="primary"
        ):
            # Create new game
            engine = GameEngine()
            game_state = engine.start_new_game(st.session_state.setup_players)

            # Start first round
            engine.start_new_round()

            # Store in session state
            st.session_state.game_engine = engine
            st.session_state.game_state = game_state
            st.session_state.event_logger = engine.get_event_logger()
            st.session_state.game_saved = False  # Reset save flag

            # Clear setup data
            st.session_state.setup_players = []

            # Navigate to game play
            st.session_state.page = 'play'
            st.rerun()

    if not can_start:
        st.warning("⚠️ You need at least 2 players to start a game.")
