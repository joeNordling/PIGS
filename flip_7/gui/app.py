"""
Flip 7 Game Tracker - Streamlit GUI Application

This is the main entry point for the Flip 7 game tracking interface.

Run with: streamlit run flip_7/gui/app.py
"""

import streamlit as st
from pathlib import Path

# Configure page
st.set_page_config(
    page_title="Flip 7 Game Tracker",
    page_icon="🎴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import components (these will be created next)
try:
    from flip_7.gui.components import game_setup, game_play, stats_view, game_browser
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from flip_7.gui.components import game_setup, game_play, stats_view, game_browser


def initialize_session_state():
    """Initialize session state variables."""
    if 'page' not in st.session_state:
        st.session_state.page = 'home'

    if 'game_engine' not in st.session_state:
        st.session_state.game_engine = None

    if 'game_state' not in st.session_state:
        st.session_state.game_state = None

    if 'event_logger' not in st.session_state:
        st.session_state.event_logger = None


def show_home():
    """Show the home page with main navigation."""
    st.title("🎴 Flip 7 Game Tracker")

    st.markdown("""
    Welcome to the Flip 7 Game Tracker! Choose an option below to get started.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🎮 New Game")
        st.markdown("Start tracking a new Flip 7 game")
        if st.button("Start New Game", use_container_width=True, type="primary"):
            st.session_state.page = 'setup'
            st.rerun()

    with col2:
        st.markdown("### 📂 Load Game")
        st.markdown("Continue a saved game")
        if st.button("Browse Games", use_container_width=True):
            st.session_state.page = 'browser'
            st.rerun()

    with col3:
        st.markdown("### 📊 Statistics")
        st.markdown("View player stats and leaderboards")
        if st.button("View Stats", use_container_width=True):
            st.session_state.page = 'stats'
            st.rerun()

    # Show quick stats on home page
    st.markdown("---")
    st.markdown("### 📈 Quick Stats")

    from flip_7.data.persistence import GameRepository
    repo = GameRepository()
    games = repo.list_games()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Games", len(games))

    with col2:
        completed = sum(1 for g in games if g.is_complete)
        st.metric("Completed Games", completed)

    with col3:
        in_progress = len(games) - completed
        st.metric("In Progress", in_progress)

    with col4:
        total_rounds = sum(g.total_rounds for g in games)
        st.metric("Total Rounds", total_rounds)

    # Recent games
    if games:
        st.markdown("### 🕐 Recent Games")
        recent_games = games[:5]

        for game in recent_games:
            with st.expander(f"{'✅' if game.is_complete else '⏸️'} {', '.join(game.player_names)} - {game.created_at.strftime('%Y-%m-%d %H:%M')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Players:** {', '.join(game.player_names)}")
                    st.write(f"**Rounds:** {game.total_rounds}")
                with col2:
                    st.write(f"**Status:** {'Complete' if game.is_complete else 'In Progress'}")
                    if game.winner_name:
                        st.write(f"**Winner:** {game.winner_name}")

                if st.button(f"Load Game", key=f"load_{game.game_id}"):
                    from flip_7.data.persistence import GameRepository
                    from flip_7.core.engine import GameEngine

                    repo = GameRepository()
                    game_state, event_logger = repo.load_game(game.game_id)

                    engine = GameEngine(game_state, event_logger)
                    st.session_state.game_engine = engine
                    st.session_state.game_state = game_state
                    st.session_state.event_logger = event_logger
                    st.session_state.game_saved = game_state.is_complete  # Already saved if complete
                    st.session_state.page = 'play'
                    st.rerun()


def show_sidebar():
    """Show the sidebar with navigation."""
    with st.sidebar:
        st.markdown("# 🎴 Flip 7")

        # Navigation
        st.markdown("### Navigation")

        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = 'home'
            st.rerun()

        # Show game controls if game is active
        if st.session_state.game_state is not None:
            st.markdown("---")
            st.markdown("### Current Game")

            game_state = st.session_state.game_state
            st.write(f"**Players:** {len(game_state.players)}")

            if game_state.current_round:
                st.write(f"**Round:** {game_state.current_round.round_number}")
            elif game_state.round_history:
                st.write(f"**Rounds:** {len(game_state.round_history)}")

            if st.button("💾 Save Game", use_container_width=True):
                from flip_7.data.persistence import GameRepository
                repo = GameRepository()
                repo.save_game(st.session_state.game_state, st.session_state.event_logger)
                st.success("Game saved!")

            if st.button("🚪 End Game", use_container_width=True):
                st.session_state.game_engine = None
                st.session_state.game_state = None
                st.session_state.event_logger = None
                st.session_state.page = 'home'
                st.rerun()

        # Game rules reference
        st.markdown("---")
        st.markdown("### 📖 Quick Reference")

        with st.expander("Card Values"):
            st.markdown("""
            **Number Cards:**
            - 0-12 (each value N appears N times, except 0 appears once)

            **Modifiers:**
            - +2, +4, +6, +8, +10 (bonus points)
            - ×2 (double number cards)

            **Action Cards:**
            - Freeze (bank and stay)
            - Flip Three (take 3 cards)
            - Second Chance (discard duplicate)
            """)

        with st.expander("Scoring & Rules"):
            st.markdown("""
            **Score Formula:**
            `(base + bonuses) × multiplier + Flip 7`

            **Win Condition:**
            - First to reach 200+ total points wins!

            **Bust Condition:**
            - Drawing a duplicate number card = BUST (zero points for round)
            - Example: Having two 12s = BUSTED!

            **Second Chance:**
            - Saves you from ONE duplicate
            - Must use it to discard the duplicate card

            **Flip 7 Bonus:**
            - Get exactly 7 number cards for +15 points
            """)


def main():
    """Main application entry point."""
    initialize_session_state()
    show_sidebar()

    # Route to appropriate page
    page = st.session_state.page

    if page == 'home':
        show_home()
    elif page == 'setup':
        game_setup.show()
    elif page == 'play':
        game_play.show()
    elif page == 'stats':
        stats_view.show()
    elif page == 'browser':
        game_browser.show()
    else:
        st.error(f"Unknown page: {page}")
        if st.button("Return Home"):
            st.session_state.page = 'home'
            st.rerun()


if __name__ == "__main__":
    main()
