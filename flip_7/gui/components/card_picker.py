"""
Card picker component for selecting cards to deal.
"""

import streamlit as st
from typing import List, Optional
from flip_7.data.models import NumberCard, ActionCard, ModifierCard, ActionType, ModifierType, Card
from flip_7.core.rules import calculate_score


def show_card_picker(player_name: str, player_id: str, current_cards: List[Card] = None):
    """
    Show a card picker dialog and return the selected card(s).

    Args:
        player_name: Name of the player receiving the card
        player_id: ID of the player (for session state tracking)
        current_cards: Current cards in player's hand (for preview)

    Returns:
        Card object, list of Cards, or None if cancelled/no selection
    """
    st.markdown(f"### 🎴 Deal Card to {player_name}")

    # Initialize session state for this player
    draft_key = f'draft_cards_{player_id}'
    mode_key = f'card_picker_mode_{player_id}'

    if draft_key not in st.session_state:
        st.session_state[draft_key] = []
    if mode_key not in st.session_state:
        st.session_state[mode_key] = 'single'

    # Mode toggle
    col1, col2 = st.columns([1, 3])
    with col1:
        mode = st.radio(
            "Selection Mode",
            ["Single", "Multi"],
            key=f"mode_toggle_{player_id}",
            horizontal=True,
            index=0 if st.session_state[mode_key] == 'single' else 1
        )
        st.session_state[mode_key] = mode.lower()

    with col2:
        if st.session_state[mode_key] == 'multi':
            count = len(st.session_state[draft_key])
            st.markdown(f"**{count} card{'s' if count != 1 else ''} selected**")

    st.markdown("---")

    # Card type selector
    card_type = st.radio(
        "Select Card Type",
        ["Number Card", "Modifier Card", "Action Card"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"card_type_{player_id}"
    )

    # Branch based on mode
    if st.session_state[mode_key] == 'single':
        # Single-select mode (original behavior)
        selected_card = None
        if card_type == "Number Card":
            selected_card = _pick_number_card(player_id)
        elif card_type == "Modifier Card":
            selected_card = _pick_modifier_card(player_id)
        elif card_type == "Action Card":
            selected_card = _pick_action_card(player_id)
        return selected_card
    else:
        # Multi-select mode (new behavior)
        return _show_multi_select_picker(player_id, player_name, card_type, current_cards)


def _pick_number_card(player_id: str):
    """Show number card picker (single-select mode)."""
    st.markdown("#### Number Cards")

    st.markdown("""
    Select the value of the number card. Number cards are the primary scoring mechanism.
    Each value appears N times in the deck (where N = value, except 0 appears once).
    """)

    # Row 1: 12, 11, 10, 9
    cols = st.columns(4)
    for i, value in enumerate([12, 11, 10, 9]):
        with cols[i]:
            if st.button(f"🎴 {value}", use_container_width=True, key=f"num_{value}_{player_id}", type="primary"):
                return NumberCard(value=value)
            st.caption(f"{value} in deck")

    # Row 2: 8, 7, 6, 5
    cols = st.columns(4)
    for i, value in enumerate([8, 7, 6, 5]):
        with cols[i]:
            if st.button(f"🎴 {value}", use_container_width=True, key=f"num_{value}_{player_id}", type="primary"):
                return NumberCard(value=value)
            st.caption(f"{value} in deck")

    # Row 3: 4, 3, 2, 1
    cols = st.columns(4)
    for i, value in enumerate([4, 3, 2, 1]):
        with cols[i]:
            if st.button(f"🎴 {value}", use_container_width=True, key=f"num_{value}_{player_id}", type="primary"):
                return NumberCard(value=value)
            st.caption(f"{value} in deck")

    # Row 4: 0
    cols = st.columns(4)
    with cols[0]:
        if st.button("🎴 0", use_container_width=True, key=f"num_0_{player_id}", type="primary"):
            return NumberCard(value=0)
        st.caption("1 in deck")

    return None


def _pick_modifier_card(player_id: str):
    """Show modifier card picker (single-select mode)."""
    st.markdown("#### Modifier Cards")

    st.markdown("**Bonus Point Modifiers** (add to score)")

    # Bonus modifiers - only +2, +4, +6, +8, +10 (1 each)
    cols = st.columns(5)
    modifiers = [
        (ModifierType.PLUS_2, 2, "+2"),
        (ModifierType.PLUS_4, 4, "+4"),
        (ModifierType.PLUS_6, 6, "+6"),
        (ModifierType.PLUS_8, 8, "+8"),
        (ModifierType.PLUS_10, 10, "+10"),
    ]

    for i, (mod_type, value, label) in enumerate(modifiers):
        with cols[i]:
            if st.button(f"🎴 {label}", use_container_width=True, key=f"mod_{label}_{player_id}"):
                return ModifierCard(modifier_type=mod_type, value=value)
            st.caption("1 in deck")

    st.markdown("**Multiplier Modifiers** (multiply number card total)")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🎴 ×2", use_container_width=True, key=f"mod_x2_{player_id}", type="primary"):
            return ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        st.caption("1 in deck")

    return None


def _pick_action_card(player_id: str):
    """Show action card picker (single-select mode)."""
    st.markdown("#### Action Cards")

    st.markdown("""
    Action cards trigger special effects when dealt to a player.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("❄️ Freeze", use_container_width=True, key=f"action_freeze_{player_id}", type="primary"):
            st.info("Player banks points and must stay")
            return ActionCard(action_type=ActionType.FREEZE)
        st.caption("3 in deck")
        st.markdown("**Effect:** Player banks their current points and their turn ends immediately.")

    with col2:
        if st.button("🔄 Flip Three", use_container_width=True, key=f"action_flip3_{player_id}", type="primary"):
            st.info("Player must take next 3 cards")
            return ActionCard(action_type=ActionType.FLIP_THREE)
        st.caption("3 in deck")
        st.markdown("**Effect:** Player must accept the next 3 cards before they can stay.")

    with col3:
        if st.button("🎯 Second Chance", use_container_width=True, key=f"action_second_{player_id}", type="primary"):
            st.info("Allows discarding a duplicate")
            return ActionCard(action_type=ActionType.SECOND_CHANCE)
        st.caption("3 in deck")
        st.markdown("**Effect:** Player can hold this card to discard a duplicate number card later.")

    return None


def _show_multi_select_picker(player_id: str, player_name: str, card_type: str, current_cards: List[Card]):
    """
    Show multi-select card picker with checkboxes.

    Args:
        player_id: ID of the player
        player_name: Name of the player
        card_type: Type of cards to show (Number Card, Modifier Card, Action Card)
        current_cards: Current cards in player's hand (for preview)

    Returns:
        List of selected cards when Apply is clicked, None otherwise
    """
    draft_key = f'draft_cards_{player_id}'

    # Show card selection area
    if card_type == "Number Card":
        _show_number_card_checkboxes(player_id, draft_key)
    elif card_type == "Modifier Card":
        _show_modifier_card_checkboxes(player_id, draft_key)
    elif card_type == "Action Card":
        _show_action_card_checkboxes(player_id, draft_key)

    st.markdown("---")

    # Show preview if cards are selected
    if len(st.session_state[draft_key]) > 0:
        _show_preview(player_name, current_cards or [], st.session_state[draft_key])
        st.markdown("---")

    # Apply and Cancel buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("❌ Cancel", key=f"multi_cancel_{player_id}", use_container_width=True):
            st.session_state[draft_key] = []
            return None

    with col2:
        apply_disabled = len(st.session_state[draft_key]) == 0
        if st.button(
            "✅ Apply",
            key=f"multi_apply_{player_id}",
            use_container_width=True,
            type="primary",
            disabled=apply_disabled
        ):
            # Return the selected cards
            selected = st.session_state[draft_key].copy()
            st.session_state[draft_key] = []
            return selected

    return None


def _show_number_card_checkboxes(player_id: str, draft_key: str):
    """Show number card checkboxes for multi-select."""
    st.markdown("#### Number Cards")
    st.markdown("Select one or more number cards to deal.")

    # Row 1: 12, 11, 10, 9
    cols = st.columns(4)
    for i, value in enumerate([12, 11, 10, 9]):
        with cols[i]:
            card = NumberCard(value=value)
            checked = any(isinstance(c, NumberCard) and c.value == value for c in st.session_state[draft_key])
            if st.checkbox(
                f"🎴 {value}",
                value=checked,
                key=f"multi_num_{value}_{player_id}"
            ):
                if not checked:
                    st.session_state[draft_key].append(card)
            else:
                if checked:
                    st.session_state[draft_key] = [
                        c for c in st.session_state[draft_key]
                        if not (isinstance(c, NumberCard) and c.value == value)
                    ]
            st.caption(f"{value} in deck")

    # Row 2: 8, 7, 6, 5
    cols = st.columns(4)
    for i, value in enumerate([8, 7, 6, 5]):
        with cols[i]:
            card = NumberCard(value=value)
            checked = any(isinstance(c, NumberCard) and c.value == value for c in st.session_state[draft_key])
            if st.checkbox(
                f"🎴 {value}",
                value=checked,
                key=f"multi_num_{value}_{player_id}"
            ):
                if not checked:
                    st.session_state[draft_key].append(card)
            else:
                if checked:
                    st.session_state[draft_key] = [
                        c for c in st.session_state[draft_key]
                        if not (isinstance(c, NumberCard) and c.value == value)
                    ]
            st.caption(f"{value} in deck")

    # Row 3: 4, 3, 2, 1
    cols = st.columns(4)
    for i, value in enumerate([4, 3, 2, 1]):
        with cols[i]:
            card = NumberCard(value=value)
            checked = any(isinstance(c, NumberCard) and c.value == value for c in st.session_state[draft_key])
            if st.checkbox(
                f"🎴 {value}",
                value=checked,
                key=f"multi_num_{value}_{player_id}"
            ):
                if not checked:
                    st.session_state[draft_key].append(card)
            else:
                if checked:
                    st.session_state[draft_key] = [
                        c for c in st.session_state[draft_key]
                        if not (isinstance(c, NumberCard) and c.value == value)
                    ]
            st.caption(f"{value} in deck")

    # Row 4: 0
    cols = st.columns(4)
    with cols[0]:
        card = NumberCard(value=0)
        checked = any(isinstance(c, NumberCard) and c.value == 0 for c in st.session_state[draft_key])
        if st.checkbox(
            "🎴 0",
            value=checked,
            key=f"multi_num_0_{player_id}"
        ):
            if not checked:
                st.session_state[draft_key].append(card)
        else:
            if checked:
                st.session_state[draft_key] = [
                    c for c in st.session_state[draft_key]
                    if not (isinstance(c, NumberCard) and c.value == 0)
                ]
        st.caption("1 in deck")


def _show_modifier_card_checkboxes(player_id: str, draft_key: str):
    """Show modifier card checkboxes for multi-select."""
    st.markdown("#### Modifier Cards")

    st.markdown("**Bonus Point Modifiers** (add to score)")

    cols = st.columns(5)
    modifiers = [
        (ModifierType.PLUS_2, 2, "+2"),
        (ModifierType.PLUS_4, 4, "+4"),
        (ModifierType.PLUS_6, 6, "+6"),
        (ModifierType.PLUS_8, 8, "+8"),
        (ModifierType.PLUS_10, 10, "+10"),
    ]

    for i, (mod_type, value, label) in enumerate(modifiers):
        with cols[i]:
            card = ModifierCard(modifier_type=mod_type, value=value)
            checked = any(
                isinstance(c, ModifierCard) and c.modifier_type == mod_type
                for c in st.session_state[draft_key]
            )
            if st.checkbox(
                f"🎴 {label}",
                value=checked,
                key=f"multi_mod_{label}_{player_id}"
            ):
                if not checked:
                    st.session_state[draft_key].append(card)
            else:
                if checked:
                    st.session_state[draft_key] = [
                        c for c in st.session_state[draft_key]
                        if not (isinstance(c, ModifierCard) and c.modifier_type == mod_type)
                    ]
            st.caption("1 in deck")

    st.markdown("**Multiplier Modifiers** (multiply number card total)")

    cols = st.columns(5)
    with cols[0]:
        card = ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        checked = any(
            isinstance(c, ModifierCard) and c.modifier_type == ModifierType.MULTIPLY_2
            for c in st.session_state[draft_key]
        )
        if st.checkbox(
            "🎴 ×2",
            value=checked,
            key=f"multi_mod_x2_{player_id}"
        ):
            if not checked:
                st.session_state[draft_key].append(card)
        else:
            if checked:
                st.session_state[draft_key] = [
                    c for c in st.session_state[draft_key]
                    if not (isinstance(c, ModifierCard) and c.modifier_type == ModifierType.MULTIPLY_2)
                ]
        st.caption("1 in deck")


def _show_action_card_checkboxes(player_id: str, draft_key: str):
    """Show action card checkboxes for multi-select."""
    st.markdown("#### Action Cards")
    st.markdown("Select action cards to deal.")

    col1, col2, col3 = st.columns(3)

    with col1:
        card = ActionCard(action_type=ActionType.FREEZE)
        checked = any(
            isinstance(c, ActionCard) and c.action_type == ActionType.FREEZE
            for c in st.session_state[draft_key]
        )
        if st.checkbox(
            "❄️ Freeze",
            value=checked,
            key=f"multi_action_freeze_{player_id}"
        ):
            if not checked:
                st.session_state[draft_key].append(card)
        else:
            if checked:
                st.session_state[draft_key] = [
                    c for c in st.session_state[draft_key]
                    if not (isinstance(c, ActionCard) and c.action_type == ActionType.FREEZE)
                ]
        st.caption("3 in deck")
        st.markdown("**Effect:** Player banks their current points and their turn ends immediately.")

    with col2:
        card = ActionCard(action_type=ActionType.FLIP_THREE)
        checked = any(
            isinstance(c, ActionCard) and c.action_type == ActionType.FLIP_THREE
            for c in st.session_state[draft_key]
        )
        if st.checkbox(
            "🔄 Flip Three",
            value=checked,
            key=f"multi_action_flip3_{player_id}"
        ):
            if not checked:
                st.session_state[draft_key].append(card)
        else:
            if checked:
                st.session_state[draft_key] = [
                    c for c in st.session_state[draft_key]
                    if not (isinstance(c, ActionCard) and c.action_type == ActionType.FLIP_THREE)
                ]
        st.caption("3 in deck")
        st.markdown("**Effect:** Player must accept the next 3 cards before they can stay.")

    with col3:
        card = ActionCard(action_type=ActionType.SECOND_CHANCE)
        checked = any(
            isinstance(c, ActionCard) and c.action_type == ActionType.SECOND_CHANCE
            for c in st.session_state[draft_key]
        )
        if st.checkbox(
            "🎯 Second Chance",
            value=checked,
            key=f"multi_action_second_{player_id}"
        ):
            if not checked:
                st.session_state[draft_key].append(card)
        else:
            if checked:
                st.session_state[draft_key] = [
                    c for c in st.session_state[draft_key]
                    if not (isinstance(c, ActionCard) and c.action_type == ActionType.SECOND_CHANCE)
                ]
        st.caption("3 in deck")
        st.markdown("**Effect:** Player can hold this card to discard a duplicate number card later.")


def _show_preview(player_name: str, current_cards: List[Card], draft_cards: List[Card]):
    """
    Show preview of what the player's hand would look like after applying selected cards.

    Args:
        player_name: Name of the player
        current_cards: Current cards in player's hand
        draft_cards: Cards that will be added
    """
    st.markdown("#### 👁️ Preview")

    # Combine current and draft cards
    preview_cards = current_cards + draft_cards

    # Display cards
    card_displays = [get_card_display(card) for card in preview_cards]
    st.markdown(f"**{player_name}'s hand after applying:** {' '.join(card_displays)}")

    # Calculate and show projected score
    try:
        score_breakdown = calculate_score(preview_cards)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Projected Round Score", score_breakdown.final_score)
        with col2:
            st.metric("Number Cards", score_breakdown.number_card_count)

        # Show breakdown
        breakdown_text = f"Base: {score_breakdown.base_score}"
        if score_breakdown.bonus_points > 0:
            breakdown_text += f" + Bonus: {score_breakdown.bonus_points}"
        if score_breakdown.multiplier > 1:
            breakdown_text += f" × {score_breakdown.multiplier}"
        if score_breakdown.has_flip_7:
            breakdown_text += f" + Flip 7: {score_breakdown.flip_7_bonus}"

        st.caption(breakdown_text)

        # Warning if would bust
        from flip_7.core.rules import check_for_duplicate_cards
        if check_for_duplicate_cards(preview_cards):
            has_second_chance = any(
                isinstance(c, ActionCard) and c.action_type == ActionType.SECOND_CHANCE
                for c in preview_cards
            )
            if has_second_chance:
                st.warning("⚠️ Preview contains duplicates, but you have Second Chance!")
            else:
                st.error("💥 WARNING: This would result in a BUST (duplicate cards)!")

    except Exception as e:
        st.caption(f"Could not calculate preview score: {e}")


def get_card_display(card):
    """
    Get a nice display string for a card.

    Args:
        card: The card to display

    Returns:
        String representation of the card
    """
    if isinstance(card, NumberCard):
        return f"🎴 {card.value}"
    elif isinstance(card, ModifierCard):
        if card.modifier_type == ModifierType.MULTIPLY_2:
            return f"✖️ ×{card.value}"
        else:
            return f"➕ +{card.value}"
    elif isinstance(card, ActionCard):
        action_icons = {
            ActionType.FREEZE: "❄️ Freeze",
            ActionType.FLIP_THREE: "🔄 Flip Three",
            ActionType.SECOND_CHANCE: "🎯 Second Chance"
        }
        return action_icons.get(card.action_type, str(card.action_type.value))
    return str(card)
