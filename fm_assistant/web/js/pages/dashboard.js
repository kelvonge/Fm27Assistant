import { api } from '../api.js';
import { h, fmt, kpi, empty, tag, noteBadge, radarChart, lineChart } from '../ui.js';
import { openPlayer } from '../player.js';

export const live = true;
const STATUT = { solide: 'good', juste: 'mid', faible: 'low', trou: 'bad', inconnu: '' };
const ACTION = { prolonger: 'good', vendre: 'low', 'laisser partir': '', 'à évaluer': 'info' };

export async function render(root, ctx) {
  const d = await api.get('/api/dashboard');
  if (d.vide) {
    root.append(h('div', { class: 'card' }, empty('⚽', 'Bienvenue dans FM Assistant 27',
      'Aucune donnée de carrière pour l\'instant. Lancez Football Manager et suivez le scan guidé : l\'assistant lit les écrans pendant que vous naviguez. Vous pouvez aussi charger une carrière de démonstration pour découvrir l\'application.',
      h('button', { class: 'btn', onclick: () => ctx.navigate('lecture') }, 'Démarrer le scan guidé'),
      h('button', { class: 'btn ghost', onclick: async () => { await api.post('/api/demo/load'); location.reload(); } }, 'Charger la démonstration'))));
    return;
  }
  const n = d.niveau, c = d.classement;
  root.append(h('div', { class: 'grid g4', style: { marginBottom: '16px' } },
    kpi('Niveau du onze type', n.onze_type != null ? [fmt.num(n.onze_type), h('small', {}, ' /20')] : '—',
      n.repere ? `${n.ecart >= 0 ? '+' : ''}${fmt.num(n.ecart)} vs repère ${d.division} (${fmt.num(n.repere.niveau)})` : 'comparaison indisponible'),
    kpi('Effectif', [d.effectif.joueurs, h('small', {}, ' joueurs')], `Âge moyen ${d.effectif.age_moyen != null ? fmt.num(d.effectif.age_moyen) + ' ans' : 'non lu'} · ${d.effectif.avec_attributs} avec attributs`),
    kpi('Masse salariale', d.masse_salariale != null ? [fmt.money(d.masse_salariale), h('small', {}, ' /sem.')] : '—',
      d.marge_salariale != null ? `${d.marge_salariale >= 0 ? 'Marge' : 'Dépassement'} de ${fmt.money(Math.abs(d.marge_salariale))}/sem.` : (d.masse_source || 'salaires non lus')),
    c ? kpi('Classement', [fmt.ord(c.rank), h('small', {}, d.equipes ? ` / ${d.equipes}` : '')], `${c.points ?? '?'} pts en ${c.played ?? '?'} match(s)`)
      : kpi('Valeur de l\'effectif', fmt.money(d.effectif.valeur_totale), 'Classement non lu (ou nom du club à renseigner)')));

  const alerts = h('div', { class: 'card' }, h('h2', {}, 'Alertes', h('span', { class: 'right' }, tag(String(d.alertes.length), d.alertes.some(a => a.niveau === 'rouge') ? 'bad' : ''))),
    d.alertes.length ? h('div', { class: 'stack', style: { gap: '8px' } }, d.alertes.map(a => h('div', { class: `alert ${a.niveau} click`, onclick: () => ctx.navigate(a.lien) }, h('div', { style: { flex: 1 } }, a.texte), h('span', { class: 'faint' }, '›'))))
      : h('div', { class: 'muted' }, 'Aucune alerte : effectif, contrats et tactique sont cohérents avec ce qui a été lu.'));
  const pm = d.prochain_match;
  const board = h('div', { class: 'card' }, h('h2', {}, 'Carrière'),
    h('dl', { class: 'kv' },
      h('dt', {}, 'Club'), h('dd', {}, d.club || h('a', { href: '#/reglages' }, 'à renseigner')),
      h('dt', {}, 'Division'), h('dd', {}, d.division || h('a', { href: '#/reglages' }, 'à renseigner')),
      h('dt', {}, 'Saison'), h('dd', {}, d.saison || '—'),
      h('dt', {}, 'Objectif'), h('dd', {}, d.objectif || h('span', { class: 'muted' }, 'non renseigné (Réglages, ou adoptez un défi dans Idées de carrière)')),
      h('dt', {}, 'Style voulu'), h('dd', {}, d.style || '—'),
      h('dt', {}, 'Prochain match'), h('dd', {}, pm ? h('a', { href: '#/tactique?onglet=match' }, `${pm.opponent} (${pm.venue === 'exterieur' ? 'extérieur' : pm.venue || 'lieu non lu'}) – ${fmt.date(pm.date)}`) : h('span', { class: 'muted' }, 'calendrier non lu'))),
    h('div', { class: 'explain', style: { marginTop: '12px' } }, n.verdict));
  root.append(h('div', { class: 'grid g-main', style: { marginBottom: '16px' } }, alerts, board));

  const depth = h('div', { class: 'card' }, h('h2', {}, 'Profondeur par poste', h('a', { class: 'right small', href: '#/effectif?onglet=profondeur' }, 'Détail ›')),
    h('div', { class: 'row', style: { gap: '8px' } }, d.profondeur.map(p => h('div', { class: 'chip', title: `${p.nom} : ${p.nb} joueur(s)`, style: { padding: '6px 10px' } }, h('b', { style: { color: 'var(--text)' } }, p.label), tag(p.statut, STATUT[p.statut])))),
    d.forces.radar ? h('div', { style: { marginTop: '10px' } }, radarChart([{ name: 'Équipe', axes: d.forces.radar.axes }], 280)) : h('p', { class: 'muted small' }, 'Radar d\'équipe indisponible : pas assez d\'attributs lus.'),
    d.forces.forts.length ? h('div', { class: 'small muted' }, h('b', { style: { color: 'var(--good)' } }, 'Points forts : '), d.forces.forts.slice(0, 3).map(f => `${f.nom} ${fmt.num(f.val)}`).join(' · '), h('br'),
      h('b', { style: { color: 'var(--low)' } }, 'Points faibles : '), d.forces.faibles.slice(0, 3).map(f => `${f.nom} ${fmt.num(f.val)}`).join(' · ')) : null);
  const hist = d.historique_finances || [];
  const contracts = h('div', { class: 'card' }, h('h2', {}, 'Contrats qui expirent', h('a', { class: 'right small', href: '#/contrats' }, 'Tout voir ›')),
    d.echeances.length ? h('div', { class: 'stack', style: { gap: '6px' } }, d.echeances.map(e => h('div', { class: 'row', style: { cursor: 'pointer', flexWrap: 'nowrap' }, onclick: () => openPlayer(e.id), title: e.raison },
      noteBadge(e.note), h('div', { style: { flex: 1, minWidth: 0 } }, h('div', { class: 'pname' }, e.name), h('div', { class: 'psub' }, `${fmt.date(e.contract_end)} · dans ${e.mois_restants} mois`)), tag(e.action, ACTION[e.action]))))
      : h('div', { class: 'muted' }, d.date_jeu ? 'Aucun contrat lu n\'expire dans les 18 mois.' : 'Date de jeu non lue : échéances non calculables.'),
    hist.length >= 2 ? h('div', { style: { marginTop: '16px' } }, h('h2', {}, 'Solde du club'), lineChart([{ name: 'Solde', points: hist.map(x => ({ x: x.date, y: x.balance })) }], { height: 150, format: fmt.money })) : null);
  root.append(h('div', { class: 'grid g2' }, depth, contracts));
}
