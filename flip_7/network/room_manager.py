"""
Room manager for Flip 7 multiplayer.

Owns all in-memory server state: active games, player rosters, and WebSocket
connections. A single RoomManager instance is shared across all FastAPI requests.
"""

from typing import Dict, Optional, Set
from uuid import uuid4

from starlette.websockets import WebSocket, WebSocketDisconnect

from flip_7.core.engine import GameEngine


# Maximum number of WebSocket connections allowed per game room.
MAX_CONNECTIONS_PER_ROOM = 10


class RoomManager:
    """
    Central store for all active multiplayer game rooms and connections.

    Each room corresponds to one GameEngine instance. Players join a room
    before the game starts (lobby phase), then the host starts the game.

    Attributes:
        rooms: Maps game_id to its GameEngine (None until game is started).
        room_players: Maps game_id to {player_id: player_name}, populated in lobby.
        connections: Maps game_id to the set of currently connected WebSockets.
        player_connections: Maps player_id to their WebSocket.
        host_player: Maps game_id to the player_id of the room host (first joiner).
        pending_action: Maps game_id to a pending action card awaiting target selection.
    """

    def __init__(self):
        self.rooms: Dict[str, Optional[GameEngine]] = {}
        self.room_players: Dict[str, Dict[str, str]] = {}
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.player_connections: Dict[str, WebSocket] = {}
        self.host_player: Dict[str, str] = {}
        self.pending_action: Dict[str, Optional[dict]] = {}

    # -------------------------------------------------------------------------
    # Room lifecycle
    # -------------------------------------------------------------------------

    def create_room(self) -> str:
        """
        Create a new empty game room and return its game_id.

        The caller is not yet assigned as host — that happens on first join.
        """
        game_id = str(uuid4())
        self.rooms[game_id] = None
        self.room_players[game_id] = {}
        self.connections[game_id] = set()
        self.pending_action[game_id] = None
        return game_id

    def join_room(self, game_id: str, player_name: str) -> str:
        """
        Add a player to an existing room and return their assigned player_id.

        Args:
            game_id: The room to join.
            player_name: Display name chosen by the player.

        Returns:
            A newly generated player_id for this player.

        Raises:
            KeyError: If game_id does not exist.
            ValueError: If the game has already started or name is taken.
        """
        if game_id not in self.rooms:
            raise KeyError(f"Room {game_id} does not exist")

        if self.rooms[game_id] is not None:
            raise ValueError("Game has already started")

        existing_names = set(self.room_players[game_id].values())
        if player_name in existing_names:
            raise ValueError(f"Player name '{player_name}' is already taken in this room")

        player_id = str(uuid4())
        self.room_players[game_id][player_id] = player_name

        # First player to join becomes the host.
        if game_id not in self.host_player:
            self.host_player[game_id] = player_id

        return player_id

    def start_game(self, game_id: str) -> GameEngine:
        """
        Start the game for the given room.

        Creates the GameEngine, calls start_new_game with all joined players
        (in join order), then immediately starts the first round.

        Args:
            game_id: The room to start.

        Returns:
            The initialised GameEngine.

        Raises:
            KeyError: If game_id does not exist.
            ValueError: If the game is already started or has fewer than 2 players.
        """
        if game_id not in self.rooms:
            raise KeyError(f"Room {game_id} does not exist")

        if self.rooms[game_id] is not None:
            raise ValueError("Game has already started")

        players = self.room_players[game_id]
        if len(players) < 2:
            raise ValueError("Need at least 2 players to start a game")

        # Preserve join order (dicts are insertion-ordered in Python 3.7+).
        player_names = list(players.values())

        # Pass the lobby-assigned player_ids directly so the engine uses them.
        # This avoids any need to remap ids between the lobby and game state.
        engine = GameEngine()
        engine.start_new_game(player_names, player_ids=list(players.keys()))
        engine.start_new_round()

        self.rooms[game_id] = engine
        return engine

    def get_engine(self, game_id: str) -> Optional[GameEngine]:
        """Return the GameEngine for a room, or None if the game hasn't started."""
        return self.rooms.get(game_id)

    def is_host(self, game_id: str, player_id: str) -> bool:
        """Return True if player_id is the host of game_id."""
        return self.host_player.get(game_id) == player_id

    def room_exists(self, game_id: str) -> bool:
        """Return True if a room with this game_id exists."""
        return game_id in self.rooms

    def player_in_room(self, game_id: str, player_id: str) -> bool:
        """Return True if the player belongs to this room."""
        return player_id in self.room_players.get(game_id, {})

    def get_player_list(self, game_id: str) -> list[dict]:
        """
        Return the player roster for a room as a list of dicts.

        Each entry has keys: player_id, player_name, is_host.
        """
        host_id = self.host_player.get(game_id)
        return [
            {
                "player_id": pid,
                "player_name": name,
                "is_host": pid == host_id,
            }
            for pid, name in self.room_players.get(game_id, {}).items()
        ]

    # -------------------------------------------------------------------------
    # Connection management
    # -------------------------------------------------------------------------

    def register_connection(
        self, game_id: str, player_id: str, websocket: WebSocket
    ) -> None:
        """
        Register a WebSocket connection for a player.

        Args:
            game_id: The room this connection belongs to.
            player_id: The player connecting.
            websocket: Their WebSocket connection.

        Raises:
            ValueError: If the room is at capacity.
        """
        if game_id not in self.connections:
            self.connections[game_id] = set()

        if len(self.connections[game_id]) >= MAX_CONNECTIONS_PER_ROOM:
            raise ValueError(
                f"Room {game_id} is at capacity ({MAX_CONNECTIONS_PER_ROOM} connections)"
            )

        self.connections[game_id].add(websocket)
        self.player_connections[player_id] = websocket

    def remove_connection(
        self, game_id: str, player_id: str, websocket: WebSocket
    ) -> None:
        """Remove a WebSocket connection, ignoring it if already absent."""
        self.connections.get(game_id, set()).discard(websocket)
        if self.player_connections.get(player_id) is websocket:
            del self.player_connections[player_id]

    async def broadcast(self, game_id: str, message: dict) -> None:
        """
        Send a JSON message to every connected player in a room.

        Silently removes connections that have already disconnected.

        Args:
            game_id: The room to broadcast to.
            message: The message payload (will be serialised to JSON).
        """
        dead: list[WebSocket] = []

        for ws in list(self.connections.get(game_id, set())):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)

        for ws in dead:
            self.connections.get(game_id, set()).discard(ws)

    async def send_to_player(self, player_id: str, message: dict) -> None:
        """
        Send a JSON message to a single player.

        Does nothing if the player is not currently connected.

        Args:
            player_id: The recipient.
            message: The message payload.
        """
        ws = self.player_connections.get(player_id)
        if ws is None:
            return
        try:
            await ws.send_json(message)
        except (WebSocketDisconnect, RuntimeError):
            pass

    # -------------------------------------------------------------------------
    # State broadcasting
    # -------------------------------------------------------------------------

    def get_public_state(self, game_id: str, requesting_player_id: str) -> dict:
        """
        Return a filtered GameState dict for the requesting player.

        Cards in other players' hands are redacted to just a count. The deck
        and discard pile are stripped entirely. A your_player_id field is added
        so the client knows which player they are.

        Args:
            game_id: The room.
            requesting_player_id: The player whose perspective to use.

        Returns:
            A dict safe to send over the wire to requesting_player_id.

        Raises:
            ValueError: If the game has not been started yet.
        """
        engine = self.rooms.get(game_id)
        if engine is None:
            raise ValueError(f"Game {game_id} has not started")

        state = engine.get_game_state().to_dict()

        # Strip deck and discard pile — clients have no need for these.
        state.pop("deck", None)
        state.pop("discard_pile", None)

        # Redact other players' hands. Because the engine now uses the same
        # player_ids assigned during join, no ID translation is needed.
        def _redact_round(round_dict: dict) -> None:
            for pid, player_state in round_dict["player_states"].items():
                if pid != requesting_player_id:
                    player_state["card_count"] = len(player_state["cards_in_hand"])
                    player_state["cards_in_hand"] = []

        if state.get("current_round"):
            _redact_round(state["current_round"])

        for past_round in state.get("round_history", []):
            _redact_round(past_round)

        state["your_player_id"] = requesting_player_id
        state["is_host"] = self.is_host(game_id, requesting_player_id)

        return state

    async def broadcast_state(self, game_id: str, message_type: str = "state_update") -> None:
        """
        Send each player their own filtered GameState view.

        Because each player's view differs (their own hand is visible; others
        are redacted), we send N separate messages — one per player.

        Args:
            game_id: The room to broadcast to.
            message_type: The 'type' field in the message (e.g. "state_update",
                          "game_started", "round_started").
        """
        for player_id in self.room_players.get(game_id, {}):
            try:
                state = self.get_public_state(game_id, player_id)
            except ValueError:
                continue

            await self.send_to_player(
                player_id,
                {"type": message_type, "state": state},
            )