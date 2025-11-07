"""
Game play component for active game tracking.
"""

import streamlit as st
from flip_7.data.models import NumberCard, ActionCard, ActionType
from flip_7.core.rules import calculate_score
from flip_7.gui.components.card_picker import show_card_picker, get_card_display
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

    st.markdown("---")

    # Player cards display
    st.markdown("### 👥 Players")

    for player_info in game_state.players:
        player_id = player_info.player_id
        player_state = current_round.player_states[player_id]

        _show_player_card(player_info, player_state, engine)

    st.markdown("---")

    # Auto-save after each action
    _auto_save_game()


def _show_player_card(player_info, player_state, engine):
    """Show a single player's card."""
    # Determine status and color
    if player_state.is_busted:
        status = "💥 BUSTED"
        color = "red"
    elif player_state.has_stayed:
        status = "✋ STAYED"
        color = "green"
    elif player_state.flip_three_active:
        status = f"🔄 FLIP THREE ({player_state.flip_three_count} cards left)"
        color = "orange"
    else:
        status = "▶️ ACTIVE"
        color = "blue"

    # Player header
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

        # Show cards
        if player_state.cards_in_hand:
            card_displays = [get_card_display(card) for card in player_state.cards_in_hand]
            st.markdown(f"**Cards:** {' '.join(card_displays)}")

            # Show score breakdown
            score_breakdown = calculate_score(player_state.cards_in_hand)
            breakdown_text = f"Base: {score_breakdown.base_score}"
            if score_breakdown.bonus_points > 0:
                breakdown_text += f" + Bonus: {score_breakdown.bonus_points}"
            if score_breakdown.multiplier > 1:
                breakdown_text += f" × {score_breakdown.multiplier}"
            if score_breakdown.has_flip_7:
                breakdown_text += f" + Flip 7: {score_breakdown.flip_7_bonus}"

            st.caption(breakdown_text)

            # Show number card count
            number_count = score_breakdown.number_card_count
            if number_count == 7:
                st.success(f"🎉 FLIP 7! ({number_count} number cards)")
            elif number_count >= 5:
                st.info(f"📊 {number_count}/7 number cards")

            # Check for duplicate cards (BUST condition!)
            from flip_7.core.rules import check_for_duplicate_cards
            if check_for_duplicate_cards(player_state.cards_in_hand):
                if player_state.has_second_chance:
                    st.warning("⚠️ DUPLICATE DETECTED! Use Second Chance to save yourself!")
                else:
                    st.error("💥 DUPLICATE - BUSTED! (Zero points this round)")
        else:
            st.caption("No cards yet")

        # Action buttons
        if not player_state.has_stayed and not player_state.is_busted:
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button(f"🎴 Deal Card", key=f"deal_{player_info.player_id}", use_container_width=True):
                    st.session_state[f'dealing_to_{player_info.player_id}'] = True
                    st.rerun()

            with col2:
                # Check if player can stay
                can_stay = not player_state.flip_three_active or player_state.flip_three_count == 0

                if st.button(
                    f"✋ Stay",
                    key=f"stay_{player_info.player_id}",
                    use_container_width=True,
                    disabled=not can_stay,
                    type="secondary"
                ):
                    try:
                        engine.player_stay(player_info.player_id)
                        st.success(f"{player_info.name} stayed!")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Cannot stay: {e}")

            with col3:
                # Second Chance button
                if player_state.has_second_chance:
                    if st.button(
                        f"🎯 Use Second Chance",
                        key=f"second_{player_info.player_id}",
                        use_container_width=True
                    ):
                        st.session_state[f'second_chance_{player_info.player_id}'] = True
                        st.rerun()

        # Card picker dialog
        if st.session_state.get(f'dealing_to_{player_info.player_id}', False):
            with st.expander(f"🎴 Select Card for {player_info.name}", expanded=True):
                selected_card = show_card_picker(
                    player_info.name,
                    player_info.player_id,
                    player_state.cards_in_hand
                )

                # Handle single-select mode (cancel button handled by card picker for multi-select)
                if selected_card is not None:
                    # Check if it's a list (multi-select) or single card
                    if isinstance(selected_card, list):
                        # Multi-select: deal cards sequentially
                        st.session_state[f'dealing_to_{player_info.player_id}'] = False
                        _deal_multiple_cards_sequentially(engine, player_info, selected_card)
                    else:
                        # Single-select: deal immediately
                        try:
                            engine.deal_card_to_player(player_info.player_id, selected_card)
                            st.session_state[f'dealing_to_{player_info.player_id}'] = False

                            # Check if it's an action card that needs target selection
                            if isinstance(selected_card, ActionCard):
                                # Store action card info for target selection
                                st.session_state['pending_action_card'] = selected_card
                                st.session_state['action_card_owner'] = player_info.player_id
                                st.success(f"Dealt {get_card_display(selected_card)} to {player_info.name} - Select target")
                            else:
                                st.success(f"Dealt {get_card_display(selected_card)} to {player_info.name}")

                            st.rerun()
                        except ValueError as e:
                            st.error(f"Error dealing card: {e}")

                # Cancel button for single-select mode
                if not isinstance(selected_card, list) and selected_card is None:
                    if st.button("❌ Cancel", key=f"cancel_deal_{player_info.player_id}"):
                        st.session_state[f'dealing_to_{player_info.player_id}'] = False
                        st.rerun()

        # Second Chance dialog
        if st.session_state.get(f'second_chance_{player_info.player_id}', False):
            with st.expander(f"🎯 Second Chance - Select Duplicate to Discard", expanded=True):
                number_cards = [c for c in player_state.cards_in_hand if isinstance(c, NumberCard)]

                if not number_cards:
                    st.warning("No number cards to discard!")
                else:
                    # Find duplicates
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
                                key=f"discard_{player_info.player_id}_{value}"
                            ):
                                # Find the card to discard
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

    # Action card target selection dialog
    if st.session_state.get('pending_action_card') is not None:
        action_card = st.session_state['pending_action_card']
        owner_id = st.session_state['action_card_owner']
        owner_name = next((p.name for p in game_state.players if p.player_id == owner_id), "Unknown")

        with st.expander(f"🎯 {action_card.action_type.value} - Select Target", expanded=True):
            # Get list of eligible targets (active players who haven't stayed)
            eligible_targets = []
            for pid, pstate in game_state.current_round.player_states.items():
                if not pstate.has_stayed:
                    pname = next((p.name for p in game_state.players if p.player_id == pid), pid)
                    eligible_targets.append((pid, pname))

            # Determine behavior based on action type
            if action_card.action_type == ActionType.SECOND_CHANCE:
                owner_state = game_state.current_round.player_states[owner_id]
                if not owner_state.has_second_chance:
                    # First Second Chance: auto-keep
                    st.info(f"First Second Chance - automatically kept by {owner_name}")
                    try:
                        engine.apply_action_card_effect(action_card, owner_id, owner_id)
                        del st.session_state['pending_action_card']
                        del st.session_state['action_card_owner']
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Error: {e}")
                else:
                    # Second Second Chance: must give to opponent
                    st.warning(f"{owner_name} already has a Second Chance - must give this one to an opponent")
                    opponent_targets = [(pid, pname) for pid, pname in eligible_targets if pid != owner_id]

                    if not opponent_targets:
                        st.error("No eligible opponents to give Second Chance to!")
                    else:
                        for target_id, target_name in opponent_targets:
                            if st.button(
                                f"Give to {target_name}",
                                key=f"sc_target_{target_id}"
                            ):
                                try:
                                    engine.apply_action_card_effect(action_card, target_id, owner_id)
                                    del st.session_state['pending_action_card']
                                    del st.session_state['action_card_owner']
                                    st.success(f"Gave Second Chance to {target_name}")
                                    st.rerun()
                                except ValueError as e:
                                    st.error(f"Error: {e}")

            elif action_card.action_type == ActionType.FLIP_THREE:
                st.markdown(f"**{owner_name}** drew Flip Three - choose who must take 3 cards:")
                for target_id, target_name in eligible_targets:
                    label = f"{'Apply to self' if target_id == owner_id else f'Apply to {target_name}'}"
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
                st.markdown(f"**{owner_name}** drew Freeze - choose who to freeze:")
                for target_id, target_name in eligible_targets:
                    target_state = game_state.current_round.player_states[target_id]
                    score_preview = calculate_score(target_state.cards_in_hand).final_score
                    label = f"{'Freeze self' if target_id == owner_id else f'Freeze {target_name}'} (banks {score_preview} pts)"
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


def _deal_multiple_cards_sequentially(engine, player_info, cards):
    """
    Deal multiple cards to a player sequentially with progress feedback.

    Args:
        engine: GameEngine instance
        player_info: PlayerInfo object for the player
        cards: List of Card objects to deal
    """
    success_count = 0
    total_cards = len(cards)

    with st.container():
        st.markdown(f"### 🎴 Dealing {total_cards} card{'s' if total_cards != 1 else ''} to {player_info.name}...")

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, card in enumerate(cards):
            try:
                # Deal the card
                engine.deal_card_to_player(player_info.player_id, card)

                # Auto-apply action cards in multi-select mode (always to self)
                if isinstance(card, ActionCard):
                    # In multi-select mode, action cards are auto-applied to the drawer
                    # For strategic targeting, use single-card mode
                    engine.apply_action_card_effect(card, player_info.player_id, player_info.player_id)

                success_count += 1

                # Update progress
                progress = (i + 1) / total_cards
                progress_bar.progress(progress)
                status_text.success(f"✅ Dealt {get_card_display(card)} ({i + 1}/{total_cards})")

                # Check if player busted or game state changed
                game_state = st.session_state.game_state
                if game_state.current_round is None:
                    # Round ended (e.g., FREEZE card on last player)
                    st.info(f"Round ended after dealing {success_count} card{'s' if success_count != 1 else ''}")
                    break

                player_state = game_state.current_round.player_states.get(player_info.player_id)
                if player_state and player_state.is_busted:
                    st.warning(f"💥 Player busted after {success_count} card{'s' if success_count != 1 else ''}! Stopping early.")
                    break

                if player_state and player_state.has_stayed:
                    st.info(f"Player stayed (FREEZE card) after {success_count} card{'s' if success_count != 1 else ''}! Stopping early.")
                    break

            except ValueError as e:
                st.error(f"❌ Error dealing {get_card_display(card)}: {e}")
                break

        # Final summary
        if success_count == total_cards:
            st.success(f"🎉 Successfully dealt all {total_cards} card{'s' if total_cards != 1 else ''} to {player_info.name}!")
        elif success_count > 0:
            st.warning(f"⚠️ Dealt {success_count} of {total_cards} cards before stopping")
        else:
            st.error(f"❌ Failed to deal any cards")

        # Add a rerun button
        if st.button("✅ Continue", key=f"continue_after_multi_deal_{player_info.player_id}", type="primary"):
            st.rerun()
