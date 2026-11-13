import { api } from '../api.js';
import { h, fmt, tabs, dataTable, playerNote, stars, tag, empty, radarChart, noteBadge, attrClass, PALETTE } from '../ui.js';
import { openPlayer, compare } from '../player.js';

export const live = true;
const LINES = { Tous: null, Gardiens: ['GB'], Défenseurs: ['DD', 'DC', 'DG', 'LD', 'LG'], Milieux: ['MDC', 'MC', 'MD', 'MG'], Offensifs: ['MOD', 'MOC', 'MOG', 'BU'] };
const STATUT = { solide: 'good', juste: 'mid', faible: 'low', trou: 'bad', inconnu: '' };
let memo = { tab: 'joueurs', q: '', line: 'Tous' };

export async function render(root, ctx) {
  if (ctx.params.onglet) memo.tab = ctx.params.onglet;
  const { joueurs, reference } = await api.get('/api/players?scope=effectif');
  if (!joueurs.length) {
    root.append(h('div', { class: 'card' }, empty('👥', 'Effectif non lu', 'Ouvrez l\'écran Effectif dans FM (puis les profils de vos joueurs) : la liste se remplira toute seule.', h('button', { class: 'btn', onclick: () => ctx.navigate('lecture') }, 'Voir la lecture en direct'))));
    return;
  }
  const body = h('div');
  const show = async (tab) => {
    memo.tab = tab;
    if (tab === 'joueurs') body.replaceChildren(playersTab(joueurs, reference));
    else if (tab === 'profondeur' || tab === 'forces') { const a = await api.get('/api/squad/analysis'); body.replaceChildren(tab === 'profondeur' ? depthTab(a) : strengthTab(a)); }
    else body.replaceChildren(await compareTab(joueurs));
  };
  root.append(tabs([['joueurs', `Joueurs (${joueurs.length})`], ['profondeur', 'Profondeur par poste'], ['forces', 'Forces & faiblesses'], ['comparateur', 'Comparateur']], memo.tab, show), body);
  await show(memo.tab);
}

function playersTab(players, ref) {
  const holder = h('div');
  const draw = () => {
    const q = memo.q.toLowerCase(), line = LINES[memo.line];
    const rows = players.filter(p => (!q || p.name.toLowerCase().includes(q) || (p.analyse.role_nom || '').toLowerCase().includes(q)) && (!line || p.analyse.postes.some(x => line.includes(x))));
    holder.replaceChildren(dataTable({
      rows, sort: 'note', onRow: (p) => openPlayer(p.id), emptyText: 'Aucun joueur ne correspond au filtre.',
      columns: [
        { key: 'cmp', label: '⇄', sortable: false, title: 'Ajouter au comparateur', render: (p) => h('input', { type: 'checkbox', checked: compare.has(p.id), onchange: () => compare.toggle(p.id) }) },
        { key: 'name', label: 'Joueur', asc: true, render: (p) => h('div', {}, h('div', { class: 'pname' }, p.name, p.injury ? h('span', { title: p.injury, style: { color: 'var(--bad)' } }, ' ✚') : null), h('div', { class: 'psub' }, p.analyse.postes.join(' · ') || p.positions || 'poste non lu')) },
        { key: 'age', label: 'Âge', align: 'r' },
        { key: 'role', label: 'Meilleur rôle', asc: true, value: (p) => p.analyse.role_nom, render: (p) => p.analyse.role_nom || h('span', { class: 'faint', title: 'Ouvrez son profil dans FM' }, 'attributs non lus') },
        { key: 'note', label: 'Note', align: 'c', value: (p) => p.analyse.note, render: playerNote },
        { key: 'ability_stars', label: 'Niveau', render: (p) => stars(p.ability_stars) },
        { key: 'potential_stars', label: 'Potentiel', render: (p) => stars(p.potential_stars) },
        { key: 'value', label: 'Valeur', align: 'r', render: (p) => fmt.money(p.value) },
        { key: 'wage', label: 'Salaire', align: 'r', render: (p) => fmt.wage(p.wage) },
        { key: 'contract_end', label: 'Contrat', render: (p) => fmt.date(p.contract_end) },
        { key: 'form', label: 'Forme', align: 'r', render: (p) => fmt.num(p.form, 2) },
        { key: 'morale', label: 'Moral', asc: true, render: (p) => p.morale || '—' },
      ],
    }));
  };
  const input = h('input', { class: 'input', placeholder: 'Filtrer par nom ou rôle…', value: memo.q, style: { width: '260px' }, oninput: (e) => { memo.q = e.target.value; draw(); } });
  const chips = h('div', { class: 'row' });
  const drawChips = () => chips.replaceChildren(...Object.keys(LINES).map(l => h('span', { class: `chip click ${memo.line === l ? 'on' : ''}`, onclick: () => { memo.line = l; drawChips(); draw(); } }, l)));
  drawChips(); draw();
  return h('div', { class: 'card' }, h('div', { class: 'toolbar' }, input, chips, h('span', { class: 'spacer' }),
    h('span', { class: 'small muted' }, ref != null ? `Niveau du onze type : ${fmt.num(ref)}/20` : 'Niveau du onze type non calculable (attributs manquants)')), holder);
}

function depthTab(a) {
  return h('div', { class: 'card' }, h('h2', {}, 'Profondeur par poste', h('span', { class: 'right small muted' }, a.reference != null ? `Référence : onze type à ${fmt.num(a.reference)}/20 · « au niveau » = à moins d'un point` : '')),
    a.profondeur.map(d => h('div', { class: 'depth-row', title: d.message },
      h('b', {}, d.label), tag(d.statut, STATUT[d.statut]),
      h('div', {}, h('div', { class: 'depth-players' }, d.joueurs.length ? d.joueurs.map(c => h('span', { class: `pchip ${c.blesse ? 'inj' : ''}`, onclick: () => openPlayer(c.id), title: c.role ? `${c.role}${c.blesse ? ' – indisponible' : ''}` : 'Attributs non lus' }, c.name, noteBadge(c.note))) : h('span', { class: 'muted' }, 'Aucun joueur')),
        h('div', { class: 'small muted', style: { marginTop: '4px' } }, d.message)))));
}

function strengthTab(a) {
  const f = a.forces;
  if (!f.radar) return h('div', { class: 'card' }, empty('📊', 'Pas assez d\'attributs lus', `Seuls ${a.avec_attributs} joueur(s) sur ${a.joueurs} ont des attributs. Ouvrez les profils dans FM pour obtenir les forces et faiblesses de l'équipe.`));
  const list = (items, good) => h('div', { class: 'stack', style: { gap: '9px' } }, items.map(x => h('div', {},
    h('div', { class: 'row', style: { justifyContent: 'space-between' } }, h('span', {}, x.nom), h('b', { class: `num ${attrClass(x.val)}` }, fmt.num(x.val), h('span', { class: 'faint small' }, ` (${x.ecart >= 0 ? '+' : ''}${fmt.num(x.ecart)})`))),
    h('div', { class: 'bar' }, h('i', { style: { width: `${x.val / 20 * 100}%`, background: good ? 'var(--good)' : 'var(--low)' } })))));
  return h('div', { class: 'grid g3' },
    h('div', { class: 'card' }, h('h2', {}, 'Profil de l\'équipe'), radarChart([{ name: 'Équipe', axes: f.radar.axes }], 300), h('p', { class: 'small muted' }, `Moyennes des 18 meilleurs joueurs de champ. Moyenne générale : ${fmt.num(f.moyenne)}.`)),
    h('div', { class: 'card' }, h('h2', {}, 'Points forts'), list(f.forts, true)),
    h('div', { class: 'card' }, h('h2', {}, 'Points faibles'), list(f.faibles, false)));
}

async function compareTab(players) {
  if (compare.ids.length < 2) return h('div', { class: 'card' }, empty('⇄', 'Comparateur', 'Cochez 2 à 4 joueurs dans la liste (colonne ⇄), ou utilisez « Ajouter au comparateur » depuis une fiche — y compris pour des cibles de recrutement.'));
  const { joueurs, attributs } = await api.get('/api/compare?ids=' + compare.ids.join(','));
  const withRadar = joueurs.filter(p => p.analyse.radar);
  const sameAxes = withRadar.length && withRadar.every(p => p.analyse.radar.axes.length === withRadar[0].analyse.radar.axes.length);
  const head = h('tr', {}, h('th', {}, ''), joueurs.map((p, i) => h('th', { class: 'c', style: { color: PALETTE[i] } }, p.name)));
  const row = (label, vals, best = 'max', render = (v) => v ?? '—') => {
    const nums = vals.filter(v => typeof v === 'number');
    const target = nums.length > 1 ? (best === 'max' ? Math.max(...nums) : Math.min(...nums)) : null;
    return h('tr', {}, h('td', {}, label), vals.map(v => h('td', { class: 'c', style: v === target && nums.some(n => n !== target) ? { fontWeight: 750, color: 'var(--good)' } : {} }, render(v))));
  };
  const rows = [
    row('Âge', joueurs.map(p => p.age), 'min'), row('Note (meilleur rôle)', joueurs.map(p => p.analyse.note), 'max', v => fmt.num(v, 2)),
    h('tr', {}, h('td', {}, 'Meilleur rôle'), joueurs.map(p => h('td', { class: 'c' }, p.analyse.role_nom || '—'))),
    row('Valeur', joueurs.map(p => p.value), 'min', fmt.money), row('Salaire', joueurs.map(p => p.wage), 'min', fmt.wage),
  ];
  for (const cat of ['technique', 'mental', 'physique', 'gardien']) {
    const list = attributs.filter(a => a.categorie === cat && joueurs.some(p => p.attributes?.[a.id] != null));
    if (!list.length) continue;
    rows.push(h('tr', {}, h('th', { colSpan: joueurs.length + 1 }, cat)));
    for (const a of list) rows.push(row(a.nom, joueurs.map(p => p.attributes?.[a.id] ?? null)));
  }
  return h('div', { class: 'grid g-main' },
    h('div', { class: 'card' }, h('h2', {}, 'Comparaison détaillée', h('button', { class: 'btn ghost small right', onclick: () => { compare.ids.length = 0; document.dispatchEvent(new CustomEvent('fma:refresh')); } }, 'Vider')), h('div', { class: 'table-wrap' }, h('table', { class: 'data' }, h('thead', {}, head), h('tbody', {}, rows)))),
    h('div', { class: 'card' }, h('h2', {}, 'Radars superposés'), sameAxes ? radarChart(withRadar.map((p, i) => ({ name: p.name, axes: p.analyse.radar.axes, color: PALETTE[joueurs.indexOf(p)] })), 340) : h('p', { class: 'muted' }, 'Radars non superposables (gardien et joueur de champ, ou attributs non lus).'),
      h('div', { class: 'legend', style: { marginTop: '8px' } }, joueurs.map((p, i) => h('span', {}, h('i', { style: { background: PALETTE[i] } }), p.name)))));
}
