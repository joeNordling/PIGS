/**
 * Flip 7 Multiplayer — client-side logic.
 *
 * Connects to the FastAPI WebSocket server, handles all message types,
 * and renders the game state for the current player.
 */

// =============================================================================
// Module state
// =============================================================================

let myPlayerId = null;
let myGameId   = null;
let ws         = null;
let lastState  = null;

// Freeze animation tracking: `pendingFreezeIds` marks players who should play the
// freeze-in animation on the very next render; `animatedFrozenIds` remembers who
// already played it this round so later re-renders just show the settled frost tint.
let pendingFreezeIds  = new Set();
let animatedFrozenIds = new Set();

// Card sort modes: 'original' | 'value' | 'type'
const SORT_MODES  = ['original', 'value', 'type'];
const SORT_LABELS = { original: '↕ Original', value: '🔢 By Value', type: '🃏 By Type' };
let cardSortMode  = 'original';

// Whether to show opponents' cards
let showOpponentCards = true;

function toggleOpponentCards() {
  showOpponentCards = !showOpponentCards;
  const btn = document.getElementById('toggle-opponent-cards-btn');
  if (btn) btn.textContent = showOpponentCards ? '🙈 Hide Cards' : '👁 Show Cards';
  if (lastState) renderGameState(lastState);
}

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
  const btn = document.querySelector('.room-code-box .btn-small');
  const showCopied = () => {
    if (!btn) return;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  };

  // navigator.clipboard only exists in secure contexts (HTTPS or localhost) -
  // LAN play (e.g. launch_multiplayer.sh --host 0.0.0.0) is plain HTTP, so it's
  // undefined there. Fall back to the classic textarea + execCommand approach.
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(myGameId).then(showCopied).catch(() => legacyCopyRoomCode(showCopied));
  } else {
    legacyCopyRoomCode(showCopied);
  }
}

function legacyCopyRoomCode(onSuccess) {
  const textarea = document.createElement('textarea');
  textarea.value = myGameId;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    document.execCommand('copy');
    onSuccess();
  } catch (err) {
    showError('lobby-error', 'Could not copy room code — please copy it manually.');
  }
  document.body.removeChild(textarea);
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
      animatedFrozenIds.clear();
      pendingFreezeIds.clear();
      showScreen('screen-game');
      closeModal('screen-action-target');
      closeModal('screen-second-chance');
      renderGameState(msg.state);
      renderScoreboard(msg.state);
      break;

    case 'state_update':
      if (msg.action_applied && msg.action_applied.type === 'freeze') {
        pendingFreezeIds.add(msg.action_applied.target_player_id);
      }
      renderGameState(msg.state);
      renderScoreboard(msg.state);
      break;

    case 'round_started':
      animatedFrozenIds.clear();
      pendingFreezeIds.clear();
      showScreen('screen-game');
      renderGameState(msg.state);
      renderScoreboard(msg.state);
      break;

    case 'round_ended':
      if (msg.action_applied && msg.action_applied.type === 'freeze') {
        pendingFreezeIds.add(msg.action_applied.target_player_id);
      }
      renderRoundEndingBoard(msg.state);
      renderScoreboard(msg.state, { phase: 'round-end' });
      break;

    case 'game_over':
      if (msg.action_applied && msg.action_applied.type === 'freeze') {
        pendingFreezeIds.add(msg.action_applied.target_player_id);
      }
      renderRoundEndingBoard(msg.state);
      renderScoreboard(msg.state, { phase: 'game-over' });
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

  // Clear the "waiting for X to choose a target" banner — the action has resolved.
  document.getElementById('action-waiting-banner').classList.add('hidden');

  // Turn banner
  const turnBanner = document.getElementById('turn-banner');
  const currentPlayerId = round.current_player_id;
  if (currentPlayerId) {
    const currentPlayer = state.players.find(p => p.player_id === currentPlayerId);
    const currentPs = round.player_states[currentPlayerId];
    if (currentPlayer && currentPs) {
      const isMe = currentPlayerId === state.your_player_id;
      if (currentPs.flip_three_active) {
        turnBanner.textContent = isMe
          ? `⚠️ Your turn — FORCED DRAW (${currentPs.flip_three_count} card(s) remaining)`
          : `⚠️ ${escHtml(currentPlayer.name)}'s turn — FORCED DRAW (${currentPs.flip_three_count} card(s) remaining)`;
        turnBanner.className = 'turn-banner turn-forced';
      } else {
        turnBanner.textContent = isMe
          ? '🎯 Your turn — Draw a card or Stay'
          : `🎯 ${escHtml(currentPlayer.name)}'s turn`;
        turnBanner.className = isMe ? 'turn-banner turn-mine' : 'turn-banner turn-other';
      }
      turnBanner.classList.remove('hidden');
    }
  } else {
    turnBanner.classList.add('hidden');
  }

  // Opponents
  const opponentsPanel = document.getElementById('opponents-panel');
  opponentsPanel.innerHTML = '';
  state.players.forEach(player => {
    if (player.player_id === state.your_player_id) return;
    const ps = round.player_states[player.player_id];
    if (!ps) return;
    const isCurrentPlayer = player.player_id === currentPlayerId;
    opponentsPanel.appendChild(renderOpponent(player, ps, isCurrentPlayer));
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

/** A Flip 7 is 7 distinct number-card values in hand — derivable straight from the hand. */
function hasFlip7(ps) {
  const values = new Set(
    ps.cards_in_hand.filter(c => c.card_type === 'number').map(c => c.value)
  );
  return values.size >= 7;
}

function statusBadge(ps, isCurrentPlayer = false, isFrozen = false) {
  if (ps.is_busted)         return '<span class="badge badge-bust">BUSTED</span>';
  if (hasFlip7(ps))         return '<span class="badge badge-flip7">🎉 FLIP 7!</span>';
  if (isFrozen)             return '<span class="badge badge-frozen">FROZEN</span>';
  if (ps.has_stayed)        return '<span class="badge badge-stay">STAYED</span>';
  if (ps.flip_three_active) return `<span class="badge badge-flip">FLIP THREE (${ps.flip_three_count} left)</span>`;
  if (isCurrentPlayer)      return '<span class="badge badge-turn">YOUR TURN</span>';
  return '<span class="badge badge-active">ACTIVE</span>';
}

/** Confetti overlay markup — mirrors frostMarkup() but for the Flip 7 celebration. */
function flip7Markup() {
  const pieces = [
    { emoji: '🎉', top: '8%',  left: '12%', tx: '-30px', ty: '-35px', tr: '-25deg' },
    { emoji: '✨', top: '12%', left: '82%', tx: '32px',  ty: '-30px', tr: '20deg'  },
    { emoji: '🎊', top: '72%', left: '18%', tx: '-25px', ty: '30px',  tr: '15deg'  },
    { emoji: '⭐', top: '68%', left: '86%', tx: '28px',  ty: '25px',  tr: '-20deg' },
  ];
  const confettiHtml = pieces.map(p => `
    <span class="flip7-confetti" style="top:${p.top}; left:${p.left}; --tx:${p.tx}; --ty:${p.ty}; --tr:${p.tr};">${p.emoji}</span>
  `).join('');
  return `<div class="flip7-overlay"></div>${confettiHtml}`;
}

/** Frost overlay markup — a few absolutely-positioned decoration divs the freeze CSS animates. */
function frostMarkup() {
  return `
    <div class="frost-overlay"></div>
    <div class="frost-crack" style="top:35%; left:15%; width:60%; height:2px; transform:rotate(-8deg);"></div>
    <div class="frost-crack" style="top:60%; left:25%; width:45%; height:2px; transform:rotate(12deg);"></div>
    <div class="frost-snowflake">❄️</div>
  `;
}

/**
 * Determine this player's freeze animation state for the current render:
 * 'freezing' the first time we render them after a freeze is applied,
 * 'frozen-settled' on every render after that (until the round resets),
 * or '' if they were never frozen (a voluntary stay doesn't get frost).
 */
function frostClassFor(playerId, ps) {
  if (!ps.has_stayed) return '';
  if (pendingFreezeIds.has(playerId)) {
    pendingFreezeIds.delete(playerId);
    animatedFrozenIds.add(playerId);
    return 'freezing';
  }
  return animatedFrozenIds.has(playerId) ? 'frozen-settled' : '';
}

function renderOpponent(playerInfo, ps, isCurrentPlayer = false) {
  const div = document.createElement('div');
  const frostClass = frostClassFor(playerInfo.player_id, ps);
  const flip7Class = hasFlip7(ps) ? 'flip7-celebrate' : '';
  div.className = 'opponent-row' + (isCurrentPlayer ? ' opponent-active-turn' : '') + (frostClass ? ' ' + frostClass : '') + (flip7Class ? ' ' + flip7Class : '');

  const cardCount = ps.card_count ?? ps.cards_in_hand.length;
  const cardsHtml = ps.cards_in_hand.length
    ? `<div class="opponent-hand f7-hand">${ps.cards_in_hand.map(c => cardHtml(c)).join('')}</div>`
    : '<div class="opponent-hand"><span class="hint">No cards yet</span></div>';

  div.innerHTML = `
    ${frostClass ? frostMarkup() : ''}
    ${flip7Class ? flip7Markup() : ''}
    <div class="opponent-name">${escHtml(playerInfo.name)} ${statusBadge(ps, isCurrentPlayer, !!frostClass)}</div>
    <div class="opponent-stats">
      <span>${cardCount} card${cardCount !== 1 ? 's' : ''}</span>
      <span>Round: <strong>${ps.round_score}</strong></span>
      <span>Total: <strong>${ps.total_score}</strong></span>
      ${ps.has_second_chance ? '<span class="badge badge-sc">SC</span>' : ''}
    </div>
    ${cardsHtml}
  `;
  return div;
}

function cycleCardSort() {
  const idx = SORT_MODES.indexOf(cardSortMode);
  cardSortMode = SORT_MODES[(idx + 1) % SORT_MODES.length];
  if (lastState) renderGameState(lastState);
}

const TYPE_ORDER = { number: 0, modifier: 1, action: 2 };

function sortedCards(cards) {
  if (cardSortMode === 'original') return [...cards];
  return [...cards].sort((a, b) => {
    const typeA = TYPE_ORDER[a.card_type] ?? 9;
    const typeB = TYPE_ORDER[b.card_type] ?? 9;
    if (typeA !== typeB) return typeA - typeB;
    return (b.value ?? 0) - (a.value ?? 0);
  });
}

/**
 * Render the local player's panel.
 * Pass `interactive: false` for read-only contexts (round-ended / game-over
 * screens) to skip the turn banner logic and action buttons.
 */
function renderMyPanel(playerInfo, ps, state, { interactive = true } = {}) {
  const div = document.createElement('div');
  const frostClass = frostClassFor(playerInfo.player_id, ps);
  const flip7Class = hasFlip7(ps) ? 'flip7-celebrate' : '';
  div.className = 'my-panel-inner' + (frostClass ? ' ' + frostClass : '') + (flip7Class ? ' ' + flip7Class : '');

  const round = state.current_round;
  const isMyTurn = interactive && round && round.current_player_id === state.your_player_id;

  // Hand display (respect current sort mode)
  const displayCards = sortedCards(ps.cards_in_hand);
  const handHtml = displayCards.length
    ? displayCards.map(c => cardHtml(c)).join('')
    : '<span class="hint">No cards yet</span>';

  // Score breakdown text
  let scoreText = `Round score: <strong>${ps.round_score}</strong> &nbsp;|&nbsp; Total: <strong>${ps.total_score}</strong>`;
  if (interactive && ps.flip_three_active) {
    scoreText += ` &nbsp;|&nbsp; <span class="badge badge-flip">Must draw ${ps.flip_three_count} more</span>`;
  }

  // Action buttons — only shown when it's this player's turn
  const canAct  = isMyTurn && !ps.has_stayed && !ps.is_busted;
  const canStay = canAct && !(ps.flip_three_active && ps.flip_three_count > 0);
  const drawLabel = ps.flip_three_active
    ? `🎲 Draw Card (forced, ${ps.flip_three_count} left)`
    : '🎲 Draw Card';

  const sortLabel = SORT_LABELS[cardSortMode];

  div.innerHTML = `
    ${frostClass ? frostMarkup() : ''}
    ${flip7Class ? flip7Markup() : ''}
    <div class="my-name">${escHtml(playerInfo.name)} ${statusBadge(ps, isMyTurn, !!frostClass)}</div>
    <div class="hand-header">
      <span class="hand-label">Cards in hand</span>
      <button class="btn btn-sort btn-small" onclick="cycleCardSort()">${sortLabel}</button>
    </div>
    <div class="my-hand">${handHtml}</div>
    <div class="my-score">${scoreText}</div>
    ${canAct ? `
      <div class="action-buttons">
        <button class="btn btn-deal" onclick="sendDrawCard()">${drawLabel}</button>
        <button class="btn btn-stay" onclick="sendStay()" ${canStay ? '' : 'disabled'}>✋ Stay</button>
        ${ps.has_second_chance ? '<button class="btn btn-sc" onclick="openSecondChance()">🎯 Use Second Chance</button>' : ''}
      </div>
    ` : (interactive && !ps.has_stayed && !ps.is_busted ? '<p class="hint waiting-hint">⏳ Waiting for your turn…</p>' : '')}
  `;
  return div;
}

// =============================================================================
// Round ending board — shows final state + reason before score screen
// =============================================================================

const END_REASON_LABELS = {
  all_stayed:    '✋ All players have stayed',
  player_busted: '💥 A player busted!',
  deck_exhausted:'🃏 Deck exhausted',
  flip_7:        '🎉 FLIP 7!',
};

function renderRoundEndingBoard(state) {
  lastState = state;
  showScreen('screen-game');

  const history = state.round_history;
  if (!history || history.length === 0) return;
  const round = history[history.length - 1];

  document.getElementById('game-round-display').textContent = `Round ${round.round_number}`;
  document.getElementById('game-deck-display').textContent  = `Cards: ${round.cards_remaining_in_deck}`;
  document.getElementById('action-waiting-banner').classList.add('hidden');

  // Show end reason in the turn banner
  const turnBanner = document.getElementById('turn-banner');
  const reasonLabel = END_REASON_LABELS[round.end_reason] ?? 'Round over';
  turnBanner.textContent = `Round ended — ${reasonLabel}`;
  turnBanner.className = round.end_reason === 'flip_7' ? 'turn-banner turn-flip7' : 'turn-banner turn-other';
  turnBanner.classList.remove('hidden');

  // Render all players from the completed round (no action buttons)
  const opponentsPanel = document.getElementById('opponents-panel');
  opponentsPanel.innerHTML = '';
  state.players.forEach(player => {
    if (player.player_id === state.your_player_id) return;
    const ps = round.player_states[player.player_id];
    if (!ps) return;
    opponentsPanel.appendChild(renderOpponent(player, ps, false));
  });

  const myInfo = state.players.find(p => p.player_id === state.your_player_id);
  const myPs   = round.player_states[state.your_player_id];
  const myPanel = document.getElementById('my-panel');
  myPanel.innerHTML = '';
  if (myInfo && myPs) {
    myPanel.appendChild(renderMyPanel(myInfo, myPs, state, { interactive: false }));
  }
}

// =============================================================================
// Scoreboard card
// =============================================================================

let scoreboardTab = 'this-game'; // 'this-game' | 'overall'

function showScoreboardTab(which) {
  scoreboardTab = which;
  document.getElementById('scoreboard-tab-this-game').classList.toggle('active', which === 'this-game');
  document.getElementById('scoreboard-tab-overall').classList.toggle('active', which === 'overall');
  document.getElementById('scoreboard-panel-this-game').classList.toggle('active', which === 'this-game');
  document.getElementById('scoreboard-panel-overall').classList.toggle('active', which === 'overall');
  if (lastState) renderScoreboard(lastState);
}

/** Games won per player_id, from match_history. */
function calculateWinCounts(state) {
  const winCounts = {};
  state.players.forEach(p => { winCounts[p.player_id] = 0; });
  (state.match_history || []).forEach(g => {
    if (g.winner_id && winCounts[g.winner_id] !== undefined) winCounts[g.winner_id] += 1;
  });
  return winCounts;
}

/**
 * Renders the scoreboard card: leader callout, "This Game" / "Overall"
 * score lists, and (at round-end / game-over) the actions row that used to
 * live on separate screens. The card grows in place for those moments
 * rather than handing off to an overlay — no reason/deltas are shown since
 * the board above already makes the outcome visible.
 *
 * opts.phase: 'round-end' | 'game-over' | undefined
 */
function renderScoreboard(state, opts = {}) {
  const roundHistory = state.round_history || [];
  const currentRound = state.current_round;
  const matchHistory = state.match_history || [];

  // Standings source: the active round if one exists, otherwise the most
  // recently completed round (round just ended / game just ended).
  const sourceStates = currentRound
    ? currentRound.player_states
    : (roundHistory.length ? roundHistory[roundHistory.length - 1].player_states : {});

  const standings = state.players
    .map(p => ({ ...p, total: sourceStates[p.player_id]?.total_score ?? 0 }))
    .sort((a, b) => b.total - a.total);

  document.getElementById('scoreboard-panel-this-game').innerHTML = standings.map((p, i) => `
    <div class="score-row ${p.player_id === state.your_player_id ? 'is-me' : ''}">
      <span>${i === 0 ? '👑 ' : ''}${escHtml(p.name)}${p.player_id === state.your_player_id ? ' <span class="you-tag">YOU</span>' : ''}</span>
      <span><strong>${p.total}</strong></span>
    </div>
  `).join('');

  // "Overall" — games won this room. The tab only appears once at least
  // one rematch has happened, since there's nothing to tally before that.
  const overallTab = document.getElementById('scoreboard-tab-overall');
  const winCounts = calculateWinCounts(state);
  if (matchHistory.length === 0) {
    overallTab.classList.add('hidden');
    if (scoreboardTab === 'overall') showScoreboardTab('this-game');
  } else {
    overallTab.classList.remove('hidden');
    const tallySorted = state.players
      .map(p => ({ ...p, wins: winCounts[p.player_id] || 0 }))
      .sort((a, b) => b.wins - a.wins);

    document.getElementById('scoreboard-panel-overall').innerHTML = tallySorted.map((p, i) => `
      <div class="score-row ${p.player_id === state.your_player_id ? 'is-me' : ''}">
        <span>${i === 0 && p.wins > 0 ? '👑 ' : ''}${escHtml(p.name)}${p.player_id === state.your_player_id ? ' <span class="you-tag">YOU</span>' : ''}</span>
        <span>${p.wins}<span class="sub">win${p.wins !== 1 ? 's' : ''}</span></span>
      </div>
    `).join('');
  }

  // Leader callout in the header.
  const leaderEl = document.getElementById('scoreboard-leader');
  if (scoreboardTab === 'overall' && matchHistory.length > 0) {
    const top = [...state.players].sort((a, b) => (winCounts[b.player_id] || 0) - (winCounts[a.player_id] || 0))[0];
    leaderEl.textContent = top ? `— ${top.name} leads, ${winCounts[top.player_id] || 0}` : '';
  } else if (standings.length) {
    leaderEl.textContent = `— ${standings[0].name} leads, ${standings[0].total}`;
  } else {
    leaderEl.textContent = '';
  }

  // Card highlight + actions row.
  const card    = document.getElementById('scoreboard-card');
  const actions = document.getElementById('scoreboard-actions');
  card.classList.toggle('is-round-end', opts.phase === 'round-end');
  card.classList.toggle('is-game-over', opts.phase === 'game-over');

  if (opts.phase === 'game-over') {
    actions.classList.add('active');
    actions.innerHTML = state.is_host
      ? '<button class="btn btn-gold" onclick="sendRematch()">🔁 Play Again (Same Room)</button><button class="btn btn-ghost" onclick="resetToLobby()">Leave Room</button>'
      : '<p class="hint">Waiting for the host to start a new game…</p><button class="btn btn-ghost" onclick="resetToLobby()">Leave Room</button>';
  } else if (opts.phase === 'round-end') {
    actions.classList.add('active');
    actions.innerHTML = state.is_host
      ? '<button class="btn btn-primary" onclick="sendStartRound()">▶ Start Next Round</button>'
      : '<p class="hint">Waiting for the host to start the next round…</p>';
  } else {
    actions.classList.remove('active');
    actions.innerHTML = '';
  }
}

async function sendRematch() {
  try {
    const res = await fetch(`/api/rooms/${myGameId}/rematch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_id: myPlayerId }),
    });
    if (!res.ok) {
      const detail = (await res.json()).detail || res.statusText;
      showError('game-error', `Could not start rematch: ${detail}`);
    }
  } catch (err) {
    showError('game-error', `Error: ${err.message}`);
  }
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
// Card rendering — mirrors the physical Flip 7 deck (flip_7/gui/components/card_picker.py)
// =============================================================================

const NUMBER_WORDS = {
  0: 'Zero', 1: 'One', 2: 'Two', 3: 'Three', 4: 'Four',
  5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine',
  10: 'Ten', 11: 'Eleven', 12: 'Twelve',
};

const NUMBER_COLORS = {
  0: '#8f8f83', 1: '#a68f6b', 2: '#b8c23c', 3: '#c74a43',
  4: '#5aa6b3', 5: '#4a9e6b', 6: '#8a6fae', 7: '#c15a4a',
  8: '#3f9b6f', 9: '#e08a3c', 10: '#e2453a', 11: '#4472b8',
  12: '#8a7f8f',
};

function cardHtml(card) {
  if (card.card_type === 'number') {
    const color = NUMBER_COLORS[card.value] ?? '#8f8f83';
    const word  = NUMBER_WORDS[card.value] ?? String(card.value);
    return (
      `<div class="f7-card" style="--c:${color};">` +
      `<div class="f7-band">${word}</div>` +
      `<div class="f7-num">${card.value}</div>` +
      `<div class="f7-band f7-band-bottom">${word}</div>` +
      `</div>`
    );
  }
  if (card.card_type === 'modifier') {
    const isMult = card.modifier_type === 'multiply_2';
    const chip   = isMult ? `×${card.value}` : `+${card.value}`;
    const capTop = isMult ? 'The sum of your number cards' : 'Add to your final score';
    return (
      `<div class="f7-tcard f7-mod">` +
      `<div class="f7-tcard-cap">${capTop}</div>` +
      `<div class="f7-tcard-chip">${chip}</div>` +
      `<div class="f7-tcard-cap">Modifier</div>` +
      `</div>`
    );
  }
  if (card.card_type === 'action') {
    const variants = {
      freeze:         ['f7-freeze', 'FREEZE', 'Play on an active player'],
      flip_three:     ['f7-flip3', 'FLIP<br>THREE', 'Play on an active player'],
      second_chance:  ['f7-second', 'SECOND<br>CHANCE', 'Save this card until needed'],
    };
    const [variantClass, label, caption] = variants[card.action_type] ?? ['f7-freeze', card.action_type, ''];
    return (
      `<div class="f7-tcard ${variantClass}">` +
      `<div class="f7-tcard-cap">${caption}</div>` +
      `<div class="f7-tcard-chip" style="font-size:0.9rem;">${label}</div>` +
      `<div class="f7-tcard-cap">Instant Action</div>` +
      `</div>`
    );
  }
  return `<div class="f7-tcard">${cardLabel(card)}</div>`;
}

// =============================================================================
// Send functions
// =============================================================================

function sendDrawCard() {
  sendMessage({ type: 'deal_card' });
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
  // Allow Enter key on lobby inputs.
  ['player-name-input', 'room-code-input'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') handleJoinOrCreate();
    });
  });

  paintFeltGrain();
});

/**
 * Procedural fabric grain for the felt table background — generates a small
 * noise tile on an off-screen canvas and applies it as a repeating CSS
 * background on #grainLayer, instead of shipping an image asset.
 */
function paintFeltGrain() {
  const w = 160, h = 160;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');

  const imageData = ctx.createImageData(w, h);
  for (let i = 0; i < imageData.data.length; i += 4) {
    const v = 128 + (Math.random() - 0.5) * 90;
    imageData.data[i] = v;
    imageData.data[i + 1] = v;
    imageData.data[i + 2] = v;
    imageData.data[i + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);

  document.getElementById('grainLayer').style.backgroundImage = `url(${canvas.toDataURL()})`;
}