"""
FastAPI WebSocket server for Flip 7 multiplayer.

Run with:
    uvicorn flip_7.network.server:app --host 0.0.0.0 --port 8765
"""

import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from flip_7.data.models import ActionCard, NumberCard
from flip_7.data.persistence import deserialize_card
from flip_7.network.room_manager import RoomManager

app = FastAPI(title="Flip 7 Multiplayer")
room_manager = RoomManager()


# =============================================================================
# Request bodies
# =============================================================================

class JoinRequest(BaseModel):
    player_name: str


class StartRequest(BaseModel):
    player_id: str


# =============================================================================
# HTTP endpoints
# =============================================================================

@app.post("/api/rooms", status_code=status.HTTP_201_CREATED)
async def create_room():
    """Create a new game room. The first player to join becomes the host."""
    game_id = room_manager.create_room()
    return {"game_id": game_id}


@app.post("/api/rooms/{game_id}/join")
async def join_room(game_id: str, body: JoinRequest):
    """
    Join an existing room by name.

    Returns the player_id to use for all future requests and the WebSocket URL.
    """
    if not room_manager.room_exists(game_id):
        raise HTTPException(status_code=404, detail="Room not found")

    try:
        player_id = room_manager.join_room(game_id, body.player_name)
    except ValueError as e:
        code = status.HTTP_409_CONFLICT if "already started" in str(e) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(e))

    # Notify already-connected players that the roster has changed.
    await room_manager.broadcast(game_id, {
        "type": "lobby_update",
        "players": room_manager.get_player_list(game_id),
        "game_id": game_id,
    })

    return {"player_id": player_id, "game_id": game_id}


@app.post("/api/rooms/{game_id}/start")
async def start_game(game_id: str, body: StartRequest):
    """
    Start the game. Only the host may call this.

    Broadcasts a game_started message with the initial state to all connected players.
    """
    if not room_manager.room_exists(game_id):
        raise HTTPException(status_code=404, detail="Room not found")

    if not room_manager.is_host(game_id, body.player_id):
        raise HTTPException(status_code=403, detail="Only the host can start the game")

    try:
        room_manager.start_game(game_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    await room_manager.broadcast_state(game_id, message_type="game_started")
    return {"ok": True}


# =============================================================================
# WebSocket endpoint
# =============================================================================

@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    """
    Persistent per-player WebSocket connection.

    On connect: validate, register, and send the current state or lobby info.
    Message loop: dispatch incoming commands to handlers; broadcast updated state.
    On disconnect: deregister the connection.
    """
    await websocket.accept()

    if not room_manager.room_exists(game_id):
        await websocket.close(code=4004, reason="Room not found")
        return

    if not room_manager.player_in_room(game_id, player_id):
        await websocket.close(code=4003, reason="Player not in room")
        return

    try:
        room_manager.register_connection(game_id, player_id, websocket)
    except ValueError as e:
        await websocket.close(code=4008, reason=str(e))
        return

    # Send initial state: game state if started, lobby roster otherwise.
    if room_manager.get_engine(game_id) is not None:
        state = room_manager.get_public_state(game_id, player_id)
        await websocket.send_json({"type": "state_update", "state": state})
    else:
        await websocket.send_json({
            "type": "lobby_update",
            "players": room_manager.get_player_list(game_id),
            "game_id": game_id,
        })

    try:
        while True:
            raw = await websocket.receive_text()

            # Reject oversized messages before parsing (Step 13 — security).
            if len(raw) > 10_000:
                await websocket.send_json({"type": "error", "message": "Message too large"})
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            await _dispatch(game_id, player_id, data, websocket)

    except WebSocketDisconnect:
        room_manager.remove_connection(game_id, player_id, websocket)


# =============================================================================
# Message dispatch — _HANDLERS dict is built after handlers are defined below
# =============================================================================

async def _dispatch(
    game_id: str, player_id: str, data: dict, websocket: WebSocket
) -> None:
    engine = room_manager.get_engine(game_id)
    if engine is None:
        await websocket.send_json({"type": "error", "message": "Game has not started"})
        return

    msg_type = data.get("type")
    handler = _HANDLERS.get(msg_type)
    if handler is None:
        await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type!r}"})
        return

    try:
        await handler(game_id, player_id, data, engine)
    except (KeyError, ValueError, TypeError) as e:
        await websocket.send_json({"type": "error", "message": str(e)})


# =============================================================================
# Message handlers
# =============================================================================

async def _handle_deal_card(
    game_id: str, player_id: str, data: dict, engine
) -> None:
    """Deal a card to the requesting player."""
    card_dict = data["card"]
    _validate_card_dict(card_dict)
    card = deserialize_card(card_dict)

    engine.deal_card_to_player(player_id, card)

    if isinstance(card, ActionCard):
        # Pause broadcasting and wait for the player to choose a target.
        current_round = engine.game_state.current_round
        eligible = []
        if current_round is not None:
            eligible = [
                {"player_id": pid, "player_name": ps.name}
                for pid, ps in current_round.player_states.items()
                if not ps.has_stayed and not ps.is_busted
            ]

        room_manager.pending_action[game_id] = {
            "card": card,
            "owner_player_id": player_id,
        }

        await room_manager.broadcast(game_id, {
            "type": "action_pending",
            "action_type": card.action_type.value,
            "owner_player_id": player_id,
            "eligible_targets": eligible,
        })
    else:
        await room_manager.broadcast_state(game_id, _infer_message_type(engine))


async def _handle_apply_action(
    game_id: str, player_id: str, data: dict, engine
) -> None:
    """Apply a pending action card's effect to a chosen target."""
    pending = room_manager.pending_action.get(game_id)
    if not pending:
        raise ValueError("No pending action card to apply")
    if pending["owner_player_id"] != player_id:
        raise ValueError("You do not own the pending action card")

    target_player_id = data["target_player_id"]
    engine.apply_action_card_effect(pending["card"], target_player_id, player_id)
    room_manager.pending_action[game_id] = None

    await room_manager.broadcast_state(game_id, _infer_message_type(engine))


async def _handle_stay(
    game_id: str, player_id: str, data: dict, engine
) -> None:
    """Mark the requesting player as staying this round."""
    engine.player_stay(player_id)
    await room_manager.broadcast_state(game_id, _infer_message_type(engine))


async def _handle_use_second_chance(
    game_id: str, player_id: str, data: dict, engine
) -> None:
    """Use a Second Chance card to discard a duplicate number card."""
    card_dict = data["card_to_discard"]
    _validate_card_dict(card_dict)
    card = deserialize_card(card_dict)

    if not isinstance(card, NumberCard):
        raise ValueError("card_to_discard must be a number card")

    engine.use_second_chance(player_id, card)
    await room_manager.broadcast_state(game_id, _infer_message_type(engine))


async def _handle_start_round(
    game_id: str, player_id: str, data: dict, engine
) -> None:
    """Start the next round. Only the host may do this."""
    if not room_manager.is_host(game_id, player_id):
        raise ValueError("Only the host can start the next round")
    if engine.game_state.current_round is not None:
        raise ValueError("A round is already in progress")
    if engine.game_state.is_complete:
        raise ValueError("The game is already complete")

    engine.start_new_round()
    await room_manager.broadcast_state(game_id, message_type="round_started")


# Built here so all handler functions are already defined above.
_HANDLERS = {
    "deal_card":         _handle_deal_card,
    "apply_action":      _handle_apply_action,
    "stay":              _handle_stay,
    "use_second_chance": _handle_use_second_chance,
    "start_round":       _handle_start_round,
}


# =============================================================================
# Helpers
# =============================================================================

def _infer_message_type(engine) -> str:
    """
    Choose the correct broadcast message type based on current game state.

    Clients use this to decide which screen to show:
    - game_over      → show winner screen
    - round_ended    → show round summary + start-next-round button
    - state_update   → normal in-round update
    """
    if engine.game_state.is_complete:
        return "game_over"
    if engine.game_state.current_round is None:
        return "round_ended"
    return "state_update"


_VALID_NUMBER_VALUES = set(range(0, 13))
_VALID_MODIFIER_TYPES = {"plus_2", "plus_4", "plus_6", "plus_8", "plus_10", "multiply_2"}
_VALID_ACTION_TYPES = {"flip_three", "freeze", "second_chance"}


def _validate_card_dict(data: dict) -> None:
    """
    Validate and sanitize a client-supplied card dict (Step 12 — security).

    - Checks all required fields are present and have valid values.
    - Replaces the client-provided card_id with a fresh server-generated UUID
      so clients cannot dictate which physical card ID they receive.

    Raises:
        ValueError: If any field is missing or invalid.
    """
    card_type = data.get("card_type")

    if card_type == "number":
        value = data.get("value")
        if not isinstance(value, int) or value not in _VALID_NUMBER_VALUES:
            raise ValueError(f"Invalid number card value: {value!r}. Must be 0–12.")

    elif card_type == "modifier":
        modifier_type = data.get("modifier_type")
        if modifier_type not in _VALID_MODIFIER_TYPES:
            raise ValueError(f"Invalid modifier_type: {modifier_type!r}")

    elif card_type == "action":
        action_type = data.get("action_type")
        if action_type not in _VALID_ACTION_TYPES:
            raise ValueError(f"Invalid action_type: {action_type!r}")

    else:
        raise ValueError(f"Unknown card_type: {card_type!r}")

    # Always replace the client-supplied card_id with a server-generated one.
    data["card_id"] = str(uuid4())


# =============================================================================
# Static files — mounted last so /api/* routes take precedence
# =============================================================================

_static_dir = Path(__file__).parent.parent / "gui_multiplayer" / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")