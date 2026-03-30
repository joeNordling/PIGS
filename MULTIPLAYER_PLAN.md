# Multiplayer Implementation Plan: Flip 7

Plain HTML/JS frontend with a FastAPI WebSocket server hosted on one player's machine.
All other players connect via browser — no Python install needed on their side.

## Architecture Summary

```
Browser (player 1) ←→ WebSocket ←→ FastAPI server (owns GameEngine) ←→ WebSocket ←→ Browser (player N)
```

- The host runs the server. Their machine owns the `GameEngine` instance.
- After every action, the server broadcasts a filtered `GameState` snapshot to all players.
- Each player sees only their own hand; other players show card count + score only.
- The existing Streamlit single-player GUI is untouched.

**New directories:**
- `flip_7/network/` — server, room manager, message handlers
- `flip_7/gui_multiplayer/static/` — HTML/JS/CSS files served to browsers

---

## Dependency Chain

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 10
                                  ↓
                    Step 6 → Step 7 → Step 8
                                  ↓
                             Step 9
                                  ↓
                        Steps 11–16 (tests + security)
```

Steps 6–8 (frontend) can be developed in parallel with Steps 4–5 (server), as they are
only coupled at the WebSocket message protocol defined in Step 5.

---

## Steps

### Step 1 — Add dependencies to `pyproject.toml`

**File modified:** `pyproject.toml`

Add a new `multiplayer` group under `[project.optional-dependencies]`:
- `fastapi>=0.110.0`
- `uvicorn[standard]>=0.29.0`
- `websockets>=12.0`

Install with: `pip install -e ".[multiplayer]"`

---

### Step 2 — Create `flip_7/network/__init__.py`

**File created:** `flip_7/network/__init__.py`

Empty file to mark the directory as a Python package. Required before any imports
from `flip_7.network` will work.

---

### Step 3 — Create `flip_7/network/room_manager.py`

**File created:** `flip_7/network/room_manager.py`

In-memory store for all active games and connections. A single `RoomManager` instance
is shared across all FastAPI requests (module-level singleton).

**Data structures:**
- `rooms: Dict[str, GameEngine]` — game_id → engine (None until game is started)
- `room_players: Dict[str, Dict[str, str]]` — game_id → {player_id: player_name}, populated in lobby
- `connections: Dict[str, Set[WebSocket]]` — game_id → all connected sockets
- `player_connections: Dict[str, WebSocket]` — player_id → their socket
- `host_player: Dict[str, str]` — game_id → player_id of the first joiner
- `pending_action: Dict[str, dict]` — game_id → {card, owner_player_id} for action cards
  awaiting target selection; cleared after `apply_action_card_effect` is called

**Methods:**
- `create_room() -> str` — generates game_id via uuid4, initializes all dicts, returns game_id
- `join_room(game_id, player_name) -> str` — validates game hasn't started, assigns player_id,
  stores in `room_players`, returns player_id
- `start_game(game_id) -> GameEngine` — creates `GameEngine`, calls `start_new_game()` then
  `start_new_round()`, stores in `rooms`
- `register_connection(game_id, player_id, websocket)` — adds to both connection dicts
- `remove_connection(game_id, player_id, websocket)` — removes from both connection dicts
- `async broadcast(game_id, message: dict)` — sends JSON to all sockets in room; handles
  `WebSocketDisconnect` by calling `remove_connection`
- `get_public_state(game_id, requesting_player_id) -> dict` — calls `engine.get_game_state().to_dict()`,
  then redacts `cards_in_hand` for every player except the requester (replaces with `card_count`),
  strips `deck` and `discard_pile` entirely, adds `your_player_id` field. This is the sole
  privacy boundary between players.

---

### Step 4 — Create `flip_7/network/server.py` (HTTP + WebSocket skeleton)

**File created:** `flip_7/network/server.py`

FastAPI app wiring HTTP and WebSocket endpoints to `RoomManager`.

**Setup:**
- Create `FastAPI()` app instance
- Create module-level `RoomManager()` singleton
- Mount `flip_7/gui_multiplayer/static/` as `StaticFiles` at `/`

**HTTP endpoints:**

| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| `POST` | `/api/rooms` | — | `{game_id}` | Creates room; caller becomes host |
| `POST` | `/api/rooms/{game_id}/join` | `{player_name}` | `{player_id, game_id}` | 404 if no room, 409 if started |
| `POST` | `/api/rooms/{game_id}/start` | `{player_id}` | `{ok}` | 403 if not host, 422 if <2 players |

After `start_game` succeeds, broadcast `{"type": "game_started", ...filtered state per player}`.

**WebSocket endpoint:** `WS /ws/{game_id}/{player_id}`

On connect:
1. Call `room_manager.register_connection(game_id, player_id, websocket)`
2. Send current filtered state to the connecting player

Message loop (`while True: data = await websocket.receive_json()`):
- Dispatch on `data["type"]` to message handlers (Step 5)
- After any successful engine mutation, call `_broadcast_state_to_all(game_id)`

On disconnect (catch `WebSocketDisconnect`):
- Call `room_manager.remove_connection(game_id, player_id, websocket)`

**Helper `_broadcast_state_to_all(game_id)`:**
Iterates all players in the room; for each, calls `get_public_state(game_id, player_id)`
and sends to that player's socket if connected. Each player receives a different payload
(their hand is visible; others are redacted).

---

### Step 5 — Implement WebSocket message handlers in `server.py`

**File modified:** `flip_7/network/server.py`

One handler function per action type, dispatched from the WebSocket message loop.
Each catches `ValueError` from the engine and returns `{"type": "error", "message": "..."}`.

**Dispatch table:**

| `data["type"]` | Handler | What it does |
|----------------|---------|--------------|
| `"deal_card"` | `handle_deal_card` | Deserializes card, calls `deal_card_to_player`. If `ActionCard`, stores in `pending_action` and broadcasts `action_pending` with eligible targets. Otherwise broadcasts full state. |
| `"apply_action"` | `handle_apply_action` | Validates caller owns pending action, calls `apply_action_card_effect(card, target_player_id, owner_id)`, clears `pending_action`, broadcasts full state. |
| `"stay"` | `handle_stay` | Calls `player_stay(player_id)`, broadcasts full state. |
| `"use_second_chance"` | `handle_use_second_chance` | Deserializes `card_to_discard`, calls `use_second_chance`, broadcasts full state. |
| `"start_round"` | `handle_start_round` | Validates caller is host and `current_round is None`, calls `start_new_round()`, broadcasts full state with type `"round_started"`. |

**Note on deserialization:** Use the existing `deserialize_card()` from `flip_7.data.persistence`
to reconstruct `Card` objects from client JSON. Input validation added in Step 13.

---

### Step 6 — Create `flip_7/gui_multiplayer/static/index.html`

**File created:** `flip_7/gui_multiplayer/static/index.html`

Single HTML file. All "screens" are `<div>` containers toggled with CSS `display: none/flex`.
No page navigation, no build step, no framework.

**Screens (div IDs):**

| ID | Shown when |
|----|-----------|
| `#screen-lobby-join` | Page load — name + room code inputs, Join and Create buttons |
| `#screen-lobby-waiting` | After joining — player list; host sees "Start Game" button |
| `#screen-game` | After `game_started` message received |
| `#screen-action-target` | Modal overlay on `action_pending` — eligible target buttons |
| `#screen-second-chance` | Modal overlay when player clicks "Use Second Chance" |
| `#screen-round-end` | After round ends — scores, "Start Next Round" (host only) |
| `#screen-game-over` | When `game_state.is_complete` is true |

---

### Step 7 — Create `flip_7/gui_multiplayer/static/game.js`

**File created:** `flip_7/gui_multiplayer/static/game.js`

All client-side logic. No framework — plain ES6.

**Module-level state:**
- `myPlayerId`, `myGameId`, `ws`, `lastGameState`, `pendingActionCard`

**Connection functions:**
- `createRoom(playerName)` — `POST /api/rooms` → calls `joinGame()`
- `joinGame(playerName, gameId)` — `POST /api/rooms/{gameId}/join` → stores player_id → calls `connectWebSocket()`
- `connectWebSocket()` — opens `WebSocket("ws://{location.host}/ws/{gameId}/{playerId}")`,
  wires `ws.onmessage` to `handleMessage()`

**`handleMessage(msg)` dispatch:**

| `msg.type` | Action |
|------------|--------|
| `"state_update"` | `renderGameState(msg.state)` |
| `"game_started"` | `renderGameState(msg.state)`, show `#screen-game` |
| `"action_pending"` | Store `pendingActionCard`, show `#screen-action-target` with target buttons |
| `"round_ended"` | Show `#screen-round-end` with scores |
| `"game_over"` | Show `#screen-game-over` |
| `"lobby_update"` | Update player list in `#screen-lobby-waiting` |
| `"error"` | Show error banner |

**`renderGameState(state)`:**
- **Opponents panel:** For each `player_id ≠ myPlayerId` — name, status badge
  (STAYED / BUSTED / FLIP THREE N left / ACTIVE), card count, round score, total score
- **My panel:** Full hand as labeled card elements, round score breakdown, total score,
  flip three counter if active
- **My action buttons:**
  - "Deal Card" — opens card selector; label changes to "Draw Required Card (N left)"
    if `flip_three_active`
  - "Stay" — disabled if `flip_three_active && flip_three_count > 0`
  - "Second Chance" — visible only if `has_second_chance`; opens `#screen-second-chance`
- If `state.is_complete` → show `#screen-game-over`
- If `state.current_round === null && !state.is_complete` → show `#screen-round-end`

**Card selector** (inline sub-panel, shown on "Deal Card" click):
- Three tabs: Number (0–12 grid), Modifier (+2/+4/+6/+8/+10/×2), Action (Freeze/Flip Three/Second Chance)
- Clicking a card sends `sendDealCard(cardDict)` and hides the selector

**Send functions:**

| Function | WebSocket message sent |
|----------|----------------------|
| `sendDealCard(cardDict)` | `{type: "deal_card", card: cardDict}` |
| `sendApplyAction(targetId)` | `{type: "apply_action", target_player_id: targetId}` |
| `sendStay()` | `{type: "stay"}` |
| `sendUseSecondChance(value)` | `{type: "use_second_chance", card_to_discard: {card_type: "number", value: value}}` |
| `sendStartRound()` | `{type: "start_round"}` |

---

### Step 8 — Create `flip_7/gui_multiplayer/static/style.css`

**File created:** `flip_7/gui_multiplayer/static/style.css`

- Dark background (visually distinct from the Streamlit single-player app)
- Card buttons styled as card shapes with hover state; action cards color-coded:
  Freeze = blue, Flip Three = orange, Second Chance = green
- Status badges: STAYED = green, BUSTED = red, FLIP THREE = orange, ACTIVE = neutral
- Modal overlays: full-screen dimmed background for action target and second chance screens
- Responsive breakpoint at 768px — players may connect from phones

---

### Step 9 — Create launch entry point

**Files created:**
- `flip_7/network/launch_server.py` — calls `uvicorn.run("flip_7.network.server:app", port=8765)`
- `flip_7/launch_multiplayer.sh` — activates conda env, runs the server

Add to `pyproject.toml` scripts: `flip7-server = "flip_7.network.launch_server:main"`

Host shares their LAN IP + port with other players: `http://192.168.x.x:8765`

---

### Step 10 — Lobby update broadcasts

**File modified:** `flip_7/network/server.py`

After each successful `join_room`, broadcast a `lobby_update` to already-connected sockets:

```json
{
  "type": "lobby_update",
  "players": [{"player_id": "...", "player_name": "...", "is_host": true}],
  "game_id": "..."
}
```

After `start_game` succeeds, send a `game_started` message (not `state_update`) so clients
know to switch from the lobby screen to the game screen.

---

### Step 11 — Integration tests

**Files modified:** `pyproject.toml`, `flip_7/tests/test_multiplayer_server.py`

Add `pytest-asyncio` and `httpx` to `dev` extras.

**Tests:**

1. Create room returns a game_id
2. Join room returns a player_id
3. Joining a started game returns 409
4. Starting with one player is rejected
5. Non-host trying to start returns 403
6. Dealing a card via WebSocket — both players receive `state_update`
7. Privacy filter — player B's `state_update` shows player A's hand as `card_count` only
8. Action pending flow — deal action card → `action_pending` received → send `apply_action`
   → full state broadcast follows
9. Both players staying ends the round and triggers `round_ended`

---

## Security Steps

### Step 12 — Validate and sanitize card input

**File modified:** `flip_7/network/server.py`

In message handlers, validate all client-supplied card data **before** calling `deserialize_card`.

**Why this matters:** `deserialize_card` passes `card_id` directly from the client payload,
and the engine falls back to using a client-provided card if it isn't found in the remaining deck
(`engine.py:199–202`). This means an unvalidated client could inject cards with arbitrary values
(e.g., `value=999`) that don't exist in the actual deck.

**What to add:**

A `validate_card_dict(data: dict)` function that:
- Checks required keys exist (raises `ValueError` on missing keys rather than letting `KeyError` crash)
- For `NumberCard`: validates `value` is an `int` in `range(0, 13)`
- For `ModifierCard`: validates `modifier_type` is a known `ModifierType` value, and `value` matches
  the expected numeric value for that modifier
- For `ActionCard`: validates `action_type` is a known `ActionType` value

Strip the client-provided `card_id` and replace it with a fresh `str(uuid4())` server-side.
The client has no legitimate reason to dictate which physical card ID they receive.

Call `validate_card_dict(data)` in both `handle_deal_card` and `handle_use_second_chance`
before deserializing.

---

### Step 13 — WebSocket rate limiting and message size cap

**File modified:** `flip_7/network/server.py`

Protects against a flooded or malicious client consuming CPU and memory.

**Rate limit:** Track a per-connection message timestamp deque (max length 10). Before processing
each message, record the current time. If all 10 slots are filled within 1 second, close the
connection with code 1008 (policy violation) and return.

**Message size cap:** Before calling `websocket.receive_json()`, receive raw text first with
`websocket.receive_text()`. If `len(raw) > 10_000`, close the connection and return. No
legitimate game message should exceed a few hundred bytes.

---

### Step 14 — Connection cap per room and error handling

**File modified:** `flip_7/network/room_manager.py` and `flip_7/network/server.py`

**Connection cap:** In `RoomManager.register_connection`, check
`len(connections[game_id]) >= MAX_CONNECTIONS` (set to 10). Raise `ValueError` if exceeded.
In the WebSocket endpoint, catch this and immediately close the connection.

**Error handling:** Wrap all handler dispatch in the WebSocket message loop with
`try/except (KeyError, ValueError, TypeError)`. On any exception, send
`{"type": "error", "message": str(e)}` and continue the loop — do not let a single bad
message crash the connection.

---

### Step 15 — Bind to LAN IP, not `0.0.0.0`

**File modified:** `flip_7/network/launch_server.py`

Binding to `0.0.0.0` on a public WiFi network exposes the server to every device on that network,
not just your intended players.

Add a `--host` CLI argument (default: auto-detect the machine's primary LAN IP using
`socket.gethostbyname(socket.gethostname())`). The auto-detected IP is printed on startup
so the host knows what URL to share with players.

Also document: enable the macOS application firewall under
**System Preferences → Privacy & Security → Firewall** to block unexpected incoming connections.

---

### Step 16 — Separate dev and production launch configurations

**Files modified:** `flip_7/network/launch_server.py`, `flip_7/launch_multiplayer.sh`

The `--reload` flag (file watcher, auto-restart on code changes) is appropriate during
development but wrong for an active game session — any accidental file modification would
restart the server mid-game, losing all in-memory game state.

Create two launch modes:
- **Dev:** `uvicorn ... --reload --host 127.0.0.1` (localhost only, auto-restart enabled)
- **Play:** `uvicorn ... --host {lan_ip}` (LAN-accessible, no auto-restart)

`launch_multiplayer.sh` should use the play configuration. Add a separate
`launch_multiplayer_dev.sh` for development.
