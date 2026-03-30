/**
 * Flip 7 Multiplayer — client-side logic.
 *
 * Connects to the FastAPI WebSocket server, handles all message types,
 * and renders the game state for the current player.
 */

// =============================================================================
// Module state
// =============================================================================

let myPlayerId   = null;
let myGameId     = null;
let ws           = null;
let lastState    = null;
let isPickerOpen = false;

// =============================================================================
// Screen management
// =============================================================================

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) target.classList.add('active');
}

/** Show a modal overlay without hiding the game board behind it. */
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

function showError(elementId, message) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = message;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 5000);
}

// =============================================================================
// Lobby: join or create
// =============================================================================

function handleJoinOrCreate() {
  const name = document.getElementById('player-name-input').value.trim();
  const code = document.getElementById('room-code-input').value.trim();

  if (!name) {
    showError('lobby-error', 'Please enter your name.');
    return;
  }

  if (code) {
    joinGame(name, code);
  } else {
    createRoom(name);
  }
}

async function createRoom(playerName) {
  try {
    const res = await fetch('/api/rooms', { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    const { game_id } = await res.json();
    await joinGame(playerName, game_id);
  } catch (err) {
    showError('lobby-error', `Failed to create room: ${err.message}`);
  }
}

async function joinGame(playerName, gameId) {
  try {
    const res = await fetch(`/api/rooms/${gameId}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: playerName }),
    });

    if (!res.ok) {
      const detail = (await res.json()).detail || res.statusText;
      showError('lobby-error', `Could not join: ${detail}`);
      return;
    }

    const data = await res.json();
    myPlayerId = data.player_id;
    myGameId   = data.game_id;

    document.getElementById('room-code-display').textContent = myGameId;
    connectWebSocket();

  } catch (err) {
    showError('lobby-error', `Connection error: ${err.message}`);
  }
}

function copyRoomCode() {
  navigator.clipboard.writeText(myGameId).then(() => {
    const btn = document.querySelector('.room-code-box .btn-small');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  });
}

async function startGame() {
  try {
    const res = await fetch(`/api/rooms/${myGameId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_id: myPlayerId }),
    });
    if (!res.ok) {
      const detail = (await res.json()).detail || res.statusText;
      showError('waiting-error', `Could not start: ${detail}`);
    }
  } catch (err) {
    showError('waiting-error', `Error: ${err.message}`);
  }
}

// =============================================================================
// WebSocket connection
// =============================================================================

function connectWebSocket() {
  showScreen('screen-lobby-waiting');

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${protocol}://${location.host}/ws/${myGameId}/${myPlayerId}`);

  ws.onmessage = (event) => {
    try {
      handleMessage(JSON.parse(event.data));
    } catch (e) {
      console.error('Failed to parse message:', e);
    }
  };

  ws.onclose = (event) => {
    if (event.code !== 1000) {
      showError('game-error', `Disconnected (${event.reason || 'connection lost'}). Refresh to reconnect.`);
    }
  };

  ws.onerror = () => {
    showError('lobby-error', 'WebSocket error. Check the server is running.');
  };
}

function sendMessage(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

// =============================================================================
// Message handling
// =============================================================================

function handleMessage(msg) {
  switch (msg.type) {

    case 'lobby_update':
      renderLobby(msg.players);
      break;

    case 'game_started':
      showScreen('screen-game');
      closeModal('screen-action-target');
      closeModal('screen-second-chance');
      renderGameState(msg.state);
      break;

    case 'state_update':
      renderGameState(msg.state);
      break;

    case 'round_started':
      showScreen('screen-game');
      renderGameState(msg.state);
      break;

    case 'round_ended':
      renderRoundEnd(msg.state);
      break;

    case 'game_over':
      renderGameOver(msg.state);
      break;

    case 'action_pending':
      handleActionPending(msg);
      break;

    case 'error':
      showError('game-error', msg.message);
      break;

    default:
      console.warn('Unknown message type:', msg.type);
  }
}

// =============================================================================
// Lobby rendering
// =============================================================================

function renderLobby(players) {
  const list = document.getElementById('player-list');
  list.innerHTML = '';
  players.forEach(p => {
    const el = document.createElement('div');
    el.className = 'player-list-item';
    el.textContent = p.player_name + (p.is_host ? ' 👑' : '');
    list.appendChild(el);
  });

  const isHost = players.some(p => p.player_id === myPlayerId && p.is_host);
  const startBtn = document.getElementById('start-game-btn');
  startBtn.classList.toggle('hidden', !isHost);

  const waitingStatus = document.getElementById('waiting-status');
  waitingStatus.classList.toggle('hidden', isHost);
}

// =============================================================================
// Game board rendering
// =============================================================================

function renderGameState(state) {
  lastState = state;

  const round = state.current_round;
  if (!round) return;

  document.getElementById('game-round-display').textContent = `Round ${round.round_number}`;
  document.getElementById('game-deck-display').textContent  = `Cards: ${round.cards_remaining_in_deck}`;

  // Opponents
  const opponentsPanel = document.getElementById('opponents-panel');
  opponentsPanel.innerHTML = '';
  state.players.forEach(player => {
    if (player.player_id === state.your_player_id) return;
    const ps = round.player_states[player.player_id];
    if (!ps) return;
    opponentsPanel.appendChild(renderOpponent(player, ps));
  });

  // My panel
  const myInfo = state.players.find(p => p.player_id === state.your_player_id);
  const myPs   = round.player_states[state.your_player_id];
  const myPanel = document.getElementById('my-panel');
  myPanel.innerHTML = '';
  if (myInfo && myPs) {
    myPanel.appendChild(renderMyPanel(myInfo, myPs, state));
  }
}

function statusBadge(ps) {
  if (ps.is_busted)        return '<span class="badge badge-bust">BUSTED</span>';
  if (ps.has_stayed)       return '<span class="badge badge-stay">STAYED</span>';
  if (ps.flip_three_active) return `<span class="badge badge-flip">FLIP THREE (${ps.flip_three_count} left)</span>`;
  return '<span class="badge badge-active">ACTIVE</span>';
}

function renderOpponent(playerInfo, ps) {
  const div = document.createElement('div');
  div.className = 'opponent-row';
  div.innerHTML = `
    <div class="opponent-name">${escHtml(playerInfo.name)} ${statusBadge(ps)}</div>
    <div class="opponent-stats">
      <span>${ps.card_count ?? ps.cards_in_hand.length} cards</span>
      <span>Round: <strong>${ps.round_score}</strong></span>
      <span>Total: <strong>${ps.total_score}</strong></span>
      ${ps.has_second_chance ? '<span class="badge badge-sc">SC</span>' : ''}
    </div>
  `;
  return div;
}

function renderMyPanel(playerInfo, ps, state) {
  const div = document.createElement('div');
  div.className = 'my-panel-inner';

  // Hand display
  const handHtml = ps.cards_in_hand.length
    ? ps.cards_in_hand.map(c => `<span class="card-chip card-${c.card_type}">${cardLabel(c)}</span>`).join('')
    : '<span class="hint">No cards yet</span>';

  // Score breakdown text
  let scoreText = `Round score: <strong>${ps.round_score}</strong> &nbsp;|&nbsp; Total: <strong>${ps.total_score}</strong>`;
  if (ps.flip_three_active) {
    scoreText += ` &nbsp;|&nbsp; <span class="badge badge-flip">Must draw ${ps.flip_three_count} more</span>`;
  }

  // Action buttons
  const canAct    = !ps.has_stayed && !ps.is_busted;
  const canStay   = canAct && !(ps.flip_three_active && ps.flip_three_count > 0);
  const dealLabel = ps.flip_three_active ? `Draw Required Card (${ps.flip_three_count} left)` : 'Deal Card';

  div.innerHTML = `
    <div class="my-name">${escHtml(playerInfo.name)} ${statusBadge(ps)}</div>
    <div class="my-hand">${handHtml}</div>
    <div class="my-score">${scoreText}</div>
    ${canAct ? `
      <div class="action-buttons">
        <button class="btn btn-deal" onclick="toggleCardPicker()">${dealLabel}</button>
        <button class="btn btn-stay" onclick="sendStay()" ${canStay ? '' : 'disabled'}>Stay</button>
        ${ps.has_second_chance ? '<button class="btn btn-sc" onclick="openSecondChance()">Use Second Chance</button>' : ''}
      </div>
    ` : ''}
  `;
  return div;
}

// =============================================================================
// Round end + game over
// =============================================================================

function renderRoundEnd(state) {
  lastState = state;
  const history = state.round_history;
  if (!history || history.length === 0) return;

  const lastRound = history[history.length - 1];
  const roundNum  = lastRound.round_number;

  document.getElementById('round-end-title').textContent = `Round ${roundNum} Complete`;

  const scoresEl = document.getElementById('round-end-scores');
  scoresEl.innerHTML = '';

  const sorted = state.players
    .map(p => ({ ...p, ps: lastRound.player_states[p.player_id] }))
    .filter(p => p.ps)
    .sort((a, b) => b.ps.round_score - a.ps.round_score);

  sorted.forEach(p => {
    const isWinner = lastRound.winner_ids.includes(p.player_id);
    const row = document.createElement('div');
    row.className = 'score-row';
    row.innerHTML = `
      <span>${isWinner ? '👑 ' : ''}${escHtml(p.name)}</span>
      <span>+${p.ps.round_score} pts &nbsp; → &nbsp; <strong>${p.ps.total_score} total</strong></span>
    `;
    scoresEl.appendChild(row);
  });

  const nextBtn     = document.getElementById('next-round-btn');
  const waitingNote = document.getElementById('round-end-waiting');
  nextBtn.classList.toggle('hidden', !state.is_host);
  if (waitingNote) waitingNote.classList.toggle('hidden', state.is_host);

  showScreen('screen-round-end');
}

function renderGameOver(state) {
  lastState = state;

  const history  = state.round_history;
  const lastRound = history[history.length - 1];

  const winner = state.players.find(p => p.player_id === state.winner_id);
  document.getElementById('game-over-winner').innerHTML =
    winner ? `<p class="winner-name">👑 ${escHtml(winner.name)} wins!</p>` : '';

  const scoresEl = document.getElementById('game-over-scores');
  scoresEl.innerHTML = '';

  const sorted = state.players
    .map(p => ({ ...p, total: lastRound?.player_states[p.player_id]?.total_score ?? 0 }))
    .sort((a, b) => b.total - a.total);

  sorted.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'score-row';
    row.innerHTML = `<span>${i + 1}. ${escHtml(p.name)}</span><span><strong>${p.total} pts</strong></span>`;
    scoresEl.appendChild(row);
  });

  showScreen('screen-game-over');
}

// =============================================================================
// Action card targeting
// =============================================================================

function handleActionPending(msg) {
  document.getElementById('action-waiting-banner').classList.add('hidden');

  if (msg.owner_player_id === myPlayerId) {
    // It's my card — show the targeting modal.
    const titleMap = {
      freeze:        'Freeze — choose who to freeze',
      flip_three:    'Flip Three — choose who must draw 3 cards',
      second_chance: 'Second Chance — keep it or give to an opponent',
    };
    document.getElementById('action-target-title').textContent =
      titleMap[msg.action_type] || 'Choose a target';

    const desc = {
      freeze:        'The chosen player banks their current score and must stay.',
      flip_three:    'The chosen player must accept the next 3 cards.',
      second_chance: 'Gives the ability to discard one duplicate number card.',
    };
    document.getElementById('action-target-desc').textContent = desc[msg.action_type] || '';

    const list = document.getElementById('action-target-list');
    list.innerHTML = '';
    msg.eligible_targets.forEach(target => {
      const btn = document.createElement('button');
      btn.className = 'btn btn-target';
      btn.textContent = target.player_id === myPlayerId ? `${target.player_name} (you)` : target.player_name;
      btn.onclick = () => sendApplyAction(target.player_id);
      list.appendChild(btn);
    });

    openModal('screen-action-target');
  } else {
    // Someone else drew an action card — show a waiting banner.
    const ownerName = lastState?.players?.find(p => p.player_id === msg.owner_player_id)?.name ?? 'A player';
    const banner = document.getElementById('action-waiting-banner');
    banner.textContent = `Waiting for ${ownerName} to choose a target for ${msg.action_type.replace('_', ' ')}…`;
    banner.classList.remove('hidden');
  }
}

// =============================================================================
// Second Chance card usage
// =============================================================================

function openSecondChance() {
  if (!lastState) return;
  const round = lastState.current_round;
  if (!round) return;

  const myPs = round.player_states[myPlayerId];
  if (!myPs) return;

  // Find duplicate number cards in hand.
  const counts = {};
  myPs.cards_in_hand.forEach(c => {
    if (c.card_type === 'number') counts[c.value] = (counts[c.value] || 0) + 1;
  });
  const duplicates = Object.entries(counts).filter(([, n]) => n > 1);

  const list = document.getElementById('second-chance-list');
  list.innerHTML = '';

  if (duplicates.length === 0) {
    list.innerHTML = '<p class="hint">No duplicate cards to discard.</p>';
  } else {
    duplicates.forEach(([value]) => {
      const btn = document.createElement('button');
      btn.className = 'btn btn-target';
      btn.textContent = `Discard a ${value}`;
      btn.onclick = () => {
        closeModal('screen-second-chance');
        sendUseSecondChance(parseInt(value, 10));
      };
      list.appendChild(btn);
    });
  }

  openModal('screen-second-chance');
}

// =============================================================================
// Card picker
// =============================================================================

function toggleCardPicker() {
  const picker = document.getElementById('card-picker');
  isPickerOpen = !isPickerOpen;
  picker.classList.toggle('hidden', !isPickerOpen);
  if (isPickerOpen) showPickerTab('numbers');
}

function hideCardPicker() {
  isPickerOpen = false;
  document.getElementById('card-picker').classList.add('hidden');
}

function showPickerTab(tab) {
  ['numbers', 'modifiers', 'actions'].forEach(t => {
    document.getElementById(`picker-${t}`).classList.toggle('hidden', t !== tab);
  });
  document.querySelectorAll('.tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', ['numbers', 'modifiers', 'actions'][i] === tab);
  });
}

function pickCard(cardDict) {
  hideCardPicker();
  sendDealCard(cardDict);
}

/** Populate the card picker grids once on page load. */
function initCardPicker() {
  // Numbers 0–12
  const numGrid = document.getElementById('picker-numbers');
  for (let v = 0; v <= 12; v++) {
    const btn = document.createElement('button');
    btn.className = 'btn card-btn card-number';
    btn.textContent = v;
    btn.onclick = () => pickCard({ card_type: 'number', value: v });
    numGrid.appendChild(btn);
  }

  // Modifiers
  const modGrid = document.getElementById('picker-modifiers');
  const modifiers = [
    { label: '+2',  dict: { card_type: 'modifier', modifier_type: 'plus_2',     value: 2  } },
    { label: '+4',  dict: { card_type: 'modifier', modifier_type: 'plus_4',     value: 4  } },
    { label: '+6',  dict: { card_type: 'modifier', modifier_type: 'plus_6',     value: 6  } },
    { label: '+8',  dict: { card_type: 'modifier', modifier_type: 'plus_8',     value: 8  } },
    { label: '+10', dict: { card_type: 'modifier', modifier_type: 'plus_10',    value: 10 } },
    { label: '×2',  dict: { card_type: 'modifier', modifier_type: 'multiply_2', value: 2  } },
  ];
  modifiers.forEach(({ label, dict }) => {
    const btn = document.createElement('button');
    btn.className = 'btn card-btn card-modifier';
    btn.textContent = label;
    btn.onclick = () => pickCard(dict);
    modGrid.appendChild(btn);
  });

  // Actions
  const actGrid = document.getElementById('picker-actions');
  const actions = [
    { label: 'Freeze',        dict: { card_type: 'action', action_type: 'freeze'        } },
    { label: 'Flip Three',    dict: { card_type: 'action', action_type: 'flip_three'    } },
    { label: 'Second Chance', dict: { card_type: 'action', action_type: 'second_chance' } },
  ];
  actions.forEach(({ label, dict }) => {
    const btn = document.createElement('button');
    btn.className = 'btn card-btn card-action';
    btn.textContent = label;
    btn.onclick = () => pickCard(dict);
    actGrid.appendChild(btn);
  });
}

// =============================================================================
// Card label helper
// =============================================================================

function cardLabel(card) {
  if (card.card_type === 'number')   return card.value;
  if (card.card_type === 'modifier') {
    const labels = { plus_2: '+2', plus_4: '+4', plus_6: '+6', plus_8: '+8', plus_10: '+10', multiply_2: '×2' };
    return labels[card.modifier_type] ?? card.modifier_type;
  }
  if (card.card_type === 'action') {
    const labels = { freeze: '❄ Freeze', flip_three: '🔄 Flip 3', second_chance: '🎯 2nd' };
    return labels[card.action_type] ?? card.action_type;
  }
  return '?';
}

// =============================================================================
// Send functions
// =============================================================================

function sendDealCard(cardDict) {
  sendMessage({ type: 'deal_card', card: cardDict });
}

function sendApplyAction(targetPlayerId) {
  closeModal('screen-action-target');
  document.getElementById('action-waiting-banner').classList.add('hidden');
  sendMessage({ type: 'apply_action', target_player_id: targetPlayerId });
}

function sendStay() {
  sendMessage({ type: 'stay' });
}

function sendUseSecondChance(value) {
  sendMessage({ type: 'use_second_chance', card_to_discard: { card_type: 'number', value } });
}

function sendStartRound() {
  sendMessage({ type: 'start_round' });
}

// =============================================================================
// Utility
// =============================================================================

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function resetToLobby() {
  myPlayerId = null;
  myGameId   = null;
  lastState  = null;
  if (ws) { ws.close(); ws = null; }
  document.getElementById('player-name-input').value = '';
  document.getElementById('room-code-input').value   = '';
  showScreen('screen-lobby-join');
}

// =============================================================================
// Init
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initCardPicker();

  // Allow Enter key on lobby inputs.
  ['player-name-input', 'room-code-input'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') handleJoinOrCreate();
    });
  });
});