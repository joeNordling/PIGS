"""
Game play component for active game tracking.
"""

import streamlit as st
from flip_7.data.models import NumberCard, ActionCard, ActionType
from flip_7.core.rules import calculate_score
from flip_7.gui.components.card_picker import get_card_display
from flip_7.data.persistence import GameRepository


def show():
    """Show the game play interface."""
    game_state = st.session_state.game_state
    engine = st.session_state.game_engine

    if game_state is None or engine is None:
        st.error("No active game. Please start or load a game first.")
        if st.button("Go to Home"):
            st.session_state.page = 'home'
            st.rerun()
        return

    # Check if game is complete
    if game_state.is_complete:
        _show_game_complete(game_state)
        return

    # Check if we need to start a new round
    if game_state.current_round is None:
        _show_round_complete(game_state, engine)
        return

    # Show active game
    _show_active_game(game_state, engine)


def _show_game_complete(game_state):
    """Show game completion screen."""
    # Auto-save the completed game
    if 'game_saved' not in st.session_state or not st.session_state.game_saved:
        try:
            repo = GameRepository()
            repo.save_game(game_state, st.session_state.event_logger)
            st.session_state.game_saved = True
        except Exception as e:
            st.error(f"Error saving game: {e}")

    st.title("🎉 Game Complete!")

    winner = next(p for p in game_state.players if p.player_id == game_state.winner_id)
    st.balloons()

    st.markdown(f"## 👑 {winner.name} Wins!")

    # Show final scores
    st.markdown("### Final Scores")

    if game_state.round_history:
        last_round = game_state.round_history[-1]
        scores = [(p.name, last_round.player_states[p.player_id].total_score)
                  for p in game_state.players]
        scores.sort(key=lambda x: x[1], reverse=True)

        for i, (name, score) in enumerate(scores, 1):
            icon = "👑" if i == 1 else f"{i}."
            st.markdown(f"{icon} **{name}**: {score} points")

    st.markdown(f"**Total Rounds:** {len(game_state.round_history)}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Save Game", use_container_width=True, type="primary"):
            repo = GameRepository()
            repo.save_game(game_state, st.session_state.event_logger)
            st.success("Game saved successfully!")

    with col2:
        if st.button("🏠 Return Home", use_container_width=True):
            st.session_state.game_engine = None
            st.session_state.game_state = None
            st.session_state.event_logger = None
            st.session_state.page = 'home'
            st.rerun()


def _show_round_complete(game_state, engine):
    """Show round complete screen and start new round button."""
    st.title(f"📊 Round {len(game_state.round_history)} Complete")

    last_round = game_state.round_history[-1]

    # Show round results
    st.markdown("### Round Results")

    round_scores = [(p.name, last_round.player_states[p.player_id].round_score,
                     last_round.player_states[p.player_id].total_score,
                     p.player_id in last_round.winner_ids)
                    for p in game_state.players]
    round_scores.sort(key=lambda x: x[1], reverse=True)

    for name, round_score, total_score, is_winner in round_scores:
        icon = "👑" if is_winner else "▪️"
        st.markdown(f"{icon} **{name}**: {round_score} points this round → **{total_score} total**")

    st.markdown("---")

    if st.button("▶️ Start Next Round", use_container_width=True, type="primary"):
        engine.start_new_round()
        st.rerun()


def _show_active_game(game_state, engine):
    """Show the active game interface."""
    current_round = game_state.current_round

    # Header
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.title(f"🎮 Round {current_round.round_number}")

    with col2:
        dealer = next(p for p in game_state.players if p.player_id == current_round.dealer_id)
        st.metric("Dealer", dealer.name)

    with col3:
        st.metric("Cards Left", current_round.cards_remaining_in_deck)

    # Turn announcement banner
    current_player_id = current_round.current_player_id
    if current_player_id:
        current_player_info = next(
            (p for p in game_state.players if p.player_id == current_player_id), None
        )
        if current_player_info:
            current_player_state = current_round.player_states[current_player_id]
            if current_player_state.flip_three_active:
                st.warning(
                    f"⚠️ **{current_player_info.name}'s turn** — "
                    f"FORCED DRAW ({current_player_state.flip_three_count} card(s) remaining)"
                )
            else:
                st.info(f"🎯 **{current_player_info.name}'s turn** — Draw a card or Stay")

    st.markdown("---")

    # Player panels
    st.markdown("### 👥 Players")

    has_pending_action = st.session_state.get('pending_action_card') is not None

    for player_info in game_state.players:
        player_state = current_round.player_states[player_info.player_id]
        is_current = player_info.player_id == current_player_id
        _show_player_panel(player_info, player_state, engine, is_current, has_pending_action)

    st.markdown("---")

    # Pending action card target selection (shown once, outside player panels)
    _show_pending_action_card_dialog(game_state, engine)

    # Auto-save after each action
    _auto_save_game()


def _show_player_panel(player_info, player_state, engine, is_current_player: bool, has_pending_action: bool):
    """Show a single player's panel."""
    # Determine status
    if player_state.is_busted:
        status = "💥 BUSTED"
        color = "red"
    elif player_state.has_stayed:
        status = "✋ STAYED"
        color = "green"
    elif player_state.flip_three_active:
        status = f"🔄 FLIP THREE ({player_state.flip_three_count} cards left)"
        color = "orange"
    elif is_current_player:
        status = "🎯 YOUR TURN"
        color = "blue"
    else:
        status = "⏳ WAITING"
        color = "gray"

    with st.container():
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        with col1:
            st.markdown(f"### {player_info.name}")

        with col2:
            st.markdown(f"**Status:** :{color}[{status}]")

        with col3:
            if player_state.cards_in_hand:
                score_breakdown = calculate_score(player_state.cards_in_hand)
                st.metric("Round Score", score_breakdown.final_score)
            else:
                st.metric("Round Score", 0)

        with col4:
            st.metric("Total Score", player_state.total_score)

        # Show cards in hand
        if player_state.cards_in_hand:
            card_displays = [get_card_display(card) for card in player_state.cards_in_hand]
            st.markdown(f"**Cards:** {' '.join(card_displays)}")

            score_breakdown = calculate_score(player_state.cards_in_hand)
            breakdown_text = f"Base: {score_breakdown.base_score}"
            if score_breakdown.bonus_points > 0:
                breakdown_text += f" + Bonus: {score_breakdown.bonus_points}"
            if score_breakdown.multiplier > 1:
                breakdown_text += f" × {score_breakdown.multiplier}"
            if score_breakdown.has_flip_7:
                breakdown_text += f" + Flip 7: {score_breakdown.flip_7_bonus}"
            st.caption(breakdown_text)

            number_count = score_breakdown.number_card_count
            if number_count == 7:
                st.success(f"🎉 FLIP 7! ({number_count} number cards)")
            elif number_count >= 5:
                st.info(f"📊 {number_count}/7 number cards")

            from flip_7.core.rules import check_for_duplicate_cards
            if check_for_duplicate_cards(player_state.cards_in_hand):
                if player_state.has_second_chance:
                    st.warning("⚠️ DUPLICATE DETECTED! Use Second Chance to save yourself!")
                else:
                    st.error("💥 DUPLICATE - BUSTED! (Zero points this round)")
        else:
            st.caption("No cards yet")

        # Action buttons — only shown for the current active player
        if is_current_player and not player_state.has_stayed and not player_state.is_busted:
            col1, col2, col3 = st.columns(3)

            with col1:
                draw_label = (
                    f"🎲 Draw Card (forced, {player_state.flip_three_count} left)"
                    if player_state.flip_three_active
                    else "🎲 Draw Card"
                )
                if st.button(
                    draw_label,
                    key=f"draw_{player_info.player_id}",
                    use_container_width=True,
                    disabled=has_pending_action,
                    type="primary",
                ):
                    try:
                        drawn_card = engine.deal_card_to_player(player_info.player_id)
                        if isinstance(drawn_card, ActionCard):
                            st.session_state['pending_action_card'] = drawn_card
                            st.session_state['action_card_owner'] = player_info.player_id
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Error drawing card: {e}")

            with col2:
                can_stay = not player_state.flip_three_active
                if st.button(
                    "✋ Stay",
                    key=f"stay_{player_info.player_id}",
                    use_container_width=True,
                    disabled=not can_stay or has_pending_action,
                    type="secondary",
                ):
                    try:
                        engine.player_stay(player_info.player_id)
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Cannot stay: {e}")

            with col3:
                if player_state.has_second_chance:
                    if st.button(
                        "🎯 Use Second Chance",
                        key=f"second_{player_info.player_id}",
                        use_container_width=True,
                    ):
                        st.session_state[f'second_chance_{player_info.player_id}'] = True
                        st.rerun()

        # Second Chance dialog (current player only)
        if st.session_state.get(f'second_chance_{player_info.player_id}', False):
            with st.expander(f"🎯 Second Chance — Select Duplicate to Discard", expanded=True):
                number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]

                if not number_cards:
                    st.warning("No number cards to discard!")
                else:
                    card_counts = {}
                    for card in number_cards:
                        card_counts[card.value] = card_counts.get(card.value, 0) + 1

                    duplicates = {val: count for val, count in card_counts.items() if count > 1}

                    if not duplicates:
                        st.warning("No duplicate cards found!")
                    else:
                        st.markdown("Select a duplicate card to discard:")
                        for value, count in duplicates.items():
                            if st.button(
                                f"Discard {value} ({count} cards)",
                                key=f"discard_{player_info.player_id}_{value}",
                            ):
                                card_to_discard = next(c for c in number_cards if c.value == value)
                                try:
                                    engine.use_second_chance(player_info.player_id, card_to_discard)
                                    st.session_state[f'second_chance_{player_info.player_id}'] = False
                                    st.success(f"Discarded {value}!")
                                    st.rerun()
                                except ValueError as e:
                                    st.error(f"Error: {e}")

                if st.button("❌ Cancel", key=f"cancel_second_{player_info.player_id}"):
                    st.session_state[f'second_chance_{player_info.player_id}'] = False
                    st.rerun()


def _show_pending_action_card_dialog(game_state, engine):
    """Show the target-selection dialog for a pending action card."""
    if st.session_state.get('pending_action_card') is None:
        return

    action_card = st.session_state['pending_action_card']
    owner_id = st.session_state['action_card_owner']
    owner_name = next((p.name for p in game_state.players if p.player_id == owner_id), "Unknown")

    with st.expander(f"🎯 {action_card.action_type.value.replace('_', ' ').title()} — Select Target", expanded=True):
        eligible_targets = []
        for pid, pstate in game_state.current_round.player_states.items():
            if not pstate.has_stayed:
                pname = next((p.name for p in game_state.players if p.player_id == pid), pid)
                eligible_targets.append((pid, pname))

        if action_card.action_type == ActionType.SECOND_CHANCE:
            owner_state = game_state.current_round.player_states[owner_id]
            if not owner_state.has_second_chance:
                st.info(f"First Second Chance — automatically kept by {owner_name}")
                try:
                    engine.apply_action_card_effect(action_card, owner_id, owner_id)
                    del st.session_state['pending_action_card']
                    del st.session_state['action_card_owner']
                    st.rerun()
                except ValueError as e:
                    st.error(f"Error: {e}")
            else:
                st.warning(f"{owner_name} already has a Second Chance — must give this one to an opponent")
                opponent_targets = [(pid, pname) for pid, pname in eligible_targets if pid != owner_id]

                if not opponent_targets:
                    st.error("No eligible opponents to give Second Chance to!")
                else:
                    for target_id, target_name in opponent_targets:
                        if st.button(f"Give to {target_name}", key=f"sc_target_{target_id}"):
                            try:
                                engine.apply_action_card_effect(action_card, target_id, owner_id)
                                del st.session_state['pending_action_card']
                                del st.session_state['action_card_owner']
                                st.success(f"Gave Second Chance to {target_name}")
                                st.rerun()
                            except ValueError as e:
                                st.error(f"Error: {e}")

        elif action_card.action_type == ActionType.FLIP_THREE:
            st.markdown(f"**{owner_name}** drew Flip Three — choose who must take 3 cards:")
            for target_id, target_name in eligible_targets:
                label = "Apply to self" if target_id == owner_id else f"Apply to {target_name}"
                if st.button(label, key=f"ft_target_{target_id}"):
                    try:
                        engine.apply_action_card_effect(action_card, target_id, owner_id)
                        del st.session_state['pending_action_card']
                        del st.session_state['action_card_owner']
                        st.success(f"Applied Flip Three to {target_name}")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Error: {e}")

        elif action_card.action_type == ActionType.FREEZE:
            st.markdown(f"**{owner_name}** drew Freeze — choose who to freeze:")
            for target_id, target_name in eligible_targets:
                target_state = game_state.current_round.player_states[target_id]
                score_preview = calculate_score(target_state.cards_in_hand).final_score
                label = (
                    f"Freeze self (banks {score_preview} pts)"
                    if target_id == owner_id
                    else f"Freeze {target_name} (banks {score_preview} pts)"
                )
                if st.button(label, key=f"freeze_target_{target_id}"):
                    try:
                        engine.apply_action_card_effect(action_card, target_id, owner_id)
                        del st.session_state['pending_action_card']
                        del st.session_state['action_card_owner']
                        st.success(f"Froze {target_name} with {score_preview} points")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Error: {e}")

    st.markdown("---")


def _auto_save_game():
    """Auto-save the game after each action."""
    if st.session_state.get('auto_save', True):
        try:
            repo = GameRepository()
            repo.save_game(st.session_state.game_state, st.session_state.event_logger)
        except Exception:
            pass  # Silently fail auto-save