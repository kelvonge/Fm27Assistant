// Petite boîte à outils d'interface : éléments, formats, tableaux, radars, courbes, terrain.
export function h(tag, props, ...children) {
  const el = tag === 'svg' || props?.svg ? document.createElementNS('http://www.w3.org/2000/svg', tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false || k === 'svg') continue;
    if (k === 'class') el.setAttribute('class', v);
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k in el && !(el instanceof SVGElement)) el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const s = (tag, props, ...ch) => h(tag, { ...props, svg: true }, ...ch);

const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export const fmt = {
  money(v) {
    if (v == null) return '—';
    const a = Math.abs(v); let t;
    if (a >= 1e9) t = (v / 1e9).toFixed(2).replace(/\.?0+$/, '') + ' Md';
    else if (a >= 1e6) t = (v / 1e6).toFixed(1).replace(/\.0$/, '') + ' M';
    else if (a >= 1e3) t = Math.round(v / 1e3) + ' k';
    else t = String(Math.round(v));
    return t.replace('.', ',') + ' €';
  },
  wage(v) { return v == null ? '—' : fmt.money(v) + '/sem.'; },
  date(iso) { if (!iso) return '—'; const [y, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; },
  shortDate(iso) { if (!iso) return '—'; const [y, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]}`; },
  num(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d).replace('.', ','); },
  ord(n) { return n == null ? '—' : n === 1 ? '1er' : `${n}e`; },
};
export const noteClass = (n) => n == null ? 'n0' : n >= 15 ? 'n5' : n >= 13 ? 'n4' : n >= 11 ? 'n3' : n >= 9 ? 'n2' : 'n1';
export const attrClass = (v) => v == null ? 'a0' : v >= 16 ? 'a5' : v >= 13 ? 'a4' : v >= 10 ? 'a3' : v >= 7 ? 'a2' : 'a1';
export function noteBadge(n, opts = {}) {
  const el = h('span', { class: `note ${noteClass(n)} ${opts.est ? 'est' : ''}`, title: opts.title || (opts.est ? 'Estimation (attributs non lus ou incomplets)' : 'Note sur 20 dans son meilleur rôle') }, n == null ? '?' : fmt.num(n));
  return el;
}
export function playerNote(p) {
  const a = p.analyse || {};
  if (a.note == null) return noteBadge(null, { title: 'Non évalué : attributs non lus' });
  if (a.source === 'etoiles') return noteBadge(a.note, { est: true, title: 'Estimation d\'après les étoiles : ouvrez le profil dans FM pour une vraie note' });
  return noteBadge(a.note, { est: !a.fiable, title: a.fiable ? `Meilleur rôle : ${a.role_nom}` : `Note partielle (${Math.round(a.couverture * 100)} % des attributs du rôle lus)` });
}
export function stars(n) {
  if (n == null) return h('span', { class: 'faint' }, '—');
  // Rangée grise de 5 étoiles + rangée dorée par-dessus, coupée à la bonne largeur (gère les demi-étoiles)
  return h('span', { class: 'stars', title: `${String(n).replace('.', ',')} étoile(s) sur 5` }, '★★★★★', h('b', { style: { width: `${n / 5 * 100}%` } }, '★★★★★'));
}
export function tag(text, cls = '') { return h('span', { class: `tag ${cls}` }, text); }
export function empty(icon, title, text, ...actions) {
  return h('div', { class: 'empty' }, h('div', { class: 'big' }, icon), h('h3', {}, title), h('p', {}, text), h('div', { class: 'row', style: { justifyContent: 'center' } }, actions));
}
export function toast(msg, err = false) {
  const t = h('div', { class: `toast ${err ? 'err' : ''}` }, msg);
  document.getElementById('toasts').append(t);
  setTimeout(() => { t.style.transition = 'opacity .3s'; t.style.opacity = 0; setTimeout(() => t.remove(), 320); }, err ? 6000 : 3200);
}
export function initials(name) { return (name || '?').split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase(); }

// ---- Tableau triable. columns : {key, label, align, render(row), value(row), sortable}
export function dataTable({ columns, rows, onRow, sort, dir = -1, maxHeight, emptyText = 'Aucune ligne.' }) {
  const state = { sort, dir };
  const wrap = h('div', { class: 'table-wrap', style: maxHeight ? { maxHeight } : {} });
  const val = (col, r) => col.value ? col.value(r) : r[col.key];
  function draw() {
    let data = rows.slice();
    const col = columns.find(c => c.key === state.sort);
    if (col) data.sort((a, b) => {
      const x = val(col, a), y = val(col, b);
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      return (typeof x === 'string' ? x.localeCompare(y, 'fr') : x - y) * state.dir;
    });
    const thead = h('thead', {}, h('tr', {}, columns.map(c => h('th', {
      class: `${c.align || ''} ${c.sortable === false ? '' : 'sortable'} ${state.sort === c.key ? 'sorted' : ''}`, title: c.title,
      onclick: c.sortable === false ? null : () => { if (state.sort === c.key) state.dir *= -1; else { state.sort = c.key; state.dir = c.asc ? 1 : -1; } draw(); },
    }, c.label, state.sort === c.key ? (state.dir > 0 ? ' ▲' : ' ▼') : ''))));
    const tbody = h('tbody', {}, data.map(r => h('tr', { class: onRow ? 'click' : '', onclick: onRow ? (e) => { if (!e.target.closest('input,button,select,a')) onRow(r); } : null },
      columns.map(c => h('td', { class: c.align || '' }, c.render ? c.render(r) : (r[c.key] ?? '—'))))));
    wrap.replaceChildren(data.length ? h('table', { class: 'data' }, thead, tbody) : h('div', { class: 'empty' }, emptyText));
  }
  draw();
  return wrap;
}

// ---- Radar. series : [{name, color, axes:[{axe, val}]}], valeurs sur 20
export const PALETTE = ['var(--accent)', '#4ea3f2', '#f2c14e', '#ef5a52'];
export function radarChart(series, size = 300) {
  const axes = series[0]?.axes || [];
  const n = axes.length, c = size / 2, R = size / 2 - 62;
  const pt = (i, v) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [c + Math.cos(a) * R * v / 20, c + Math.sin(a) * R * v / 20]; };
  const svg = s('svg', { viewBox: `0 0 ${size} ${size}`, width: '100%', style: { maxWidth: size + 'px', display: 'block', margin: '0 auto', overflow: 'visible' } });
  for (const lvl of [5, 10, 15, 20]) svg.append(s('polygon', { points: axes.map((_, i) => pt(i, lvl).join(',')).join(' '), fill: 'none', stroke: 'var(--line)', 'stroke-width': lvl === 20 ? 1.2 : .7 }));
  axes.forEach((ax, i) => {
    const [x, y] = pt(i, 20), [lx, ly] = pt(i, 23.5);
    svg.append(s('line', { x1: c, y1: c, x2: x, y2: y, stroke: 'var(--line)', 'stroke-width': .7 }));
    svg.append(s('text', { x: lx, y: ly, 'text-anchor': Math.abs(lx - c) < 8 ? 'middle' : lx > c ? 'start' : 'end', 'dominant-baseline': 'middle', fill: 'var(--muted)', 'font-size': 11 }, ax.axe));
  });
  series.forEach((sr, k) => {
    const color = sr.color || PALETTE[k % PALETTE.length];
    const pts = sr.axes.map((ax, i) => pt(i, ax.val ?? 0));
    const poly = s('polygon', { points: pts.map(p => p.join(',')).join(' '), fill: color, 'fill-opacity': series.length > 1 ? .13 : .22, stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round' });
    poly.animate([{ transform: 'scale(.6)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], { duration: 420, easing: 'cubic-bezier(.2,.7,.2,1)' });
    poly.style.transformOrigin = `${c}px ${c}px`;
    svg.append(poly);
    pts.forEach((p, i) => svg.append(s('circle', { cx: p[0], cy: p[1], r: 3, fill: color }, s('title', {}, `${sr.name ? sr.name + ' – ' : ''}${sr.axes[i].axe} : ${sr.axes[i].val ?? 'non lu'}`))));
  });
  return svg;
}

// ---- Courbe d'évolution. series : [{name, color, points:[{x, y}]}]
export function lineChart(series, { height = 190, format = (v) => fmt.num(v) } = {}) {
  const W = 620, H = height, pad = { l: 46, r: 14, t: 12, b: 26 };
  const all = series.flatMap(sr => sr.points.filter(p => p.y != null).map(p => p.y));
  if (all.length < 2) return h('div', { class: 'muted small' }, 'Pas encore assez de dates de jeu lues pour tracer une évolution.');
  let lo = Math.min(...all), hi = Math.max(...all);
  if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
  const m = (hi - lo) * 0.12; lo -= m; hi += m;
  const xs = [...new Set(series.flatMap(sr => sr.points.map(p => p.x)))].sort();
  const X = (x) => pad.l + (xs.length === 1 ? 0.5 : xs.indexOf(x) / (xs.length - 1)) * (W - pad.l - pad.r);
  const Y = (y) => pad.t + (1 - (y - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', style: { display: 'block' } });
  for (let i = 0; i <= 3; i++) {
    const v = lo + (hi - lo) * i / 3;
    svg.append(s('line', { x1: pad.l, x2: W - pad.r, y1: Y(v), y2: Y(v), stroke: 'var(--line-soft)' }));
    svg.append(s('text', { x: pad.l - 8, y: Y(v), 'text-anchor': 'end', 'dominant-baseline': 'middle', fill: 'var(--faint)', 'font-size': 10 }, format(v)));
  }
  const step = Math.ceil(xs.length / 6);
  xs.forEach((x, i) => { if (i % step === 0 || i === xs.length - 1) svg.append(s('text', { x: X(x), y: H - 8, 'text-anchor': 'middle', fill: 'var(--faint)', 'font-size': 10 }, fmt.shortDate(x))); });
  series.forEach((sr, k) => {
    const color = sr.color || PALETTE[k % PALETTE.length];
    const pts = sr.points.filter(p => p.y != null);
    if (!pts.length) return;
    const path = s('path', { d: pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.x)},${Y(p.y)}`).join(' '), fill: 'none', stroke: color, 'stroke-width': 2.2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' });
    svg.append(path);
    try { const len = path.getTotalLength?.() || 800; path.style.strokeDasharray = len; path.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 700, easing: 'ease-out' }); } catch (e) { /* animation facultative */ }
    pts.forEach(p => svg.append(s('circle', { cx: X(p.x), cy: Y(p.y), r: 3.4, fill: 'var(--panel)', stroke: color, 'stroke-width': 2 }, s('title', {}, `${sr.name} – ${fmt.date(p.x)} : ${format(p.y)}`))));
  });
  const legend = series.length > 1 ? h('div', { class: 'legend' }, series.map((sr, k) => h('span', {}, h('i', { style: { background: sr.color || PALETTE[k % PALETTE.length] } }), sr.name))) : null;
  return h('div', {}, svg, legend);
}

// ---- Terrain interactif. xi.postes : [{x, y, joueur, role_nom, note, hors_poste, label}]
export function pitch(xi, onSlot) {
  const el = h('div', { class: 'pitch' });
  el.append(s('svg', { class: 'lines', viewBox: '0 0 68 88', preserveAspectRatio: 'none' },
    s('g', { fill: 'none', stroke: 'rgba(255,255,255,.28)', 'stroke-width': .25 },
      s('rect', { x: 2, y: 2, width: 64, height: 84 }), s('line', { x1: 2, y1: 44, x2: 66, y2: 44 }), s('circle', { cx: 34, cy: 44, r: 7.5 }),
      s('rect', { x: 17, y: 2, width: 34, height: 13 }), s('rect', { x: 26, y: 2, width: 16, height: 5 }),
      s('rect', { x: 17, y: 73, width: 34, height: 13 }), s('rect', { x: 26, y: 81, width: 16, height: 5 }))));
  for (const p of xi.postes) {
    const top = 96 - p.y * 0.92, left = 6 + p.x * 0.88;
    const slot = h('div', { class: `slot ${p.hors_poste ? 'out' : ''} ${p.joueur ? '' : 'vide'}`, style: { left: left + '%', top: top + '%' },
      title: p.joueur ? `${p.joueur.name} – ${p.role_nom} (${fmt.num(p.note)}/20)${p.hors_poste ? ' – hors de son poste naturel' : ''}\n${p.raison || ''}` : 'Aucun joueur évalué pour ce poste',
      onclick: () => onSlot && onSlot(p) },
      h('div', { class: 'badge' }, p.joueur ? fmt.num(p.note) : '?'),
      h('div', { class: 'nm' }, p.joueur ? p.joueur.name : p.label),
      h('div', { class: 'rl' }, p.joueur ? p.role_nom : 'poste à pourvoir'));
    el.append(slot);
  }
  return el;
}

export function tabs(items, active, onChange) {
  const el = h('div', { class: 'tabs' });
  const draw = (cur) => el.replaceChildren(...items.map(([id, label]) => h('button', { class: `tab ${id === cur ? 'active' : ''}`, onclick: () => { draw(id); onChange(id); } }, label)));
  draw(active);
  return el;
}
export function openModal(...content) {
  const m = document.getElementById('modal');
  const close = () => { m.hidden = true; m.replaceChildren(); };
  m.replaceChildren(h('div', { class: 'veil', onclick: close }), h('div', { class: 'box' }, h('button', { class: 'btn ghost icon close-x', onclick: close, title: 'Fermer' }, '✕'), content));
  m.hidden = false;
  return close;
}
export function kpi(label, value, sub) { return h('div', { class: 'card kpi' }, h('div', { class: 'label' }, label), h('div', { class: 'value' }, value), sub ? h('div', { class: 'sub' }, sub) : null); }
export function skeleton(n = 3) { return h('div', { class: 'grid g3' }, Array.from({ length: n }, () => h('div', { class: 'skeleton' }))); }
