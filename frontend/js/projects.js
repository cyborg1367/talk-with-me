'use strict';

// ── Dark mode (shared with chat.js) ───────────────────────────────────────

function initDarkMode() {
  const saved       = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved ? saved === 'dark' : prefersDark);
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
  btn.innerHTML = isDark ? iconSun() : iconMoon();
  btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
}

// ── Icons ─────────────────────────────────────────────────────────────────

function iconMoon() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>`;
}

function iconSun() {
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>`;
}

function iconExternal() {
  return `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
    <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
  </svg>`;
}

function iconGitHub() {
  return `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
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

// ── Escape HTML ───────────────────────────────────────────────────────────

function escapeHtml(str) {
  const el = document.createElement('div');
  el.appendChild(document.createTextNode(str || ''));
  return el.innerHTML;
}

// ── Render a single project card ──────────────────────────────────────────

function renderCard(project, index) {
  const card = document.createElement('div');
  card.className = 'project-card';
  card.style.animationDelay = `${index * 0.07}s`;

  // Badges (demo + github)
  let badges = '';
  if (project.demo) {
    badges += `
      <a href="${escapeHtml(project.demo)}" target="_blank" rel="noopener noreferrer"
         class="project-badge-demo" aria-label="Live demo">
        ${iconExternal()} Live
      </a>`;
  }
  if (project.url && !project.private) {
    badges += `
      <a href="${escapeHtml(project.url)}" target="_blank" rel="noopener noreferrer"
         class="project-badge-github" aria-label="GitHub repository">
        ${iconGitHub()} GitHub
      </a>`;
  }

  // Tech tags
  const techTags = (project.tech || [])
    .map(t => `<span class="project-tech-tag">${escapeHtml(t)}</span>`)
    .join('');

  // Highlights (max 3 shown)
  let highlightsHtml = '';
  const highlights = (project.highlights || []).slice(0, 3);
  if (highlights.length) {
    const items = highlights
      .map(h => `<li>${escapeHtml(h)}</li>`)
      .join('');
    highlightsHtml = `
      <div class="project-highlights">
        <p class="project-highlights-title">Highlights</p>
        <ul class="project-highlights-list">${items}</ul>
      </div>`;
  }

  card.innerHTML = `
    <div class="project-card-accent"></div>
    <div class="project-card-body">
      <div class="project-card-header">
        <h2 class="project-card-name">${escapeHtml(project.name)}</h2>
        <div class="project-card-badges">${badges}</div>
      </div>
      ${project.description
        ? `<p class="project-card-desc">${escapeHtml(project.description)}</p>`
        : ''}
      ${techTags
        ? `<div class="project-tech-list">${techTags}</div>`
        : ''}
      ${highlightsHtml}
    </div>
  `;

  return card;
}

// ── Load and render all projects ──────────────────────────────────────────

async function loadProjects() {
  const $grid = document.getElementById('projects-grid');

  try {
    const res = await fetch('/api/projects');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const projects = await res.json();

    // Clear skeletons
    $grid.innerHTML = '';

    if (!projects.length) {
      $grid.innerHTML = '<p style="color:var(--text-faint);grid-column:1/-1;text-align:center;padding:40px">No projects found.</p>';
      return;
    }

    projects.forEach((p, i) => {
      $grid.appendChild(renderCard(p, i));
    });

  } catch (err) {
    console.error('Failed to load projects:', err);
    $grid.innerHTML = `
      <p style="color:var(--text-faint);grid-column:1/-1;text-align:center;padding:40px">
        Failed to load projects — please refresh.
      </p>`;
  }
}

// ── Load profile for header ───────────────────────────────────────────────

async function loadHeader() {
  try {
    const res = await fetch('/api/profile');
    if (!res.ok) return;
    const p = await res.json();
    document.getElementById('hdr-initials').textContent = p.initials || 'MA';
    document.getElementById('hdr-name').textContent     = p.name    || '';
    document.getElementById('hdr-tagline').textContent  = p.tagline || '';
    document.getElementById('hero-title').textContent   = `${p.name?.split(' ')[0] || ''}'s Projects`;
    document.title = `${p.name} — Projects`;
  } catch {}
}

// ── Init ──────────────────────────────────────────────────────────────────

document.getElementById('theme-toggle').addEventListener('click', toggleDarkMode);

initDarkMode();
loadHeader();
loadProjects();