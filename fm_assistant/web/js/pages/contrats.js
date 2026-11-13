import { api } from '../api.js';
import { h, fmt, kpi, dataTable, noteBadge, tag, lineChart, empty } from '../ui.js';
import { openPlayer } from '../player.js';

export const live = true;
const ACTION = { prolonger: 'good', vendre: 'low', 'laisser partir': '', 'à évaluer': 'info' };

export async function render(root) {
  const d = await api.get('/api/contracts');
  if (!d.tous.length) { root.append(h('div', { class: 'card' }, empty('📄', 'Aucun contrat lu', 'Affichez les colonnes Salaire et Contrat dans la vue Effectif de FM, puis ouvrez l\'écran Finances.'))); return; }
  const f = d.finances || {};
  root.append(h('div', { class: 'grid g4', style: { marginBottom: '16px' } },
    kpi('Masse salariale', (f.wage_bill ?? d.masse_salariale_lue) != null ? [fmt.money(f.wage_bill ?? d.masse_salariale_lue), h('small', {}, ' /sem.')] : '—', f.wage_bill ? 'lue sur l\'écran Finances' : 'somme des salaires lus'),
    kpi('Budget salarial', f.wage_budget != null ? [fmt.money(f.wage_budget), h('small', {}, ' /sem.')] : '—', d.marge_salariale != null ? `${d.marge_salariale >= 0 ? 'Marge' : 'Dépassement'} : ${fmt.money(Math.abs(d.marge_salariale))}` : 'écran Finances non lu'),
    kpi('Budget transferts', fmt.money(f.transfer_budget), f.transfer_budget == null ? 'écran Finances non lu' : ''),
    kpi('Solde du club', fmt.money(f.balance), d.economie_ventes ? `Ventes conseillées : −${fmt.money(d.economie_ventes)}/sem. de salaires` : '')));
  if (d.notes.length) root.append(h('div', { class: 'stack', style: { marginBottom: '16px', gap: '6px' } }, d.notes.map(n => h('div', { class: 'alert' }, n))));
  const cols = (withAction) => [
    { key: 'name', label: 'Joueur', asc: true, render: (p) => h('div', {}, h('div', { class: 'pname' }, p.name), h('div', { class: 'psub' }, `${p.age ?? '?'} ans · ${p.postes.join(' · ')}`)) },
    { key: 'note', label: 'Note', align: 'c', render: (p) => noteBadge(p.note) },
    { key: 'contract_end', label: 'Fin de contrat', asc: true, render: (p) => p.contract_end ? h('span', {}, fmt.date(p.contract_end), p.mois_restants != null ? h('span', { class: 'muted small' }, ` (${p.mois_restants} mois)`) : null) : '—' },
    { key: 'wage', label: 'Salaire', align: 'r', render: (p) => fmt.wage(p.wage) },
    { key: 'value', label: 'Valeur', align: 'r', render: (p) => fmt.money(p.value) },
    ...(withAction ? [{ key: 'action', label: 'Conseil', asc: true, render: (p) => p.action ? tag(p.action, ACTION[p.action]) : '—' },
      { key: 'raison', label: 'Pourquoi', sortable: false, render: (p) => h('div', { class: 'small muted', style: { maxWidth: '460px' } }, p.raison || '') }] : []),
  ];
  root.append(h('div', { class: 'card', style: { marginBottom: '16px' } }, h('h2', {}, 'Contrats qui expirent dans les 18 mois'),
    dataTable({ rows: d.echeances, columns: cols(true), sort: 'contract_end', dir: 1, onRow: (p) => openPlayer(p.id), maxHeight: '420px', emptyText: d.date_jeu ? 'Aucune échéance proche parmi les contrats lus.' : 'Date de jeu non lue : échéances non calculables.' })));
  root.append(h('div', { class: 'card', style: { marginBottom: '16px' } }, h('h2', {}, 'Joueurs à vendre'),
    dataTable({ rows: d.a_vendre, columns: cols(true).filter(c => c.key !== 'action'), sort: 'wage', onRow: (p) => openPlayer(p.id), maxHeight: '420px', emptyText: 'Aucun joueur clairement en trop d\'après les données lues.' })));
  const hist = d.historique_finances || [];
  root.append(h('div', { class: 'grid g-main' },
    h('div', { class: 'card' }, h('h2', {}, 'Tous les salaires', h('span', { class: 'right small muted' }, d.salaire_median != null ? `Médiane : ${fmt.wage(d.salaire_median)}` : '')), dataTable({ rows: d.tous, columns: cols(false), sort: 'wage', onRow: (p) => openPlayer(p.id), maxHeight: '480px' })),
    h('div', { class: 'stack', style: { gap: '16px' } },
      h('div', { class: 'card' }, h('h2', {}, 'Évolution financière'), lineChart([{ name: 'Solde', points: hist.map(x => ({ x: x.date, y: x.balance })) }], { format: fmt.money }),
        hist.some(x => x.wage_bill) ? h('div', { style: { marginTop: '10px' } }, lineChart([{ name: 'Masse salariale', color: '#f2c14e', points: hist.map(x => ({ x: x.date, y: x.wage_bill })) }, { name: 'Budget salarial', color: '#4ea3f2', points: hist.map(x => ({ x: x.date, y: x.wage_budget })) }], { height: 150, format: fmt.money })) : null),
      h('div', { class: 'card' }, h('h2', {}, 'Staff'), d.staff?.length ? h('table', { class: 'data' }, h('tbody', {}, d.staff.map(s => h('tr', {}, h('td', {}, h('b', {}, s.name)), h('td', { class: 'muted' }, s.job || '—'), h('td', { class: 'r' }, fmt.date(s.contract_end)))))) : h('div', { class: 'muted' }, 'Staff non lu : ouvrez l\'écran Staff dans FM.')))));
}
