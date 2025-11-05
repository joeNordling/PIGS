"""
Card picker component for selecting cards to deal.
"""

import streamlit as st
from flip_7.data.models import NumberCard, ActionCard, ModifierCard, ActionType, ModifierType


def show_card_picker(player_name: str):
    """
    Show a card picker dialog and return the selected card.

    Args:
        player_name: Name of the player receiving the card

    Returns:
        Card object or None if cancelled
    """
    st.markdown(f"### 🎴 Deal Card to {player_name}")

    # Card type selector
    card_type = st.radio(
        "Select Card Type",
        ["Number Card", "Modifier Card", "Action Card"],
        horizontal=True,
        label_visibility="collapsed"
    )

    selected_card = None

    if card_type == "Number Card":
        selected_card = _pick_number_card()
    elif card_type == "Modifier Card":
        selected_card = _pick_modifier_card()
    elif card_type == "Action Card":
        selected_card = _pick_action_card()

    return selected_card


def _pick_number_card():
    """Show number card picker."""
    st.markdown("#### Number Cards")

    st.markdown("""
    Select the value of the number card. Number cards are the primary scoring mechanism.
    Each value appears N times in the deck (where N = value, except 0 appears once).
    """)

    # Row 1: 12, 11, 10, 9
    cols = st.columns(4)
    for i, value in enumerate([12, 11, 10, 9]):
        with cols[i]:
            if st.button(f"🎴 {value}", use_container_width=True, key=f"num_{value}", type="primary"):
                return NumberCard(value=value)
            st.caption(f"{value} in deck")

    # Row 2: 8, 7, 6, 5
    cols = st.columns(4)
    for i, value in enumerate([8, 7, 6, 5]):
        with cols[i]:
            if st.button(f"🎴 {value}", use_container_width=True, key=f"num_{value}", type="primary"):
                return NumberCard(value=value)
            st.caption(f"{value} in deck")

    # Row 3: 4, 3, 2, 1
    cols = st.columns(4)
    for i, value in enumerate([4, 3, 2, 1]):
        with cols[i]:
            if st.button(f"🎴 {value}", use_container_width=True, key=f"num_{value}", type="primary"):
                return NumberCard(value=value)
            st.caption(f"{value} in deck")

    # Row 4: 0
    cols = st.columns(4)
    with cols[0]:
        if st.button("🎴 0", use_container_width=True, key="num_0", type="primary"):
            return NumberCard(value=0)
        st.caption("1 in deck")

    return None


def _pick_modifier_card():
    """Show modifier card picker."""
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
            if st.button(f"🎴 {label}", use_container_width=True, key=f"mod_{label}"):
                return ModifierCard(modifier_type=mod_type, value=value)
            st.caption("1 in deck")

    st.markdown("**Multiplier Modifiers** (multiply number card total)")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🎴 ×2", use_container_width=True, key="mod_x2", type="primary"):
            return ModifierCard(modifier_type=ModifierType.MULTIPLY_2, value=2)
        st.caption("1 in deck")

    return None


def _pick_action_card():
    """Show action card picker."""
    st.markdown("#### Action Cards")

    st.markdown("""
    Action cards trigger special effects when dealt to a player.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("❄️ Freeze", use_container_width=True, key="action_freeze", type="primary"):
            st.info("Player banks points and must stay")
            return ActionCard(action_type=ActionType.FREEZE)
        st.caption("3 in deck")
        st.markdown("**Effect:** Player banks their current points and their turn ends immediately.")

    with col2:
        if st.button("🔄 Flip Three", use_container_width=True, key="action_flip3", type="primary"):
            st.info("Player must take next 3 cards")
            return ActionCard(action_type=ActionType.FLIP_THREE)
        st.caption("3 in deck")
        st.markdown("**Effect:** Player must accept the next 3 cards before they can stay.")

    with col3:
        if st.button("🎯 Second Chance", use_container_width=True, key="action_second", type="primary"):
            st.info("Allows discarding a duplicate")
            return ActionCard(action_type=ActionType.SECOND_CHANCE)
        st.caption("3 in deck")
        st.markdown("**Effect:** Player can hold this card to discard a duplicate number card later.")

    return None


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
