(() => {
  const config = window.SQUADFINDER_ROOM_COMMS;
  if (!config) return;

  const csrf = window.SQUADFINDER_CSRF;
  const roomBase = `/api/room/${config.roomId}`;
  const requestJson = async (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrf);
    if (options.body && typeof options.body !== 'string') {
      headers.set('Content-Type', 'application/json');
      options.body = JSON.stringify(options.body);
    }
    const response = await fetch(url, {...options, headers, credentials: 'same-origin'});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  };

  document.querySelectorAll('[data-comms-tab]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-comms-tab]').forEach(tab => {
        const active = tab === button;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', String(active));
      });
      document.querySelectorAll('.comms-panel').forEach(panel => panel.classList.toggle('active', panel.id === button.dataset.commsTab));
      document.getElementById(button.dataset.commsTab)?.scrollIntoView({block: 'nearest'});
    });
  });

  const messagesEl = document.querySelector('[data-chat-messages]');
  const emptyEl = document.querySelector('[data-chat-empty]');
  const chatStatus = document.querySelector('[data-chat-status]');
  const chatForm = document.querySelector('[data-chat-form]');
  const chatInput = document.querySelector('[data-chat-input]');
  const chatCounter = document.querySelector('[data-chat-counter]');
  let lastMessageId = 0;
  let chatStarted = false;

  const formatTime = value => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat([], {hour: '2-digit', minute: '2-digit'}).format(date);
  };

  const appendMessage = message => {
    if (document.querySelector(`[data-message-id="${message.id}"]`)) return;
    emptyEl?.remove();
    const nearBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 90;
    const article = document.createElement('article');
    article.className = 'chat-message';
    article.dataset.messageId = message.id;
    const avatar = document.createElement('span');
    avatar.className = 'avatar chat-avatar';
    avatar.textContent = (message.display_name || '?').charAt(0).toUpperCase();
    const content = document.createElement('div');
    const header = document.createElement('div');
    header.className = 'chat-message-head';
    const name = document.createElement('strong');
    name.textContent = message.display_name;
    const username = document.createElement('span');
    username.textContent = `@${message.username}`;
    const time = document.createElement('time');
    time.textContent = formatTime(message.created_at);
    time.dateTime = message.created_at;
    const body = document.createElement('p');
    body.textContent = message.body;
    header.append(name, username, time);
    content.append(header, body);
    article.append(avatar, content);
    messagesEl.appendChild(article);
    lastMessageId = Math.max(lastMessageId, Number(message.id));
    if (!chatStarted || nearBottom) messagesEl.scrollTop = messagesEl.scrollHeight;
  };

  const pollMessages = async () => {
    try {
      const data = await requestJson(`${roomBase}/messages?after=${lastMessageId}`);
      data.messages.forEach(appendMessage);
      chatStarted = true;
      if (chatStatus) chatStatus.textContent = 'Live';
    } catch (error) {
      if (chatStatus) chatStatus.textContent = error.message;
    }
  };

  if (messagesEl) {
    pollMessages();
    window.setInterval(pollMessages, 2200);
  }

  const updateCounter = () => {
    if (!chatCounter || !chatInput) return;
    chatCounter.textContent = `${chatInput.value.length}/1000`;
    chatInput.style.height = 'auto';
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 140)}px`;
  };
  chatInput?.addEventListener('input', updateCounter);
  chatInput?.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      chatForm?.requestSubmit();
    }
  });
  chatForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const body = chatInput.value.trim();
    if (!body) return;
    const button = chatForm.querySelector('button');
    button.disabled = true;
    try {
      await requestJson(`${roomBase}/messages`, {method: 'POST', body: {body}});
      chatInput.value = '';
      updateCounter();
      await pollMessages();
    } catch (error) {
      if (chatStatus) chatStatus.textContent = error.message;
    } finally {
      button.disabled = false;
      chatInput.focus();
    }
  });

  const voiceStatus = document.querySelector('[data-voice-status]');
  const warning = document.querySelector('[data-voice-warning]');
  const participantsEl = document.querySelector('[data-voice-participants]');
  const audioEl = document.querySelector('[data-voice-audio]');
  const joinButton = document.querySelector('[data-voice-join]');
  const leaveButton = document.querySelector('[data-voice-leave]');
  const muteButton = document.querySelector('[data-voice-mute]');
  const deafenButton = document.querySelector('[data-voice-deafen]');
  const peerConnections = new Map();
  let peerDirectory = new Map();
  let localStream = null;
  let sessionId = null;
  let muted = false;
  let deafened = false;
  let connected = false;
  let signalTimer = null;
  let peerTimer = null;
  let heartbeatTimer = null;

  const makeSessionId = () => {
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  };

  const setVoiceStatus = (text, state = '') => {
    if (!voiceStatus) return;
    voiceStatus.textContent = text;
    voiceStatus.dataset.state = state;
  };

  const renderParticipants = peers => {
    if (!participantsEl) return;
    participantsEl.textContent = '';
    const all = connected ? [{
      session_id: sessionId,
      user_id: config.userId,
      display_name: config.displayName,
      username: config.username,
      muted,
      deafened,
      self: true,
    }, ...peers] : peers;
    if (!all.length) {
      const empty = document.createElement('div');
      empty.className = 'voice-empty';
      empty.innerHTML = '<span>◖</span><h3>Voice channel is quiet</h3><p>Join voice to speak with squad members from the browser.</p>';
      participantsEl.appendChild(empty);
      return;
    }
    all.forEach(peer => {
      const item = document.createElement('article');
      item.className = 'voice-person';
      const avatar = document.createElement('span');
      avatar.className = 'avatar voice-avatar';
      avatar.textContent = (peer.display_name || '?').charAt(0).toUpperCase();
      const info = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = `${peer.display_name}${peer.self ? ' (You)' : ''}`;
      const meta = document.createElement('small');
      const states = [];
      if (peer.muted) states.push('Muted');
      if (peer.deafened) states.push('Deafened');
      meta.textContent = states.length ? states.join(' · ') : `@${peer.username}`;
      const state = document.createElement('span');
      state.className = 'voice-speaking-indicator';
      state.title = 'Connected to voice';
      info.append(name, meta);
      item.append(avatar, info, state);
      participantsEl.appendChild(item);
    });
  };

  const sendSignal = (target, payload) => requestJson(`${roomBase}/voice/signal`, {
    method: 'POST',
    body: {session_id: sessionId, target_session: target, payload},
  }).catch(() => {});

  const closePeer = peerId => {
    const entry = peerConnections.get(peerId);
    if (!entry) return;
    try { entry.pc.close(); } catch (_) {}
    entry.audio?.remove();
    peerConnections.delete(peerId);
  };

  const flushCandidates = async entry => {
    if (!entry.pc.remoteDescription) return;
    while (entry.candidates.length) {
      const candidate = entry.candidates.shift();
      try { await entry.pc.addIceCandidate(candidate); } catch (_) {}
    }
  };

  const ensurePeer = (peerId, initiate = false) => {
    if (peerConnections.has(peerId)) return peerConnections.get(peerId);
    const pc = new RTCPeerConnection({
      iceServers: config.iceServers || [],
    });
    const audio = document.createElement('audio');
    audio.autoplay = true;
    audio.playsInline = true;
    audio.muted = deafened;
    audio.dataset.peerSession = peerId;
    audioEl?.appendChild(audio);
    const entry = {pc, audio, candidates: []};
    peerConnections.set(peerId, entry);
    localStream?.getTracks().forEach(track => pc.addTrack(track, localStream));
    pc.addEventListener('icecandidate', event => {
      if (event.candidate) sendSignal(peerId, {type: 'ice', candidate: event.candidate.toJSON()});
    });
    pc.addEventListener('track', event => {
      audio.srcObject = event.streams[0];
      audio.muted = deafened;
      audio.play().catch(() => {});
    });
    pc.addEventListener('connectionstatechange', () => {
      if (['failed', 'closed'].includes(pc.connectionState)) closePeer(peerId);
    });
    if (initiate) {
      (async () => {
        try {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          await sendSignal(peerId, {type: 'offer', sdp: pc.localDescription});
        } catch (_) { closePeer(peerId); }
      })();
    }
    return entry;
  };

  const handleSignal = async signal => {
    const peerId = signal.sender_session;
    const payload = signal.payload || {};
    const entry = ensurePeer(peerId, false);
    try {
      if (payload.type === 'offer') {
        await entry.pc.setRemoteDescription(payload.sdp);
        await flushCandidates(entry);
        const answer = await entry.pc.createAnswer();
        await entry.pc.setLocalDescription(answer);
        await sendSignal(peerId, {type: 'answer', sdp: entry.pc.localDescription});
      } else if (payload.type === 'answer') {
        if (!entry.pc.currentRemoteDescription) {
          await entry.pc.setRemoteDescription(payload.sdp);
          await flushCandidates(entry);
        }
      } else if (payload.type === 'ice' && payload.candidate) {
        const candidate = new RTCIceCandidate(payload.candidate);
        if (entry.pc.remoteDescription) await entry.pc.addIceCandidate(candidate);
        else entry.candidates.push(candidate);
      }
    } catch (_) {}
  };

  const pollSignals = async () => {
    if (!connected) return;
    try {
      const data = await requestJson(`${roomBase}/voice/signals?session_id=${encodeURIComponent(sessionId)}`);
      for (const signal of data.signals) await handleSignal(signal);
    } catch (error) {
      setVoiceStatus(error.message, 'error');
    }
  };

  const pollPeers = async () => {
    if (!connected) return;
    try {
      const data = await requestJson(`${roomBase}/voice/peers?session_id=${encodeURIComponent(sessionId)}`);
      peerDirectory = new Map(data.peers.map(peer => [peer.session_id, peer]));
      for (const peerId of peerConnections.keys()) {
        if (!peerDirectory.has(peerId)) closePeer(peerId);
      }
      renderParticipants(data.peers);
      setVoiceStatus(`Connected · ${data.peers.length + 1} in voice`, 'connected');
    } catch (error) {
      setVoiceStatus(error.message, 'error');
    }
  };

  const heartbeat = () => connected && requestJson(`${roomBase}/voice/heartbeat`, {
    method: 'POST', body: {session_id: sessionId, muted, deafened},
  }).catch(() => {});

  const updateVoiceControls = () => {
    joinButton.hidden = connected;
    leaveButton.hidden = !connected;
    muteButton.disabled = !connected;
    deafenButton.disabled = !connected;
    muteButton.setAttribute('aria-pressed', String(muted));
    deafenButton.setAttribute('aria-pressed', String(deafened));
    muteButton.classList.toggle('active', muted);
    deafenButton.classList.toggle('active', deafened);
    muteButton.querySelector('small').textContent = muted ? 'Unmute' : 'Mute';
    deafenButton.querySelector('small').textContent = deafened ? 'Undeafen' : 'Deafen';
  };

  const disconnectVoice = async (notify = true) => {
    if (!connected) return;
    connected = false;
    window.clearInterval(signalTimer);
    window.clearInterval(peerTimer);
    window.clearInterval(heartbeatTimer);
    for (const peerId of [...peerConnections.keys()]) closePeer(peerId);
    localStream?.getTracks().forEach(track => track.stop());
    localStream = null;
    if (notify) {
      try { await requestJson(`${roomBase}/voice/leave`, {method: 'POST', body: {session_id: sessionId}}); } catch (_) {}
    }
    muted = false;
    deafened = false;
    setVoiceStatus('Not connected');
    renderParticipants([]);
    updateVoiceControls();
  };

  joinButton?.addEventListener('click', async () => {
    if (connected) return;
    warning.hidden = true;
    if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(location.hostname)) {
      warning.hidden = false;
      warning.textContent = 'Your browser blocks microphone access on an insecure network address. Open SquadFinder through HTTPS, then try again.';
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
      warning.hidden = false;
      warning.textContent = 'This browser does not support the voice features required by SquadFinder.';
      return;
    }
    joinButton.disabled = true;
    setVoiceStatus('Requesting microphone…');
    try {
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
        video: false,
      });
      sessionId = makeSessionId();
      const data = await requestJson(`${roomBase}/voice/join`, {method: 'POST', body: {session_id: sessionId}});
      connected = true;
      peerDirectory = new Map(data.peers.map(peer => [peer.session_id, peer]));
      renderParticipants(data.peers);
      updateVoiceControls();
      setVoiceStatus(`Connected · ${data.peers.length + 1} in voice`, 'connected');
      data.peers.forEach(peer => ensurePeer(peer.session_id, true));
      signalTimer = window.setInterval(pollSignals, 850);
      peerTimer = window.setInterval(pollPeers, 3000);
      heartbeatTimer = window.setInterval(heartbeat, 10000);
      pollSignals();
    } catch (error) {
      localStream?.getTracks().forEach(track => track.stop());
      localStream = null;
      warning.hidden = false;
      warning.textContent = error.name === 'NotAllowedError'
        ? 'Microphone permission was denied. Allow microphone access in the browser and join again.'
        : error.message;
      setVoiceStatus('Connection failed', 'error');
    } finally {
      joinButton.disabled = false;
    }
  });

  muteButton?.addEventListener('click', () => {
    muted = !muted;
    localStream?.getAudioTracks().forEach(track => { track.enabled = !muted; });
    updateVoiceControls();
    renderParticipants([...peerDirectory.values()]);
    heartbeat();
  });

  deafenButton?.addEventListener('click', () => {
    deafened = !deafened;
    audioEl?.querySelectorAll('audio').forEach(audio => { audio.muted = deafened; });
    updateVoiceControls();
    renderParticipants([...peerDirectory.values()]);
    heartbeat();
  });

  leaveButton?.addEventListener('click', () => disconnectVoice(true));
  window.addEventListener('beforeunload', () => {
    if (!connected) return;
    fetch(`${roomBase}/voice/leave`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
      body: JSON.stringify({session_id: sessionId}),
      credentials: 'same-origin',
      keepalive: true,
    }).catch(() => {});
    localStream?.getTracks().forEach(track => track.stop());
  });

  updateVoiceControls();
  renderParticipants([]);
})();
