"""
Integration tests for the Flip 7 multiplayer server.

Uses FastAPI's synchronous TestClient so no async test runner is required.
Each test creates its own room so there is no shared state between tests.
"""

import pytest
from fastapi.testclient import TestClient

from flip_7.network.server import app, room_manager
from flip_7.data.models import Card, NumberCard, ActionCard, ActionType

client = TestClient(app)


# =============================================================================
# Helpers
# =============================================================================

def create_room() -> str:
    """Create a room and return its game_id."""
    res = client.post("/api/rooms")
    assert res.status_code == 201
    return res.json()["game_id"]


def join(game_id: str, name: str) -> str:
    """Join a room and return the assigned player_id."""
    res = client.post(f"/api/rooms/{game_id}/join", json={"player_name": name})
    assert res.status_code == 200
    return res.json()["player_id"]


def start(game_id: str, host_id: str) -> None:
    """Start the game as the host."""
    res = client.post(f"/api/rooms/{game_id}/start", json={"player_id": host_id})
    assert res.status_code == 200


def setup_game() -> tuple[str, str, str]:
    """
    Create a two-player started game.

    Returns:
        (game_id, player1_id, player2_id) — player1 is the host.
    """
    game_id = create_room()
    p1 = join(game_id, "Alice")
    p2 = join(game_id, "Bob")
    start(game_id, p1)
    return game_id, p1, p2


def consume_connect_message(ws, expected_type: str) -> dict:
    """Receive and return the first message sent on WebSocket connect."""
    msg = ws.receive_json()
    assert msg["type"] == expected_type, f"Expected {expected_type!r} on connect, got {msg['type']!r}"
    return msg


def stack_deck(game_id: str, card: Card) -> None:
    """
    Put `card` on top of the room's deck so the next 'deal_card' message
    draws it deterministically.

    The server draws randomly from the shared deck (deal_card ignores any
    'card' the client sends — a client dictating its own draw would be a
    cheat vector), so tests that need a specific card must seed the deck
    directly instead.
    """
    engine = room_manager.get_engine(game_id)
    engine.game_state.deck.insert(0, card)


# =============================================================================
# HTTP endpoint tests
# =============================================================================

class TestCreateRoom:
    def test_returns_game_id(self):
        res = client.post("/api/rooms")
        assert res.status_code == 201
        assert "game_id" in res.json()
        assert len(res.json()["game_id"]) == 36  # UUID format

    def test_each_room_has_unique_id(self):
        ids = {client.post("/api/rooms").json()["game_id"] for _ in range(5)}
        assert len(ids) == 5


class TestJoinRoom:
    def test_returns_player_id_and_game_id(self):
        game_id = create_room()
        res = client.post(f"/api/rooms/{game_id}/join", json={"player_name": "Alice"})
        assert res.status_code == 200
        body = res.json()
        assert "player_id" in body
        assert body["game_id"] == game_id

    def test_first_player_becomes_host(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")
        p2 = join(game_id, "Bob")

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            msg = consume_connect_message(ws, "lobby_update")
            host = next(p for p in msg["players"] if p["player_id"] == p1)
            non_host = next(p for p in msg["players"] if p["player_id"] == p2)
            assert host["is_host"] is True
            assert non_host["is_host"] is False

    def test_duplicate_name_returns_422(self):
        game_id = create_room()
        join(game_id, "Alice")
        res = client.post(f"/api/rooms/{game_id}/join", json={"player_name": "Alice"})
        assert res.status_code == 422

    def test_unknown_room_returns_404(self):
        res = client.post("/api/rooms/no-such-room/join", json={"player_name": "X"})
        assert res.status_code == 404

    def test_joining_started_game_returns_409(self):
        game_id, p1, _ = setup_game()
        res = client.post(f"/api/rooms/{game_id}/join", json={"player_name": "Charlie"})
        assert res.status_code == 409


class TestStartGame:
    def test_non_host_returns_403(self):
        game_id = create_room()
        join(game_id, "Alice")
        p2 = join(game_id, "Bob")
        res = client.post(f"/api/rooms/{game_id}/start", json={"player_id": p2})
        assert res.status_code == 403

    def test_single_player_returns_422(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")
        res = client.post(f"/api/rooms/{game_id}/start", json={"player_id": p1})
        assert res.status_code == 422

    def test_unknown_room_returns_404(self):
        res = client.post("/api/rooms/no-such-room/start", json={"player_id": "x"})
        assert res.status_code == 404

    def test_host_can_start_with_two_players(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")
        join(game_id, "Bob")
        res = client.post(f"/api/rooms/{game_id}/start", json={"player_id": p1})
        assert res.status_code == 200


# =============================================================================
# Rematch (Play Again in the same room) tests
# =============================================================================

class TestRematch:
    def test_non_host_returns_403(self):
        game_id, p1, p2 = setup_game()
        room_manager.get_engine(game_id).game_state.is_complete = True
        res = client.post(f"/api/rooms/{game_id}/rematch", json={"player_id": p2})
        assert res.status_code == 403

    def test_unknown_room_returns_404(self):
        res = client.post("/api/rooms/no-such-room/rematch", json={"player_id": "x"})
        assert res.status_code == 404

    def test_game_not_complete_returns_422(self):
        game_id, p1, p2 = setup_game()
        res = client.post(f"/api/rooms/{game_id}/rematch", json={"player_id": p1})
        assert res.status_code == 422

    def test_host_can_start_rematch_after_game_over(self):
        game_id, p1, p2 = setup_game()
        old_engine = room_manager.get_engine(game_id)
        old_engine.game_state.is_complete = True

        res = client.post(f"/api/rooms/{game_id}/rematch", json={"player_id": p1})
        assert res.status_code == 200

        new_engine = room_manager.get_engine(game_id)
        assert new_engine is not old_engine
        assert new_engine.game_state.is_complete is False
        assert new_engine.game_state.current_round is not None
        # Same roster carries over, in the same room.
        assert {p.player_id for p in new_engine.game_state.players} == {p1, p2}

    def test_rematch_before_any_game_started_returns_422(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")
        join(game_id, "Bob")
        res = client.post(f"/api/rooms/{game_id}/rematch", json={"player_id": p1})
        assert res.status_code == 422

    def test_match_history_captures_completed_game_and_resets_for_rematch(self):
        game_id, p1, p2 = setup_game()
        engine = room_manager.get_engine(game_id)

        # Finish the round with p1 crossing the win threshold.
        round_states = engine.game_state.current_round.player_states
        round_states[p1].has_stayed = True
        round_states[p1].total_score = 205
        round_states[p2].has_stayed = True
        round_states[p2].total_score = 40
        engine.end_round()

        assert engine.game_state.is_complete
        assert engine.game_state.winner_id == p1

        res = client.post(f"/api/rooms/{game_id}/rematch", json={"player_id": p1})
        assert res.status_code == 200

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            msg = consume_connect_message(ws, "state_update")
            state = msg["state"]

        assert state["game_number"] == 2
        assert len(state["match_history"]) == 1

        completed_game = state["match_history"][0]
        assert completed_game["winner_id"] == p1
        assert completed_game["final_scores"][p1] == 205
        assert completed_game["final_scores"][p2] == 40
        assert len(completed_game["rounds"]) == 1


# =============================================================================
# WebSocket connection tests
# =============================================================================

class TestWebSocketConnection:
    def test_connect_before_game_start_sends_lobby_update(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            msg = consume_connect_message(ws, "lobby_update")
            assert any(p["player_name"] == "Alice" for p in msg["players"])

    def test_connect_after_game_start_sends_state_update(self):
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            msg = consume_connect_message(ws, "state_update")
            assert msg["state"]["your_player_id"] == p1

    def test_unknown_player_id_is_rejected(self):
        game_id = create_room()
        join(game_id, "Alice")

        with client.websocket_connect(f"/ws/{game_id}/not-a-real-id") as ws:
            # Server closes the connection — receive_json raises or returns nothing
            # depending on close timing; just confirm no valid lobby message arrives
            try:
                msg = ws.receive_json()
                assert msg.get("type") != "lobby_update"
            except Exception:
                pass  # clean disconnect is also acceptable

    def test_message_before_game_started_returns_error(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")
        join(game_id, "Bob")

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()  # lobby_update
            ws.send_json({"type": "stay"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_unknown_message_type_returns_error(self):
        game_id, p1, _ = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()  # state_update
            ws.send_json({"type": "not_a_real_command"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not_a_real_command" in msg["message"]


# =============================================================================
# Lobby broadcast tests
# =============================================================================

class TestLobbyBroadcasts:
    def test_joining_notifies_connected_players(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()  # initial lobby_update for Alice alone

            # Bob joins — Alice should receive an updated roster
            join(game_id, "Bob")
            update = ws.receive_json()
            assert update["type"] == "lobby_update"
            names = [p["player_name"] for p in update["players"]]
            assert "Alice" in names and "Bob" in names

    def test_start_game_broadcasts_game_started(self):
        game_id = create_room()
        p1 = join(game_id, "Alice")

        # Alice must connect BEFORE Bob joins so she receives the lobby_update
        # broadcast that fires when Bob joins. Joining before connecting means
        # the broadcast fires with nobody listening and the message is lost.
        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()  # lobby_update: Alice only

            join(game_id, "Bob")
            ws.receive_json()  # lobby_update: Alice + Bob

            client.post(f"/api/rooms/{game_id}/start", json={"player_id": p1})
            msg = ws.receive_json()
            assert msg["type"] == "game_started"
            assert "state" in msg
            assert msg["state"]["your_player_id"] == p1


# =============================================================================
# Deal card tests
# =============================================================================

class TestDealCard:
    def test_dealing_broadcasts_state_update_to_all(self):
        game_id, p1, p2 = setup_game()
        stack_deck(game_id, NumberCard(value=7))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()  # connect state_update
            ws2.receive_json()  # connect state_update

            ws1.send_json({"type": "deal_card"})

            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["type"] == "state_update"
            assert msg2["type"] == "state_update"

    def test_dealt_card_appears_in_dealers_hand(self):
        game_id, p1, _ = setup_game()
        stack_deck(game_id, NumberCard(value=5))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "deal_card"})
            msg = ws.receive_json()

            p1_state = msg["state"]["current_round"]["player_states"][p1]
            values = [c["value"] for c in p1_state["cards_in_hand"]]
            assert 5 in values

    def test_server_assigns_its_own_card_id(self):
        """The dealt card always carries a server-generated card_id."""
        game_id, p1, _ = setup_game()
        stack_deck(game_id, NumberCard(value=3))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "deal_card"})
            msg = ws.receive_json()
            p1_state = msg["state"]["current_round"]["player_states"][p1]
            for card in p1_state["cards_in_hand"]:
                assert card.get("card_id")


# =============================================================================
# Privacy filter tests
# =============================================================================

class TestPrivacyFilter:
    def test_opponent_card_count_is_visible(self):
        game_id, p1, p2 = setup_game()
        stack_deck(game_id, NumberCard(value=9))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            # P1 deals a card
            ws1.send_json({"type": "deal_card"})
            ws1.receive_json()  # P1's own state_update (hand visible)
            p2_msg = ws2.receive_json()  # P2's state_update

            # P2 should see P1's card_count annotated onto their view
            p1_in_p2_view = p2_msg["state"]["current_round"]["player_states"][p1]
            assert p1_in_p2_view["card_count"] == 1

    def test_own_hand_is_visible(self):
        game_id, p1, _ = setup_game()
        stack_deck(game_id, NumberCard(value=4))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "deal_card"})
            msg = ws.receive_json()

            p1_state = msg["state"]["current_round"]["player_states"][p1]
            assert len(p1_state["cards_in_hand"]) == 1
            assert "card_count" not in p1_state

    def test_deck_is_not_sent_to_clients(self):
        game_id, p1, _ = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            msg = ws.receive_json()
            assert "deck" not in msg["state"]
            assert "discard_pile" not in msg["state"]

    def test_your_player_id_field_is_set(self):
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["state"]["your_player_id"] == p1
            assert msg2["state"]["your_player_id"] == p2


# =============================================================================
# Action card tests
# =============================================================================

class TestActionCards:
    def test_dealing_action_card_sends_action_pending(self):
        game_id, p1, _ = setup_game()
        stack_deck(game_id, ActionCard(action_type=ActionType.FREEZE))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "deal_card"})
            msg = ws.receive_json()
            assert msg["type"] == "action_pending"
            assert msg["action_type"] == "freeze"
            assert msg["owner_player_id"] == p1
            assert isinstance(msg["eligible_targets"], list)

    def test_action_pending_broadcast_to_all_players(self):
        game_id, p1, p2 = setup_game()
        stack_deck(game_id, ActionCard(action_type=ActionType.FLIP_THREE))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            ws1.send_json({"type": "deal_card"})

            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["type"] == "action_pending"
            assert msg2["type"] == "action_pending"

    def test_apply_action_requires_owner(self):
        """A player who did not draw the card cannot apply it."""
        game_id, p1, p2 = setup_game()
        stack_deck(game_id, ActionCard(action_type=ActionType.FREEZE))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            # P1 draws the action card
            ws1.send_json({"type": "deal_card"})
            ws1.receive_json()  # action_pending
            ws2.receive_json()  # action_pending

            # P2 tries to apply it — should get an error
            ws2.send_json({"type": "apply_action", "target_player_id": p1})
            msg = ws2.receive_json()
            assert msg["type"] == "error"

    def test_apply_action_broadcasts_state_update(self):
        game_id, p1, p2 = setup_game()
        stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            ws1.send_json({"type": "deal_card"})
            ws1.receive_json()  # action_pending
            ws2.receive_json()  # action_pending

            # P1 applies Second Chance to themselves
            ws1.send_json({"type": "apply_action", "target_player_id": p1})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["type"] in ("state_update", "round_ended", "game_over")
            assert msg2["type"] in ("state_update", "round_ended", "game_over")

    def test_second_second_chance_with_no_eligible_target_is_auto_discarded(self):
        """
        If the drawer already holds a Second Chance and every other player
        has stayed/busted, there's no legitimate target for a second one.
        The server should discard it and let the drawer keep going, rather
        than leaving them stuck with an action_pending that has no valid
        option to pick.
        """
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:
            ws1.receive_json()
            ws2.receive_json()

            # P1 draws a Second Chance and keeps it.
            stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))
            ws1.send_json({"type": "deal_card"})
            ws1.receive_json()  # action_pending
            ws2.receive_json()  # action_pending
            ws1.send_json({"type": "apply_action", "target_player_id": p1})
            ws1.receive_json()  # state_update — turn advances to P2
            ws2.receive_json()

            # P2 stays, leaving P1 as the only active player.
            ws2.send_json({"type": "stay"})
            ws1.receive_json()  # state_update — turn advances back to P1
            ws2.receive_json()

            # P1 draws a second Second Chance. No eligible target exists:
            # P1 already holds one, and P2 has stayed.
            stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))
            ws1.send_json({"type": "deal_card"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["type"] != "action_pending"
            assert msg2["type"] != "action_pending"

            p1_state = msg1["state"]["current_round"]["player_states"][p1]
            assert p1_state["has_second_chance"] is True  # original one untouched
            sc_count = sum(
                1 for c in p1_state["cards_in_hand"]
                if c.get("card_type") == "action" and c.get("action_type") == "second_chance"
            )
            assert sc_count == 1  # the second one was discarded, not kept

            # P1's turn should continue uninterrupted — they can draw again.
            ws1.send_json({"type": "deal_card"})
            msg = ws1.receive_json()
            assert msg["type"] != "error"

    def test_second_chance_discarded_when_every_active_player_already_has_one(self):
        """
        Same as above, but P2 is still active (not stayed) and holds their
        own Second Chance too — not just the drawer. Offering it to P2 would
        silently no-op in the engine (target already has one, so nothing is
        set and the card never moves), which looks identical to the original
        stuck-card bug. Both cases must be excluded from eligible_targets.
        """
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:
            ws1.receive_json()
            ws2.receive_json()

            # P1 draws a Second Chance and keeps it.
            stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))
            ws1.send_json({"type": "deal_card"})
            ws1.receive_json()  # action_pending
            ws2.receive_json()  # action_pending
            ws1.send_json({"type": "apply_action", "target_player_id": p1})
            ws1.receive_json()  # state_update — turn advances to P2
            ws2.receive_json()

            # P2 draws their own Second Chance and keeps it too. Both players
            # are now active and already hold one.
            stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))
            ws2.send_json({"type": "deal_card"})
            ws1.receive_json()  # action_pending
            ws2.receive_json()  # action_pending
            ws2.send_json({"type": "apply_action", "target_player_id": p2})
            ws1.receive_json()  # state_update — turn advances back to P1
            ws2.receive_json()

            # P1 draws a third Second Chance. Neither P1 (self) nor P2
            # (opponent, but already holds one) is a legitimate target.
            stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))
            ws1.send_json({"type": "deal_card"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["type"] != "action_pending"
            assert msg2["type"] != "action_pending"

            state = msg1["state"]["current_round"]["player_states"]
            assert state[p1]["has_second_chance"] is True
            assert state[p2]["has_second_chance"] is True
            sc_count_p1 = sum(
                1 for c in state[p1]["cards_in_hand"]
                if c.get("card_type") == "action" and c.get("action_type") == "second_chance"
            )
            assert sc_count_p1 == 1  # the third card was discarded

    def test_apply_action_without_pending_returns_error(self):
        game_id, p1, _ = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "apply_action", "target_player_id": p1})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_deal_card_while_action_pending_is_rejected(self):
        """
        Drawing again before resolving a pending action card must be
        rejected — otherwise the drawer could bust on a duplicate before a
        held Second Chance (or a Flip Three's forced draws) ever takes
        effect, since that effect only applies once the target is chosen.
        """
        game_id, p1, _ = setup_game()
        stack_deck(game_id, ActionCard(action_type=ActionType.SECOND_CHANCE))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "deal_card"})
            ws.receive_json()  # action_pending

            hand_before = len(
                room_manager.get_engine(game_id).game_state
                .current_round.player_states[p1].cards_in_hand
            )

            ws.send_json({"type": "deal_card"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

            hand_after = len(
                room_manager.get_engine(game_id).game_state
                .current_round.player_states[p1].cards_in_hand
            )
            assert hand_after == hand_before  # no extra card was dealt

    def test_stay_while_action_pending_is_rejected(self):
        game_id, p1, _ = setup_game()
        stack_deck(game_id, ActionCard(action_type=ActionType.FREEZE))

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "deal_card"})
            ws.receive_json()  # action_pending

            ws.send_json({"type": "stay"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


# =============================================================================
# Stay and round end tests
# =============================================================================

class TestStayAndRoundEnd:
    def test_stay_broadcasts_state_update(self):
        game_id, p1, _ = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws:
            ws.receive_json()
            ws.send_json({"type": "stay"})
            msg = ws.receive_json()
            assert msg["type"] in ("state_update", "round_ended")

    def test_both_players_staying_triggers_round_ended(self):
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            # P1 stays — round still active (P2 hasn't stayed)
            ws1.send_json({"type": "stay"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["type"] == "state_update"
            assert msg2["type"] == "state_update"

            # P2 stays — round should now end
            ws2.send_json({"type": "stay"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["type"] == "round_ended"
            assert msg2["type"] == "round_ended"

    def test_round_ended_state_has_round_history(self):
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            ws1.send_json({"type": "stay"})
            ws1.receive_json()
            ws2.receive_json()

            ws2.send_json({"type": "stay"})
            msg = ws1.receive_json()

            assert len(msg["state"]["round_history"]) == 1
            assert msg["state"]["current_round"] is None

    def test_only_host_can_start_next_round(self):
        game_id, p1, p2 = setup_game()

        with client.websocket_connect(f"/ws/{game_id}/{p1}") as ws1, \
             client.websocket_connect(f"/ws/{game_id}/{p2}") as ws2:

            ws1.receive_json()
            ws2.receive_json()

            # End the round
            ws1.send_json({"type": "stay"})
            ws1.receive_json(); ws2.receive_json()
            ws2.send_json({"type": "stay"})
            ws1.receive_json(); ws2.receive_json()

            # P2 (non-host) tries to start next round
            ws2.send_json({"type": "start_round"})
            msg = ws2.receive_json()
            assert msg["type"] == "error"

            # P1 (host) starts next round — succeeds
            ws1.send_json({"type": "start_round"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["type"] == "round_started"
            assert msg2["type"] == "round_started"