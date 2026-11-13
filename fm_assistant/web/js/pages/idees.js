import { api } from '../api.js';
import { h, tag, openModal, toast, empty } from '../ui.js';

let memo = { diff: 0, duree: '', style: '' };
const DUREE = { courte: 'Courte (1-3 saisons)', moyenne: 'Moyenne (4-8 saisons)', longue: 'Longue (9+ saisons)' };
const diff = (n) => h('span', { class: 'diff', title: `Difficulté ${n}/5` }, '●'.repeat(n), h('i', {}, '●'.repeat(5 - n)));

export async function render(root, ctx) {
  const { defis, avertissement } = await api.get('/api/ideas');
  const styles = [...new Set(defis.map(d => d.style))].sort();
  const detail = (d) => openModal(
    h('div', { class: 'row' }, diff(d.difficulte), tag(DUREE[d.duree] || d.duree), tag(d.style, 'info')),
    h('h2', { style: { fontSize: '24px', margin: '10px 0 6px' } }, d.titre), h('p', { class: 'muted', style: { fontSize: '15px' } }, d.pitch),
    h('div', { class: 'grid g3', style: { marginTop: '14px' } },
      h('div', {}, h('h3', {}, 'Objectifs'), h('ul', { class: 'clean' }, d.objectifs.map(x => h('li', {}, x)))),
      h('div', {}, h('h3', {}, 'Règles'), h('ul', { class: 'clean' }, d.regles.map(x => h('li', {}, x)))),
      h('div', {}, h('h3', {}, 'Clubs conseillés'), h('ul', { class: 'clean' }, d.clubs.map(x => h('li', {}, x))))),
    h('div', { class: 'row', style: { marginTop: '18px' } },
      h('button', { class: 'btn', onclick: async () => { await ctx.setSettings({ objectif: `Défi « ${d.titre} » : ${d.objectifs[0]}` }); toast('Défi adopté : il apparaît comme objectif sur le tableau de bord.'); } }, 'Adopter ce défi'),
      h('button', { class: 'btn ghost', onclick: surprise }, 'Un autre au hasard')));
  async function surprise() { const pool = filtered(); if (!pool.length) return toast('Aucun défi ne correspond aux filtres.', true); detail(pool[Math.floor(Math.random() * pool.length)]); }
  const filtered = () => defis.filter(d => (!memo.diff || d.difficulte === memo.diff) && (!memo.duree || d.duree === memo.duree) && (!memo.style || d.style === memo.style));
  const grid = h('div', { class: 'grid g3' });
  const bar = h('div', { class: 'toolbar' });
  const draw = () => {
    const chip = (label, on, fn) => h('span', { class: `chip click ${on ? 'on' : ''}`, onclick: () => { fn(); draw(); } }, label);
    bar.replaceChildren(h('button', { class: 'btn', onclick: surprise }, '🎲 Surprends-moi'),
      h('span', { class: 'muted small' }, 'Difficulté'), ...[1, 2, 3, 4, 5].map(n => chip(String(n), memo.diff === n, () => { memo.diff = memo.diff === n ? 0 : n; })),
      h('span', { class: 'muted small' }, 'Durée'), ...Object.keys(DUREE).map(k => chip(k, memo.duree === k, () => { memo.duree = memo.duree === k ? '' : k; })),
      h('span', { class: 'muted small' }, 'Style'), ...styles.map(s => chip(s, memo.style === s, () => { memo.style = memo.style === s ? '' : s; })));
    const list = filtered();
    grid.replaceChildren(...(list.length ? list.map(d => h('div', { class: 'card idea', onclick: () => detail(d) },
      h('div', { class: 'row' }, diff(d.difficulte), h('span', { class: 'spacer' }), tag(d.duree), tag(d.style, 'info')),
      h('h3', { style: { fontSize: '17px', margin: 0 } }, d.titre), h('div', { class: 'muted' }, d.pitch),
      h('div', { class: 'small faint' }, d.clubs.slice(0, 3).join(' · ')))) : [h('div', { class: 'card', style: { gridColumn: '1 / -1' } }, empty('🔍', 'Aucun défi pour ces filtres', 'Retirez un filtre, ou ajoutez vos propres idées dans defis.json.'))]));
  };
  draw();
  if (avertissement) root.append(h('div', { class: 'alert orange', style: { marginBottom: '12px' } }, avertissement));
  root.append(bar, grid);
  if (ctx.params.d) { const d = defis.find(x => x.id === ctx.params.d); if (d) detail(d); }
}
