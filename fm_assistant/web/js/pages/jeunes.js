import { api } from '../api.js';
import { h, fmt, noteBadge, stars, tag, empty } from '../ui.js';
import { openPlayer } from '../player.js';

export const live = true;
const DEC = { 'intégrer': ['Intégrer à l\'équipe première', 'good'], rotation: ['Rotation / remplaçant', 'info'], 'prêt': ['Prêt conseillé', 'mid'], garder: ['Garder en formation', ''], 'à évaluer': ['À évaluer', ''] };

export async function render(root) {
  const d = await api.get('/api/youth');
  if (!d.jeunes.length) { root.append(h('div', { class: 'card' }, empty('🌱', 'Aucun jeune à suivre', d.message || 'Aucun joueur de 21 ans ou moins lu.'))); return; }
  const counts = {};
  d.jeunes.forEach(j => { counts[j.decision] = (counts[j.decision] || 0) + 1; });
  root.append(h('div', { class: 'row', style: { marginBottom: '14px' } }, Object.entries(counts).map(([k, n]) => h('span', { class: 'chip' }, tag(String(n), DEC[k][1]), DEC[k][0])),
    h('span', { class: 'spacer' }), h('span', { class: 'small muted' }, d.reference != null ? `Référence : onze type à ${fmt.num(d.reference)}/20` : 'Niveau de référence indisponible'),
    d.age_inconnu ? h('span', { class: 'small muted' }, ` · ${d.age_inconnu} joueur(s) sans âge lu, non classés`) : null));
  root.append(h('div', { class: 'grid g2' }, d.jeunes.map(j => h('div', { class: 'card idea', onclick: () => openPlayer(j.id) },
    h('div', { class: 'row' }, noteBadge(j.note), h('div', { style: { flex: 1 } }, h('h3', { style: { margin: 0 } }, j.name), h('div', { class: 'psub' }, `${j.age} ans · ${j.postes.join(' · ') || 'poste non lu'}${j.rang_poste ? ` · ${fmt.ord(j.rang_poste)} choix à son poste` : ''}`)), tag(...DEC[j.decision])),
    h('div', { class: 'row small' }, h('span', { class: 'muted' }, 'Niveau'), stars(j.ability_stars), h('span', { class: 'muted' }, 'Potentiel'), stars(j.potential_stars)),
    h('div', { class: 'explain' }, j.raison),
    j.plan ? h('div', {}, h('div', { class: 'small muted', style: { marginBottom: '6px' } }, j.plan),
      h('table', { class: 'data' }, h('tbody', {}, j.axes.map(a => h('tr', {}, h('td', {}, a.nom), h('td', { class: 'r' }, h('b', {}, a.val)), h('td', { class: 'muted small' }, a.travail)))))) : null))));
}
