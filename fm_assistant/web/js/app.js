// Coquille de l'application : navigation, statut en direct, recherche globale, thème.
import { api } from './api.js';
import { h, toast, openModal, tag } from './ui.js';
import { openPlayer, closePlayer } from './player.js';

const ICON = {
  dashboard: 'M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z', lecture: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 100 6 3 3 0 000-6z',
  effectif: 'M17 21v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2M10 11a4 4 0 100-8 4 4 0 000 8zM21 21v-2a4 4 0 00-3-3.9M16 3.1a4 4 0 010 7.8',
  tactique: 'M4 3h16v18H4zM4 12h16M12 9.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5z', recrutement: 'M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-4.3-4.3',
  jeunes: 'M12 3l9 5-9 5-9-5 9-5zM7 11v5c0 1.5 2.2 3 5 3s5-1.5 5-3v-5', contrats: 'M14 3H6v18h12V7zM14 3v4h4M9 13h6M9 17h6',
  idees: 'M9 18h6M10 21h4M12 3a6 6 0 00-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.800 1-2.5A6 6 0 0012 3z', chat: 'M21 12a8 8 0 01-11.6 7.100L4 20l1-4.500A8 8 0 1121 12z',
  reglages: 'M12 9a3 3 0 100 6 3 3 0 000-6zM19 12l2-1-1-3-2 .5-1.500-1.500.500-2-3-1-1 2h-2L10 3 7 4l.5 2L6 7.500 4 7 3 10l2 1v2l-2 1 1 3 2-.500L7.500 18.500 7 20.500l3 1 1-2h2l1 2 3-1-.500-2 1.500-1.500 2 .500 1-3-2-1z',
};
const ROUTES = [
  { id: 'dashboard', label: 'Tableau de bord' }, { id: 'lecture', label: 'Lecture en direct' }, { sep: true },
  { id: 'effectif', label: 'Effectif' }, { id: 'tactique', label: 'Assistant tactique' }, { id: 'recrutement', label: 'Recrutement' },
  { id: 'jeunes', label: 'Jeunes' }, { id: 'contrats', label: 'Contrats & finances' }, { sep: true },
  { id: 'idees', label: 'Idées de carrière' }, { id: 'chat', label: 'Chat local', hidden: true }, { id: 'reglages', label: 'Réglages' },
];
const view = document.getElementById('view');
const state = { status: null, settings: null, page: null, module: null, lectures: -1, chat: false };

export function navigate(id, params = {}) {
  const q = new URLSearchParams(params).toString();
  location.hash = `#/${id}${q ? '?' + q : ''}`;
}
function current() {
  const [path, q] = location.hash.replace(/^#\/?/, '').split('?');
  return { id: ROUTES.some(r => r.id === path) ? path : 'dashboard', params: Object.fromEntries(new URLSearchParams(q || '')) };
}
function drawNav() {
  const cur = current().id;
  document.getElementById('nav').replaceChildren(...ROUTES.filter(r => !r.hidden || (r.id === 'chat' && state.chat)).map(r => r.sep ? h('div', { class: 'nav-sep' }) :
    h('a', { class: `nav-item ${r.id === cur ? 'active' : ''}`, href: `#/${r.id}` },
      h('svg', { viewBox: '0 0 24 24' }, h('path', { svg: true, d: ICON[r.id] })), r.label)));
}
async function render(keepScroll = false) {
  const { id, params } = current();
  const route = ROUTES.find(r => r.id === id);
  document.getElementById('page-title').textContent = route.label;
  drawNav();
  const top = keepScroll ? view.scrollTop : 0;
  try {
    const mod = await import(`./pages/${id}.js`);
    state.module = mod; state.page = id;
    const root = h('div', { class: keepScroll ? '' : 'page' });
    await mod.render(root, { params, navigate, status: state.status, settings: state.settings, refresh: () => render(true), setSettings });
    if (current().id !== id) return;  // l'utilisateur a changé de page pendant le chargement
    view.replaceChildren(root);
    view.scrollTop = top;
  } catch (e) {
    console.error(e);
    view.replaceChildren(h('div', { class: 'card' }, h('h3', {}, 'Cette page n\'a pas pu s\'afficher'), h('p', { class: 'muted' }, e.message), h('button', { class: 'btn', onclick: () => render() }, 'Réessayer')));
  }
}
function ink(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || ''); if (!m) return '#04130c';
  const n = parseInt(m[1], 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? '#06100c' : '#ffffff';
}
export function applySettings(s) {
  state.settings = s;
  if (s.accent) { document.documentElement.style.setProperty('--accent', s.accent); document.documentElement.style.setProperty('--accent-ink', ink(s.accent)); }
  document.getElementById('brand-club').textContent = s.club || 'Club non renseigné';
  document.getElementById('brand-mark').textContent = (s.club || 'FM').split(/\s+/).map(w => w[0]).slice(0, 3).join('').toUpperCase();
}
async function setSettings(patch) { applySettings(await api.put('/api/settings', patch)); }

async function poll() {
  try {
    const s = await api.get('/api/status');
    state.status = s;
    const dot = document.getElementById('live-dot');
    dot.className = 'dot ' + ({ actif: 'on', arriere_plan: 'wait', absent: 'off', pause: 'wait', indisponible: 'off', arret: 'off' }[s.etat] || 'off') + (s.erreur && s.etat !== 'indisponible' ? ' err' : '');
    document.getElementById('live-text').textContent = s.demo && s.etat !== 'actif' ? `Mode démonstration – ${s.message}` : s.message;
    const gd = document.getElementById('game-date');
    gd.hidden = !s.date_jeu; if (s.date_jeu) gd.textContent = `Date de jeu : ${s.date_jeu.split('-').reverse().join('/')}`;
    const ov = document.getElementById('btn-overlay');
    ov.hidden = !s.overlay.disponible; ov.classList.toggle('on', s.overlay.ouvert);
    document.dispatchEvent(new CustomEvent('fma:status', { detail: s }));
    if (state.lectures >= 0 && s.lectures !== state.lectures && state.module?.live && document.getElementById('drawer').hidden
        && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) render(true);  // nouvelle lecture → page à jour
    state.lectures = s.lectures;
  } catch (e) { document.getElementById('live-text').textContent = e.message; document.getElementById('live-dot').className = 'dot err'; }
}

// ---- Recherche globale
const search = document.getElementById('search'), results = document.getElementById('search-results');
let timer, sel = -1, items = [];
function pick(r) {
  results.hidden = true; search.value = '';
  if (r.type === 'joueur') openPlayer(r.id);
  else if (r.type === 'defi') navigate('idees', { d: r.id });
  else if (r.type === 'role') api.get('/api/knowledge').then(k => {
    const role = k.roles.find(x => x.id === r.id);
    openModal(h('h2', { style: { marginTop: 0 } }, role.nom), h('p', { class: 'muted' }, role.description),
      h('p', {}, h('b', {}, 'Postes : '), role.postes.map(p => k.postes.find(x => x.id === p)?.label || p).join(', ')),
      h('p', {}, h('b', {}, 'Attributs clés : '), role.cles.join(', ')), h('p', {}, h('b', {}, 'Attributs secondaires : '), role.secondaires.join(', ')),
      h('p', { class: 'small faint' }, 'Les rôles et leurs poids sont modifiables dans connaissances.json (Réglages → Dossier de données).'));
  });
}
function drawResults() {
  results.replaceChildren(...(items.length ? items.map((r, i) => h('div', { class: `search-item ${i === sel ? 'sel' : ''}`, onmousedown: (e) => { e.preventDefault(); pick(r); } },
    h('span', { class: 'search-type' }, { joueur: 'Joueur', role: 'Rôle', defi: 'Défi' }[r.type]), h('b', {}, r.titre), h('small', {}, r.sous_titre))) : [h('div', { class: 'search-item muted' }, 'Aucun résultat dans les données lues.')]));
  results.hidden = false;
}
search.addEventListener('input', () => { clearTimeout(timer); const q = search.value.trim(); if (q.length < 2) { results.hidden = true; return; }
  timer = setTimeout(async () => { try { items = (await api.get('/api/search?q=' + encodeURIComponent(q))).resultats; sel = items.length ? 0 : -1; drawResults(); } catch (e) { /* silencieux */ } }, 130); });
search.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown') { sel = Math.min(items.length - 1, sel + 1); drawResults(); e.preventDefault(); }
  else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); drawResults(); e.preventDefault(); }
  else if (e.key === 'Enter' && items[sel]) pick(items[sel]);
  else if (e.key === 'Escape') { results.hidden = true; search.blur(); }
});
search.addEventListener('blur', () => setTimeout(() => { results.hidden = true; }, 120));
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); search.focus(); }
  if (e.key === 'Escape') { closePlayer(); const m = document.getElementById('modal'); m.hidden = true; m.replaceChildren(); }
});
document.getElementById('live-pill').onclick = () => navigate('lecture');
document.getElementById('btn-overlay').onclick = async () => { try { const r = await api.post('/api/overlay/toggle'); toast(r.ouvert ? 'Overlay affiché par-dessus le jeu (déplaçable à la souris)' : 'Overlay fermé'); poll(); } catch (e) { toast(e.message, true); } };
document.getElementById('btn-theme').onclick = () => { const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = t; try { localStorage.setItem('fma-theme', t); } catch (e) { /* stockage indisponible */ } };
try { const t = localStorage.getItem('fma-theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* stockage indisponible */ }
document.addEventListener('fma:refresh', () => render(true));
window.addEventListener('hashchange', () => render());

(async function start() {
  try {
    applySettings(await api.get('/api/settings'));
    await poll();
    api.get('/api/chat/status').then(c => { state.chat = c.disponible; drawNav(); }).catch(() => {});
    const empty = state.status && state.status.compteurs.effectif === 0;
    if (state.settings.premier_lancement && empty && !location.hash) location.hash = '#/lecture';
  } catch (e) { toast(e.message, true); }
  await render();
  setInterval(poll, 2000);
})();
