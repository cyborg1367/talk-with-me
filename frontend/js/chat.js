/**
 * chat.js — Frontend logic for the personal AI assistant.
 *
 * Key responsibilities:
 *   1. Load /api/profile and populate the header + sidebar.
 *   2. Render incoming and outgoing messages as chat bubbles.
 *   3. Stream responses from /api/chat/stream using the Fetch Streaming API.
 *   4. Handle tool-call delays transparently (typing indicator stays up).
 *   5. Manage suggestion chips, typing indicator, and send-button state.
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────

const state = {
  history:          [],
  loading:          false,
  botInitials:      'AI',
  firstMessageSent: false,
  userName:         '',
  ownerName:        '',     // set in startChat; used by the CTA
  botResponseCount: 0,      // incremented after every real bot reply
  ctaShown:         false,  // ensures the CTA appears at most once
};

// ── DOM references ────────────────────────────────────────────────────────

const $messages  = document.getElementById('messages');
const $typing    = document.getElementById('typing');
const $input     = document.getElementById('msg-input');
const $sendBtn   = document.getElementById('send-btn');
const $scrollBtn = document.getElementById('scroll-btn');

// ── Marked.js setup ───────────────────────────────────────────────────────

if (typeof marked !== 'undefined') {
  marked.use({ breaks: true, gfm: true, headerIds: false, mangle: false });
}

function toHtml(text) {
  return typeof marked !== 'undefined' ? marked.parse(text) : escapeHtml(text);
}

function escapeHtml(str) {
  const el = document.createElement('div');
  el.appendChild(document.createTextNode(str));
  return el.innerHTML;
}

// ── Dark mode ─────────────────────────────────────────────────────────────

/**
 * Read saved preference (or OS default) and apply the correct theme.
 * Called once on page load.
 */
function initDarkMode() {
  const saved       = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark      = saved ? saved === 'dark' : prefersDark;
  applyTheme(isDark);
}

function toggleDarkMode() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  applyTheme(!isDark);
  localStorage.setItem('theme', !isDark ? 'dark' : 'light');
}

function applyTheme(isDark) {
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.innerHTML       = isDark ? iconSun() : iconMoon();
  btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
}

// ── Copy button ───────────────────────────────────────────────────────────

/**
 * Append a copy button to a bubble element.
 * Clicking it copies the bubble's plain text and shows a ✓ for 1.5 s.
 *
 * @param {HTMLElement} bubble  A `.bubble` element.
 */
function addCopyButton(bubble) {
  const btn = document.createElement('button');
  btn.className = 'copy-btn';
  btn.setAttribute('aria-label', 'Copy message');
  btn.innerHTML = iconCopy();

  btn.addEventListener('click', async e => {
    e.stopPropagation();
    try {
      // innerText gives plain text respecting line breaks; strip trailing whitespace.
      const text = (bubble.innerText || bubble.textContent || '').trim();
      await navigator.clipboard.writeText(text);

      btn.innerHTML = iconCheck();
      btn.classList.add('copy-btn--copied');
      setTimeout(() => {
        btn.innerHTML = iconCopy();
        btn.classList.remove('copy-btn--copied');
      }, 1500);
    } catch (err) {
      console.warn('Copy failed:', err);
    }
  });

  bubble.appendChild(btn);
}

// ── Scroll-to-bottom button ───────────────────────────────────────────────

/**
 * Show the scroll button when the user has scrolled up more than 80 px
 * from the bottom; hide it otherwise.
 */
function updateScrollBtn() {
  const { scrollTop, scrollHeight, clientHeight } = $messages;
  $scrollBtn.hidden = scrollHeight - scrollTop - clientHeight < 80;
}

$messages.addEventListener('scroll', updateScrollBtn, { passive: true });
$scrollBtn.addEventListener('click', scrollToBottom);

// ── Profile loader ────────────────────────────────────────────────────────

async function loadProfile() {
  try {
    const res = await fetch('/api/profile');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const p = await res.json();

    state.botInitials = p.initials;

    // Header
    document.getElementById('hdr-initials').textContent = p.initials;
    document.getElementById('hdr-name').textContent     = p.name;
    document.getElementById('hdr-tagline').textContent  = p.tagline;
    document.getElementById('hdr-status').textContent   = p.status;
    document.title = `${p.name} — AI Assistant`;

    // Sidebar
    document.getElementById('sb-initials').textContent      = p.initials;
    document.getElementById('sb-name').textContent          = p.name;
    document.getElementById('sb-title').textContent         = p.title;
    document.getElementById('sb-tagline').textContent       = p.tagline;
    document.getElementById('sb-status').textContent        = p.status;
    document.getElementById('typing-initials').textContent  = p.initials;

    // Skills
    const $skills = document.getElementById('sb-skills');
    p.skills.forEach(skill => {
      const tag = document.createElement('span');
      tag.className = 'skill-tag';
      tag.textContent = skill;
      $skills.appendChild(tag);
    });

    // Social links
    const links = [
      { href: p.linkedin_url,                     label: 'LinkedIn', icon: iconLinkedIn() },
      { href: p.github_url,                       label: 'GitHub',   icon: iconGitHub() },
      { href: p.email ? `mailto:${p.email}` : '', label: p.email,    icon: iconEmail() },
    ].filter(l => l.href);

    if (links.length) {
      document.getElementById('social-divider').hidden = false;
      const $nav = document.getElementById('sb-social');
      links.forEach(({ href, label, icon }) => {
        const a = document.createElement('a');
        a.href = href; a.className = 'social-link';
        a.rel = 'noopener noreferrer';
        a.target = href.startsWith('mailto') ? '_self' : '_blank';
        a.innerHTML = `${icon}<span>${escapeHtml(label)}</span>`;
        $nav.appendChild(a);
      });
    }

    // Show name overlay — it calls startChat(p) once the user submits their name
    showNameOverlay(p);

  } catch (err) {
    console.error('Profile load failed:', err);
    // If profile fails, show overlay with empty profile data
    showNameOverlay({ name: 'the assistant', initials: 'AI', suggested_questions: [] });
  }
}

// ── Name overlay ──────────────────────────────────────────────────────────

/**
 * Display the name-collection overlay.
 * When the user submits, the overlay fades out and startChat() is called.
 *
 * @param {object} profileData  The profile object returned by /api/profile.
 */
function showNameOverlay(profileData) {
  const $overlay   = document.getElementById('name-overlay');
  const $nameInput = document.getElementById('name-input');
  const $submitBtn = document.getElementById('name-submit-btn');

  // Fill avatar with the profile initials
  const $overlayInitials = document.getElementById('overlay-initials');
  if ($overlayInitials) $overlayInitials.textContent = profileData.initials || 'AI';

  // Enable submit only when there is text
  $nameInput.addEventListener('input', () => {
    $submitBtn.disabled = !$nameInput.value.trim();
  });

  const submit = () => {
    const name = $nameInput.value.trim();
    if (!name) return;

    state.userName = name;

    // Animate the overlay out, then remove it and start the chat
    $overlay.classList.add('hiding');
    $overlay.addEventListener('animationend', () => {
      $overlay.remove();
      startChat(profileData);
    }, { once: true });
  };

  $nameInput.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
  $submitBtn.addEventListener('click', submit);

  // Auto-focus after the card entrance animation finishes
  setTimeout(() => $nameInput.focus(), 400);
}

/**
 * Show the personalised greeting and suggestion chips.
 * Called after the user has submitted their name.
 *
 * @param {object} profileData
 */
function startChat(profileData) {
  const firstName = profileData.name?.split(' ')[0] ?? 'me';
  state.ownerName = profileData.name ?? '';

  const greeting =
    `Hi ${state.userName}! 👋 I'm ${profileData.name}'s AI assistant. `
    + `Feel free to ask me anything about ${firstName}'s background, `
    + `experience, skills, or projects. How can I help you today?`;

  addMessage('bot', greeting);

  // Seed the history so the LLM knows the user's name from the first turn.
  state.history.push({ role: 'user',      content: `Hi, my name is ${state.userName}.` });
  state.history.push({ role: 'assistant', content: greeting });

  if (profileData.suggested_questions?.length) {
    showSuggestions(profileData.suggested_questions);
  }
}

// ── Suggestion chips ──────────────────────────────────────────────────────

function showSuggestions(questions) {
  const container = document.createElement('div');
  container.id = 'suggestions';
  container.className = 'suggestions';
  container.setAttribute('aria-label', 'Suggested questions');

  questions.forEach((q, i) => {
    const btn = document.createElement('button');
    btn.className = 'suggestion-chip';
    btn.textContent = q;
    btn.style.setProperty('--chip-delay', `${i * 0.08 + 0.1}s`);
    btn.setAttribute('aria-label', `Ask: ${q}`);
    btn.addEventListener('click', () => {
      $input.value = q;
      autoGrow();
      sendMessage();
    });
    container.appendChild(btn);
  });

  $messages.appendChild(container);
  scrollToBottom();
}

function hideSuggestions() {
  const el = document.getElementById('suggestions');
  if (!el) return;
  el.classList.add('suggestions--hiding');
  el.addEventListener('animationend', () => el.remove(), { once: true });
}

// ── Static message rendering (greeting, errors) ───────────────────────────

/**
 * Append a complete message bubble to the thread.
 * Used for the greeting and error messages.
 * Streaming bot responses use createStreamBubble / updateStreamBubble instead.
 */
function addMessage(role, content, isError = false) {
  const isUser   = role === 'user';
  const initials = isUser ? 'You' : state.botInitials;
  const time     = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const row    = document.createElement('div');
  row.className = `msg-row ${role}`;
  row.setAttribute('role', 'article');

  const avatar = document.createElement('div');
  avatar.className  = `msg-avatar ${isUser ? 'user-avatar' : 'bot-avatar'}`;
  avatar.textContent = initials;
  avatar.setAttribute('aria-hidden', 'true');

  const bubble = document.createElement('div');
  bubble.className = `bubble ${isUser ? 'user-bubble' : 'bot-bubble'}${isError ? ' bubble-error' : ''}`;
  if (isUser) {
    bubble.textContent = content;   // plain text — no XSS
  } else {
    bubble.innerHTML = toHtml(content);
  }

  // Copy button on bot messages only
  if (!isUser) addCopyButton(bubble);

  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = time;

  const body = document.createElement('div');
  body.className = 'msg-body';
  body.appendChild(bubble);
  body.appendChild(meta);

  row.appendChild(avatar);
  row.appendChild(body);
  $messages.appendChild(row);
  scrollToBottom();
}

// ── Streaming bubble helpers ──────────────────────────────────────────────

/**
 * Create an empty bot bubble row and return the inner bubble element.
 * The caller appends text chunks to it via updateStreamBubble().
 *
 * @returns {HTMLElement} The bubble div (`.bubble.bot-bubble.bubble-streaming`).
 */
function createStreamBubble() {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const row    = document.createElement('div');
  row.className = 'msg-row bot';
  row.setAttribute('role', 'article');

  const avatar = document.createElement('div');
  avatar.className  = 'msg-avatar bot-avatar';
  avatar.textContent = state.botInitials;
  avatar.setAttribute('aria-hidden', 'true');

  // bubble-streaming adds the blinking cursor via CSS ::after
  const bubble = document.createElement('div');
  bubble.className = 'bubble bot-bubble bubble-streaming';

  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = time;

  const body = document.createElement('div');
  body.className = 'msg-body';
  body.appendChild(bubble);
  body.appendChild(meta);

  row.appendChild(avatar);
  row.appendChild(body);
  $messages.appendChild(row);
  scrollToBottom();

  return bubble;
}

/**
 * Re-render the bubble's content with the latest accumulated text.
 * Markdown is re-parsed on every update so formatting is always correct.
 *
 * @param {HTMLElement} bubble   Element returned by createStreamBubble().
 * @param {string}      content  Full accumulated response so far.
 */
function updateStreamBubble(bubble, content) {
  bubble.innerHTML = toHtml(content);
  scrollToBottom();
}

/**
 * Remove the blinking cursor once the stream is complete.
 *
 * @param {HTMLElement} bubble
 */
function finaliseStreamBubble(bubble) {
  bubble.classList.remove('bubble-streaming');
  // Add copy button now that content is complete
  addCopyButton(bubble);
  updateScrollBtn();
}

// ── Scroll ────────────────────────────────────────────────────────────────

/**
 * Scroll the message list to the very bottom after the browser has
 * finished laying out newly appended content.
 *
 * Two nested requestAnimationFrames are used intentionally:
 *   - First rAF: browser commits pending DOM mutations to layout.
 *   - Second rAF: scrollHeight now reflects the fully rendered element,
 *     so the scroll target is accurate.
 * Without this, scrollHeight is measured before the appended element
 * (e.g. the CTA card) has its full height, and the scroll lands short.
 */
function scrollToBottom() {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      $messages.scrollTop = $messages.scrollHeight;
      updateScrollBtn();
    });
  });
}

// ── Typing indicator ──────────────────────────────────────────────────────

function showTyping() {
  $typing.style.display = 'flex';
  scrollToBottom();
}

function hideTyping() {
  $typing.style.display = 'none';
}

// ── Send button ───────────────────────────────────────────────────────────

function syncSendBtn() {
  $sendBtn.disabled = !$input.value.trim() || state.loading;
}

const SEND_ICON = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2.5"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <line x1="12" y1="19" x2="12" y2="5"/>
  <polyline points="5 12 12 5 19 12"/>
</svg>`;

function btnLoading(on) {
  $sendBtn.innerHTML = on
    ? '<span class="spinner" aria-label="Sending…"></span>'
    : SEND_ICON;
}

// ── Core send flow (streaming) ────────────────────────────────────────────

async function sendMessage() {
  const text = $input.value.trim();
  if (!text || state.loading) return;

  // ① Lock UI
  state.loading = true;
  $input.value  = '';
  $input.style.height = 'auto';
  btnLoading(true);
  $sendBtn.disabled = true;

  // ② Dismiss suggestion chips on first real message
  if (!state.firstMessageSent) {
    state.firstMessageSent = true;
    hideSuggestions();
  }

  // ③ Show user message immediately
  addMessage('user', text);

  // ④ Snapshot history before this turn; push user message
  const historySnapshot = [...state.history];
  state.history.push({ role: 'user', content: text });

  showTyping();

  let fullResponse = '';
  let botBubble    = null;   // created on first chunk

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: historySnapshot }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? `HTTP ${res.status}`);
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   sseBuffer = '';
    let   streamFailed = false;

    // ── Read the SSE stream ──────────────────────────────────────────────
    while (true) {
      let done, value;
      try {
        ({ done, value } = await reader.read());
      } catch {
        // Connection dropped mid-stream — fall back to non-streaming
        streamFailed = true;
        break;
      }
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });

      const lines = sseBuffer.split('\n');
      sseBuffer   = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;

        const raw = line.slice(6).trim();
        if (raw === '[DONE]') continue;

        let parsed;
        try { parsed = JSON.parse(raw); }
        catch { continue; }

        // Server-side error (e.g. stream dropped) — fall back silently
        if (parsed.error) { streamFailed = true; break; }

        if (parsed.chunk) {
          fullResponse += parsed.chunk;

          if (!botBubble) {
            hideTyping();
            botBubble = createStreamBubble();
          }

          updateStreamBubble(botBubble, fullResponse);
        }
      }

      if (streamFailed) break;
    }

    // ── Fallback: fetch full response if stream failed ───────────────────
    if (streamFailed && !fullResponse) {
      logger.log?.('Streaming failed — falling back to /api/chat');

      const fallback = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: historySnapshot }),
      });

      if (!fallback.ok) {
        const err = await fallback.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${fallback.status}`);
      }

      const data = await fallback.json();
      fullResponse = data.response;

      hideTyping();
      if (!botBubble) botBubble = createStreamBubble();
      updateStreamBubble(botBubble, fullResponse);
    }

    // ── Stream finished ──────────────────────────────────────────────────
    if (botBubble) finaliseStreamBubble(botBubble);

    if (fullResponse) {
      state.history.push({ role: 'assistant', content: fullResponse });

      // Show the email CTA after the 3rd real bot response
      state.botResponseCount++;
      if (state.botResponseCount === 3 && !state.ctaShown) {
        state.ctaShown = true;
        setTimeout(() => showContactCTA(), 900);
      }
    }

  } catch (err) {
    hideTyping();
    if (botBubble) {
      // Partial response arrived before the error — mark it as failed
      botBubble.classList.remove('bubble-streaming');
      botBubble.classList.add('bubble-error');
    } else {
      addMessage('bot', `Something went wrong — please try again.\n\n_${err.message}_`, true);
    }
    // Roll back the failed user turn so history stays consistent
    state.history.pop();

  } finally {
    state.loading = false;
    btnLoading(false);
    syncSendBtn();
    $input.focus();
  }
}

// ── Email capture CTA ─────────────────────────────────────────────────────

/**
 * Inject the contact CTA card into the message list.
 * Triggered after the 3rd real bot response.
 */
function showContactCTA() {
  if (document.getElementById('cta-card')) return; // guard against duplicates

  const ownerFirst = state.ownerName.split(' ')[0] || 'the owner';

  const card = document.createElement('div');
  card.id        = 'cta-card';
  card.className = 'cta-card';
  card.setAttribute('role', 'complementary');
  card.setAttribute('aria-label', 'Get in touch');

  card.innerHTML = `
    <button class="cta-dismiss" id="cta-dismiss" aria-label="Dismiss">
      ${iconClose()}
    </button>
    <div class="cta-icon-wrap" aria-hidden="true">${iconEnvelope()}</div>
    <p class="cta-title">Enjoyed the conversation?</p>
    <p class="cta-sub">
      Leave your details and ${escapeHtml(ownerFirst)} will get back to you.
    </p>
    <input
      type="text"
      id="cta-name"
      class="cta-input"
      placeholder="Your name"
      value="${escapeHtml(state.userName)}"
      maxlength="100"
      autocomplete="name"
    />
    <input
      type="email"
      id="cta-email"
      class="cta-input"
      placeholder="your@email.com"
      maxlength="200"
      autocomplete="email"
    />
    <button class="cta-submit-btn" id="cta-submit-btn">
      Send message
      ${iconArrowRight()}
    </button>
  `;

  $messages.appendChild(card);
  // CTA card is taller than a message bubble; give the browser an extra
  // 50 ms beyond the two rAFs so its full height is in the layout before
  // we measure scrollHeight.
  setTimeout(scrollToBottom, 50);

  // Dismiss
  document.getElementById('cta-dismiss').addEventListener('click', () => {
    card.classList.add('cta-card--hiding');
    card.addEventListener('animationend', () => card.remove(), { once: true });
  });

  // Submit on button click or Enter in the email field
  const submit = () => submitCTA(card, ownerFirst);
  document.getElementById('cta-submit-btn').addEventListener('click', submit);
  document.getElementById('cta-email').addEventListener('keydown', e => {
    if (e.key === 'Enter') submit();
  });
  document.getElementById('cta-name').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('cta-email').focus();
  });
}

/**
 * Validate the CTA form, POST to /api/contact, and show the success state.
 *
 * @param {HTMLElement} card       The CTA card element.
 * @param {string}      ownerFirst The owner's first name for the success message.
 */
async function submitCTA(card, ownerFirst) {
  const $name   = document.getElementById('cta-name');
  const $email  = document.getElementById('cta-email');
  const $submit = document.getElementById('cta-submit-btn');

  const name  = $name.value.trim();
  const email = $email.value.trim();

  // Clear previous error states
  $name.classList.remove('cta-input--error');
  $email.classList.remove('cta-input--error');

  // Client-side validation
  let valid = true;
  if (!name)                { $name.classList.add('cta-input--error');  $name.focus();  valid = false; }
  if (!isValidEmail(email)) { $email.classList.add('cta-input--error'); if (valid) $email.focus(); valid = false; }
  if (!valid) return;

  // Build a short conversation context snippet for the push notification
  const snippet = state.history
    .filter(m => m.role === 'user')
    .slice(-3)
    .map(m => m.content.slice(0, 80).replace(/\n/g, ' '))
    .join(' | ');
  const notes = snippet ? `Asked about: ${snippet}` : 'Via website chat';

  // Loading state
  $submit.disabled  = true;
  $submit.innerHTML = '<span class="spinner"></span>';

  try {
    const res = await fetch('/api/contact', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ name, email, notes }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? `HTTP ${res.status}`);
    }

    // ── Success state ────────────────────────────────────────────────────
    card.innerHTML = `
      <div class="cta-success">
        <div class="cta-success-icon">${iconCheckCircle()}</div>
        <div>
          <p class="cta-success-title">Message sent!</p>
          <p class="cta-success-sub">
            ${escapeHtml(ownerFirst)} will be in touch with you soon.
          </p>
        </div>
      </div>
    `;
    scrollToBottom();

  } catch {
    // Restore the button so the user can retry
    $submit.disabled  = false;
    $submit.innerHTML = `Send message ${iconArrowRight()}`;
    $email.classList.add('cta-input--error');
  }
}

/** Basic email format check. */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ── Textarea auto-grow ────────────────────────────────────────────────────

function autoGrow() {
  $input.style.height = 'auto';
  $input.style.height = `${Math.min($input.scrollHeight, 120)}px`;
  syncSendBtn();
}

// ── Event listeners ───────────────────────────────────────────────────────

$input.addEventListener('input',   autoGrow);
$input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
$sendBtn.addEventListener('click', sendMessage);

// ── SVG icons ─────────────────────────────────────────────────────────────

function iconLinkedIn() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z"/>
    <rect x="2" y="9" width="4" height="12"/>
    <circle cx="4" cy="4" r="2"/>
  </svg>`;
}

function iconGitHub() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483
    0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466
    -.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832
    .092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688
    -.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59
    0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028
    1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012
    2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/>
  </svg>`;
}

function iconEmail() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
    <polyline points="22,6 12,13 2,6"/>
  </svg>`;
}

function iconCopy() {
  return `<svg width="13" height="13" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="9" y="9" width="13" height="13" rx="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>`;
}

function iconCheck() {
  return `<svg width="13" height="13" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12"/>
  </svg>`;
}

function iconMoon() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>`;
}

function iconSun() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/>
    <line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>`;
}

function iconEnvelope() {
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
    <polyline points="22,6 12,13 2,6"/>
  </svg>`;
}

function iconClose() {
  return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6"  y1="6" x2="18" y2="18"/>
  </svg>`;
}

function iconArrowRight() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <line x1="5" y1="12" x2="19" y2="12"/>
    <polyline points="12 5 19 12 12 19"/>
  </svg>`;
}

function iconCheckCircle() {
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12"/>
  </svg>`;
}

// ── Init ──────────────────────────────────────────────────────────────────

document.getElementById('theme-toggle').addEventListener('click', toggleDarkMode);

initDarkMode();
loadProfile();