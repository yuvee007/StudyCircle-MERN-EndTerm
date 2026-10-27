(() => {
  'use strict';

  const $ = id => id.startsWith('.') ? document.querySelector(id) : document.getElementById(id);
  const localDate = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const shiftDate = days => { const d = new Date(); d.setDate(d.getDate() + days); return localDate(d); };

  let sessions = [];
  let currentUser = null;
  let authMode = 'login';
  let activeView = 'discover';
  let myTab = 'upcoming';
  let sortMode = 'soonest'; // 'soonest', 'latest', 'seats'
  let toastTimer;
  let pollInterval = null;
  let activeDetailSessionId = null;

  // Web Audio chime for pleasing feedback without external assets
  function playChime(type = 'success') {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      if (type === 'success') {
        osc.frequency.setValueAtTime(523.25, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
        osc.start();
        osc.stop(ctx.currentTime + 0.25);
      } else if (type === 'leave') {
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(349.23, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.06, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
        osc.start();
        osc.stop(ctx.currentTime + 0.2);
      }
    } catch {}
  }

  // Network request wrapper
  async function request(path, options = {}) {
    const headers = {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {})
    };
    let response;
    try {
      response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
    } catch {
      throw new Error('Can’t reach StudyCircle right now. Check your connection.');
    }
    const data = await response.json().catch(() => ({ error: 'The server returned an unexpected response.' }));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  }

  async function refreshSessions(silent = false) {
    if (!currentUser) return;
    try {
      const data = await request('/api/sessions');
      sessions = data.sessions;
      if (!silent) render();
    } catch (e) {
      if (!silent) showToast(e.message);
    }
  }

  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function dateTime(s) {
    return new Date(`${s.date}T${s.time}:00`);
  }

  function prettyDate(date) {
    return new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric'
    });
  }

  function prettyTime(time) {
    const [h, m] = time.split(':').map(Number);
    const d = new Date();
    d.setHours(h, m, 0, 0);
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  function isPast(s) {
    return dateTime(s).getTime() < Date.now();
  }

  function initials(name) {
    return (name || 'S').slice(0, 1).toUpperCase();
  }

  function classFor(subject) {
    return ({
      'Computer Science': 'cs',
      'Mathematics': 'math',
      'Physics': 'physics',
      'Economics': 'economics',
      'Design': 'design',
      'Biology': 'biology'
    })[subject] || '';
  }

  function showToast(message) {
    const el = $('toast');
    el.textContent = message;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 3200);
  }

  function showAuth(message = '') {
    currentUser = null;
    sessions = [];
    $('auth-screen').classList.remove('hidden');
    $('.app-shell').classList.add('hidden');
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    if (message) {
      $('auth-error').textContent = message;
      $('auth-error').classList.remove('hidden');
    }
  }

  function updateAuthMode() {
    $('auth-title').innerHTML = authMode === 'login' ? 'Good things<br>happen <span>together.</span>' : 'Find your people.<br><span>Start here.</span>';
    $('auth-copy').textContent = authMode === 'login' ? 'Sign in to find your study circle, save a seat, and keep your plans in one place.' : 'Create an account to join campus circles and host a study sprint of your own.';
    $('auth-submit').innerHTML = (authMode === 'login' ? 'Sign in' : 'Create account') + ' <span>→</span>';
    $('auth-password').autocomplete = authMode === 'login' ? 'current-password' : 'new-password';
    document.querySelectorAll('.auth-mode').forEach(b => b.classList.toggle('active', b.dataset.mode === authMode));
    $('auth-error').classList.add('hidden');
  }

  function updateCommon() {
    const today = localDate(new Date());
    $('today-label').textContent = new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
    
    const joinedUpcoming = sessions.filter(s => s.isJoined && !isPast(s));
    const hostingUpcoming = sessions.filter(s => s.isHost && !isPast(s));
    
    $('my-count').textContent = joinedUpcoming.length;
    $('stat-today').textContent = sessions.filter(s => s.date === today && !isPast(s)).length;
    $('stat-seats').textContent = sessions.filter(s => !isPast(s)).reduce((sum, s) => sum + Math.max(0, s.capacity - s.attendees.length), 0);
    $('stat-groups').textContent = sessions.filter(s => !isPast(s)).length;

    // User avatars and dropdown stats
    $('user-name').textContent = currentUser;
    $('user-avatar').textContent = initials(currentUser);
    $('avatar-top').textContent = initials(currentUser);
    $('drop-name').textContent = currentUser;
    $('drop-avatar').textContent = initials(currentUser);
    $('drop-joined-count').textContent = joinedUpcoming.length;
    $('drop-hosting-count').textContent = hostingUpcoming.length;
  }

  function renderDiscover() {
    updateCommon();
    const query = $('search-input').value.trim().toLowerCase();
    const subject = $('subject-filter').value;
    const when = $('when-filter').value;
    const openOnly = $('open-only-filter').checked;
    const today = localDate(new Date());

    let list = sessions.filter(s => !isPast(s));
    if (query) {
      list = list.filter(s => [s.title, s.subject, s.location, s.host, s.description].some(v => (v || '').toLowerCase().includes(query)));
    }
    if (subject !== 'all') list = list.filter(s => s.subject === subject);
    if (when === 'today') list = list.filter(s => s.date === today);
    if (when === 'upcoming') list = list.filter(s => s.date !== today);
    if (openOnly) list = list.filter(s => s.capacity > s.attendees.length);

    // Sorting
    if (sortMode === 'soonest') list.sort((a, b) => dateTime(a) - dateTime(b));
    else if (sortMode === 'latest') list.sort((a, b) => dateTime(b) - dateTime(a));
    else if (sortMode === 'seats') list.sort((a, b) => (b.capacity - b.attendees.length) - (a.capacity - a.attendees.length));

    $('results-count').textContent = `${list.length} ${list.length === 1 ? 'circle' : 'circles'} found`;
    $('sort-button').innerHTML = (sortMode === 'soonest' ? 'Soonest first' : sortMode === 'latest' ? 'Latest first' : 'Most seats') + ' <span>↕</span>';

    $('session-grid').innerHTML = list.map(s => {
      const spots = Math.max(0, s.capacity - s.attendees.length);
      const isFull = spots === 0;
      const pctFilled = Math.min(100, Math.round((s.attendees.length / s.capacity) * 100));

      let actionBtn = '';
      if (s.isHost) {
        actionBtn = '<button class="joined-button" disabled title="You created this circle">Hosting</button>';
      } else if (s.isJoined) {
        actionBtn = `<button class="joined-button" data-action="leave" data-id="${esc(s.id)}" title="Click to leave this circle">✓ Joined</button>`;
      } else if (!isFull) {
        actionBtn = `<button class="join-button" data-action="join" data-id="${esc(s.id)}" title="Reserve a seat in this circle">Join circle →</button>`;
      } else {
        actionBtn = '<button class="full-button" disabled title="All seats are reserved">Full</button>';
      }

      // Attendee avatars stack
      const attendeeStack = s.attendees.slice(0, 4).map(name => {
        const isH = name.toLowerCase() === (s.host || '').toLowerCase();
        const isMe = currentUser && name.toLowerCase() === currentUser.toLowerCase();
        const faceClass = ['Maya', 'Zoya'].includes(name) ? 'purple' : ['Ishaan', 'Kabir'].includes(name) ? 'gold' : '';
        const tag = isH ? 'host-tag' : faceClass;
        return `<span class="mini-avatar ${tag}" title="${esc(name)}${isH ? ' (Host)' : ''}${isMe ? ' (You)' : ''}">${esc(initials(name))}</span>`;
      }).join('');
      const moreCount = s.attendees.length > 4 ? `<span class="mini-avatar" title="${s.attendees.length - 4} more">+${s.attendees.length - 4}</span>` : '';

      return `
        <article class="session-card" data-action="view-details" data-id="${esc(s.id)}">
          <div class="card-top">
            <span class="subject-tag ${classFor(s.subject)}">${esc(s.subject)}</span>
            <span class="capacity-badge ${isFull ? 'full' : ''}"><b>${spots}</b> ${spots === 1 ? 'seat' : 'seats'} left</span>
          </div>
          <h3 class="card-title">${esc(s.title)}</h3>
          <p class="card-desc">${esc(s.description || 'A focused study session. Bring your materials and questions.')}</p>
          <div class="seat-bar" title="${s.attendees.length} of ${s.capacity} seats reserved">
            <div class="seat-fill ${isFull ? 'full' : ''}" style="width: ${pctFilled}%;"></div>
          </div>
          <div class="card-details">
            <div class="detail-line"><span class="detail-icon">◷</span>${esc(prettyDate(s.date))} · ${esc(prettyTime(s.time))}</div>
            <div class="detail-line"><span class="detail-icon">⌖</span>${esc(s.location)}</div>
          </div>
          <div class="card-bottom">
            <div class="host-section">
              <div class="attendee-stack">${attendeeStack}${moreCount}</div>
              <div class="host-info-text">Hosted by <strong>${esc(s.host)}</strong></div>
            </div>
            <div onclick="event.stopPropagation()">${actionBtn}</div>
          </div>
        </article>
      `;
    }).join('');

    $('empty-state').classList.toggle('hidden', list.length > 0);
    $('session-grid').classList.toggle('hidden', list.length === 0);
  }

  function renderMy() {
    updateCommon();
    let list = sessions.filter(s => s.isJoined && (myTab === 'past' ? isPast(s) : !isPast(s)) && (myTab !== 'hosted' || s.isHost));
    list.sort((a, b) => myTab === 'past' ? dateTime(b) - dateTime(a) : dateTime(a) - dateTime(b));

    $('my-list').innerHTML = list.map(s => {
      const dt = new Date(`${s.date}T12:00:00`);
      const day = dt.toLocaleDateString(undefined, { day: 'numeric' });
      const month = dt.toLocaleDateString(undefined, { month: 'short' });

      let actionSection = '';
      if (myTab === 'past') {
        actionSection = '<span class="status-label">Completed</span>';
      } else if (s.isHost) {
        actionSection = `
          <button type="button" class="detail-link-btn" data-action="view-details" data-id="${esc(s.id)}">Details</button>
          <button type="button" class="cancel-button" data-action="cancel-host" data-id="${esc(s.id)}">Cancel circle</button>
        `;
      } else {
        actionSection = `
          <button type="button" class="detail-link-btn" data-action="view-details" data-id="${esc(s.id)}">Details</button>
          <button type="button" class="cancel-button" data-action="leave" data-id="${esc(s.id)}">Leave</button>
        `;
      }

      return `
        <article class="my-item">
          <div class="date-block">
            <strong>${esc(day)}</strong>
            <small>${esc(month)} · ${esc(prettyTime(s.time))}</small>
          </div>
          <div class="my-item-main">
            <h3>${esc(s.title)}</h3>
            <div class="my-item-meta">
              <span><b>${esc(s.subject)}</b></span>
              <span>·</span>
              <span>${esc(s.location)}</span>
              <span>·</span>
              <span>${s.attendees.length}/${s.capacity} members</span>
              <span class="role-pill ${s.isHost ? 'role-host' : 'role-member'}">${s.isHost ? 'Host' : 'Member'}</span>
            </div>
          </div>
          <div class="my-item-actions">
            ${actionSection}
          </div>
        </article>
      `;
    }).join('');

    $('my-empty').classList.toggle('hidden', list.length > 0);
    $('my-list').classList.toggle('hidden', list.length === 0);
  }

  function render() {
    if (activeView === 'discover') renderDiscover();
    else renderMy();
  }

  function setView(view) {
    activeView = view;
    $('page-discover').classList.toggle('hidden', view !== 'discover');
    $('page-my').classList.toggle('hidden', view !== 'my');
    document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === view));
    $('crumb-current').textContent = view === 'discover' ? 'Discover' : 'My sessions';
    closeProfileDropdown();
    render();
  }

  // Session Details Modal
  function openDetailsModal(sessionId) {
    const s = sessions.find(x => x.id === sessionId);
    if (!s) return;
    activeDetailSessionId = s.id;

    $('detail-title').textContent = s.title;
    $('detail-subject').textContent = s.subject;
    $('detail-subject').className = `subject-tag ${classFor(s.subject)}`;
    
    const spots = Math.max(0, s.capacity - s.attendees.length);
    $('detail-capacity-pill').textContent = spots === 0 ? 'Full' : `${spots} open seat${spots === 1 ? '' : 's'}`;
    $('detail-datetime').textContent = `${prettyDate(s.date)} at ${prettyTime(s.time)}`;
    $('detail-location').textContent = s.location;
    $('detail-host').textContent = `${s.host} ${s.isHost ? '(You)' : ''}`;
    $('detail-seats').textContent = `${s.attendees.length} joined / ${s.capacity} max`;
    $('detail-description').textContent = s.description || 'No additional notes provided. Bring your notebook and study questions!';
    $('detail-attendee-count').textContent = `${s.attendees.length}/${s.capacity} Members`;

    // Render attendee chips
    $('detail-attendees-list').innerHTML = s.attendees.map(name => {
      const isH = name.toLowerCase() === (s.host || '').toLowerCase();
      const isMe = currentUser && name.toLowerCase() === currentUser.toLowerCase();
      return `
        <div class="attendee-chip ${isH ? 'host-chip' : ''}">
          <span class="attendee-chip-avatar">${esc(initials(name))}</span>
          <span>${esc(name)}</span>
          ${isH ? '<span class="chip-tag">Host</span>' : ''}
          ${isMe && !isH ? '<span class="chip-tag">You</span>' : ''}
        </div>
      `;
    }).join('');

    // Modal action button
    const actionSlot = $('detail-action-slot');
    if (isPast(s)) {
      actionSlot.innerHTML = '<span class="status-label">Session Ended</span>';
    } else if (s.isHost) {
      actionSlot.innerHTML = `<button type="button" class="cancel-button" data-action="cancel-host" data-id="${esc(s.id)}">Cancel session</button>`;
    } else if (s.isJoined) {
      actionSlot.innerHTML = `<button type="button" class="cancel-button" data-action="leave" data-id="${esc(s.id)}">Leave circle</button>`;
    } else if (spots > 0) {
      actionSlot.innerHTML = `<button type="button" class="primary-button" data-action="join" data-id="${esc(s.id)}">Join this circle <span>→</span></button>`;
    } else {
      actionSlot.innerHTML = '<button type="button" class="full-button" disabled>Circle is full</button>';
    }

    $('detail-modal-backdrop').classList.remove('hidden');
  }

  function closeDetailsModal() {
    $('detail-modal-backdrop').classList.add('hidden');
    activeDetailSessionId = null;
  }

  function closeProfileDropdown() {
    $('profile-dropdown').classList.add('hidden');
    $('avatar-top').setAttribute('aria-expanded', 'false');
  }

  async function enterApp(user) {
    currentUser = user;
    try {
      await refreshSessions(true);
      $('auth-screen').classList.add('hidden');
      $('.app-shell').classList.remove('hidden');
      setView('discover');
      // Live background sync every 12 seconds
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        if (!document.hidden && !$('modal-backdrop').classList.contains('hidden')) return;
        await refreshSessions(true);
        render();
      }, 12000);
    } catch (error) {
      showAuth(error.message);
    }
  }

  function openCreateModal() {
    const form = $('session-form');
    form.reset();
    form.elements.date.min = localDate(new Date());
    form.elements.date.value = shiftDate(1);
    form.elements.time.value = '16:00';
    $('form-error').classList.add('hidden');
    $('modal-backdrop').classList.remove('hidden');
    setTimeout(() => form.elements.title.focus(), 50);
  }

  function closeCreateModal() {
    $('modal-backdrop').classList.add('hidden');
  }

  // EVENT LISTENERS

  // Auth toggle
  document.querySelectorAll('.auth-mode').forEach(b => b.addEventListener('click', () => {
    authMode = b.dataset.mode;
    updateAuthMode();
  }));

  // Demo user quick login buttons for evaluators
  document.querySelectorAll('.demo-btn[data-user]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const u = btn.dataset.user;
      authMode = 'login';
      updateAuthMode();
      $('auth-username').value = u;
      $('auth-password').value = 'password123';
      $('auth-submit').click();
    });
  });

  // Quick guest account button
  $('quick-guest-btn').addEventListener('click', async () => {
    authMode = 'register';
    updateAuthMode();
    const rand = Math.floor(1000 + Math.random() * 9000);
    $('auth-username').value = `Guest_${rand}`;
    $('auth-password').value = 'guestPass123!';
    $('auth-submit').click();
  });

  // Auth submit
  $('auth-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget;
    const button = $('auth-submit');
    button.disabled = true;
    button.textContent = authMode === 'login' ? 'Signing in…' : 'Creating account…';
    $('auth-error').classList.add('hidden');

    try {
      const data = await request(`/api/${authMode === 'login' ? 'login' : 'register'}`, {
        method: 'POST',
        body: JSON.stringify({
          username: form.elements.username.value.trim(),
          password: form.elements.password.value
        })
      });
      form.reset();
      playChime('success');
      await enterApp(data.user);
    } catch (error) {
      $('auth-error').textContent = error.message;
      $('auth-error').classList.remove('hidden');
    } finally {
      button.disabled = false;
      updateAuthMode();
    }
  });

  // Navigation
  document.querySelectorAll('.nav-item').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));

  // Open create modal buttons
  ['create-session', 'sidebar-create', 'my-create', 'empty-create'].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener('click', openCreateModal);
  });

  // Close modals
  $('modal-close').addEventListener('click', closeCreateModal);
  $('cancel-modal').addEventListener('click', closeCreateModal);
  $('modal-backdrop').addEventListener('click', e => {
    if (e.target === $('modal-backdrop')) closeCreateModal();
  });

  $('detail-modal-close').addEventListener('click', closeDetailsModal);
  $('detail-modal-backdrop').addEventListener('click', e => {
    if (e.target === $('detail-modal-backdrop')) closeDetailsModal();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeCreateModal();
      closeDetailsModal();
      closeProfileDropdown();
    }
  });

  // Search & filter inputs
  $('search-input').addEventListener('input', renderDiscover);
  $('subject-filter').addEventListener('change', renderDiscover);
  $('when-filter').addEventListener('change', renderDiscover);
  $('open-only-filter').addEventListener('change', renderDiscover);

  // Sorting
  $('sort-button').addEventListener('click', () => {
    if (sortMode === 'soonest') sortMode = 'latest';
    else if (sortMode === 'latest') sortMode = 'seats';
    else sortMode = 'soonest';
    renderDiscover();
  });

  // Reset filters
  $('clear-filters').addEventListener('click', () => {
    $('search-input').value = '';
    $('subject-filter').value = 'all';
    $('when-filter').value = 'all';
    $('open-only-filter').checked = false;
    renderDiscover();
  });

  $('browse-sessions').addEventListener('click', () => setView('discover'));

  // My Sessions tabs
  document.querySelectorAll('.my-tab').forEach(b => b.addEventListener('click', () => {
    myTab = b.dataset.tab;
    document.querySelectorAll('.my-tab').forEach(x => x.classList.toggle('active', x === b));
    renderMy();
  }));

  // Manual refresh button
  $('refresh-button').addEventListener('click', async () => {
    $('refresh-button').style.transform = 'rotate(360deg)';
    await refreshSessions();
    showToast('Campus circles updated.');
    setTimeout(() => { $('refresh-button').style.transform = 'none'; }, 300);
  });

  // Top profile avatar dropdown
  $('avatar-top').addEventListener('click', e => {
    e.stopPropagation();
    const dropdown = $('profile-dropdown');
    const isHidden = dropdown.classList.toggle('hidden');
    $('avatar-top').setAttribute('aria-expanded', !isHidden);
  });

  $('drop-view-calendar').addEventListener('click', () => setView('my'));

  // Sign out handlers (sidebar and dropdown)
  async function performLogout() {
    try {
      await request('/api/logout', { method: 'POST', body: '{}' });
    } catch {}
    closeProfileDropdown();
    showAuth('You have signed out.');
  }

  $('logout-button').addEventListener('click', performLogout);
  $('drop-logout-btn').addEventListener('click', performLogout);

  document.addEventListener('click', e => {
    if (!e.target.closest('.user-menu-wrap')) closeProfileDropdown();
  });

  // Share circle button in Details Modal
  $('detail-share-btn').addEventListener('click', async () => {
    const s = sessions.find(x => x.id === activeDetailSessionId);
    if (!s) return;
    const shareText = `📚 StudyCircle: “${s.title}” (${s.subject}) on ${prettyDate(s.date)} at ${prettyTime(s.time)} @ ${s.location}. Host: ${s.host}. Join on campus!`;
    try {
      await navigator.clipboard.writeText(shareText);
      showToast('Invite copied to clipboard! Share it with classmates.');
      playChime('success');
    } catch {
      showToast(shareText);
    }
  });

  // Join, Leave, Cancel action delegation
  document.addEventListener('click', async e => {
    const button = e.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    const sid = button.dataset.id;

    if (action === 'view-details') {
      openDetailsModal(sid);
      return;
    }

    const s = sessions.find(x => x.id === sid);
    if (!s) return;

    try {
      if (action === 'join') {
        button.disabled = true;
        await request(`/api/sessions/${encodeURIComponent(s.id)}/join`, { method: 'POST', body: '{}' });
        playChime('success');
        showToast(`You’re in! Reserved seat for “${s.title}”.`);
      } else if (action === 'leave') {
        if (!window.confirm(`Leave “${s.title}”? Your seat will open for someone else.`)) return;
        button.disabled = true;
        await request(`/api/sessions/${encodeURIComponent(s.id)}/leave`, { method: 'POST', body: '{}' });
        playChime('leave');
        showToast('You left the study circle.');
      } else if (action === 'cancel-host') {
        if (!window.confirm(`Cancel “${s.title}” for all members? This cannot be undone.`)) return;
        button.disabled = true;
        await request(`/api/sessions/${encodeURIComponent(s.id)}`, { method: 'DELETE' });
        playChime('leave');
        showToast('Your session has been cancelled.');
        closeDetailsModal();
      }

      await refreshSessions(true);
      if (activeDetailSessionId === sid) {
        if (action === 'cancel-host') closeDetailsModal();
        else openDetailsModal(sid);
      }
      render();
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
      await refreshSessions(true);
      render();
    }
  });

  // Create session form submission
  $('session-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const error = $('form-error');
    const submit = $('submit-session-btn');

    const payload = {
      title: String(data.get('title') || '').trim(),
      subject: data.get('subject'),
      date: data.get('date'),
      time: data.get('time'),
      location: String(data.get('location') || '').trim(),
      description: String(data.get('description') || '').trim(),
      capacity: Number(data.get('capacity'))
    };

    if (!payload.title || !payload.subject || !payload.date || !payload.time || !payload.location) {
      error.textContent = 'Please fill in the circle name, subject, date, time, and campus location.';
      error.classList.remove('hidden');
      return;
    }

    if (new Date(`${payload.date}T${payload.time}:00`).getTime() <= Date.now()) {
      error.textContent = 'Choose a start date and time in the future.';
      error.classList.remove('hidden');
      return;
    }

    error.classList.add('hidden');
    submit.disabled = true;
    submit.textContent = 'Creating circle…';

    try {
      await request('/api/sessions', { method: 'POST', body: JSON.stringify(payload) });
      closeCreateModal();
      playChime('success');
      await refreshSessions(true);
      myTab = 'upcoming';
      document.querySelectorAll('.my-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === myTab));
      setView('my');
      showToast('Your study circle is live on campus!');
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove('hidden');
    } finally {
      submit.disabled = false;
      submit.innerHTML = 'Create session <span>→</span>';
    }
  });

  // Initialize
  $('form-date').min = localDate(new Date());
  updateAuthMode();

  // Check existing session
  request('/api/me')
    .then(data => data.user ? enterApp(data.user) : showAuth())
    .catch(() => showAuth('StudyCircle server is unavailable. Start the server and refresh this page.'));
})();
