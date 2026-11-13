import { api } from '../api.js';
import { h, fmt, tabs, dataTable, noteBadge, stars, tag, empty, toast } from '../ui.js';
import { openPlayer } from '../player.js';

let memo = { tab: 'recherche', crit: {} };

export async function render(root, ctx) {
  const [kb, needs] = await Promise.all([api.get('/api/knowledge'), api.get('/api/recruitment/needs')]);
  const body = h('div');
  const show = (tab) => { memo.tab = tab; body.replaceChildren({ recherche: searchTab, besoins: needsTab, pepites: gemsTab, shortlist: () => searchTab(true) }[tab]()); };

  function resultTable(res) {
    return dataTable({
      rows: res.resultats, sort: 'note', onRow: (p) => openPlayer(p.id), emptyText: res.message || 'Aucun joueur lu ne correspond à ces critères. Élargissez-les, ou faites défiler davantage de joueurs dans la recherche de FM.',
      columns: [
        { key: 'name', label: 'Joueur', asc: true, render: (p) => h('div', {}, h('div', { class: 'pname' }, p.name, p.shortlist ? h('span', { title: 'Dans votre shortlist', style: { color: 'var(--mid)' } }, ' ★') : null), h('div', { class: 'psub' }, [p.postes.join(' · '), p.club].filter(Boolean).join(' — ') || 'poste non lu'), p.note_perso ? h('div', { class: 'psub', style: { color: 'var(--accent)' } }, '✎ ' + p.note_perso) : null) },
        { key: 'age', label: 'Âge', align: 'r' },
        { key: 'note', label: 'Note', align: 'c', render: (p) => noteBadge(p.note, { est: p.source !== 'attributs', title: p.source === 'attributs' ? 'Note calculée sur ses attributs' : p.source === 'etoiles' ? 'Estimation d\'après les étoiles' : p.source === 'partielle' ? 'Note partielle' : 'Non évalué' }) },
        { key: 'role_nom', label: 'Rôle', asc: true, render: (p) => p.role_nom || '—' },
        { key: 'ecart_niveau', label: 'vs onze', align: 'r', title: 'Écart avec le niveau de votre onze type', render: (p) => p.ecart_niveau == null ? '—' : h('span', { style: { color: p.ecart_niveau >= 0 ? 'var(--good)' : 'var(--muted)' } }, `${p.ecart_niveau >= 0 ? '+' : ''}${fmt.num(p.ecart_niveau)}`) },
        { key: 'qualite_prix', label: 'Qualité/prix', align: 'r', title: 'Écart de note par rapport aux joueurs lus du même prix (positif = bonne affaire)', render: (p) => p.qualite_prix == null ? '—' : tag(`${p.qualite_prix >= 0 ? '+' : ''}${fmt.num(p.qualite_prix)}`, p.qualite_prix >= 0.8 ? 'good' : p.qualite_prix <= -0.8 ? 'low' : '') },
        { key: 'potential_stars', label: 'Potentiel', render: (p) => stars(p.potential_stars) },
        { key: 'value', label: 'Valeur', align: 'r', render: (p) => fmt.money(p.value) },
        { key: 'wage', label: 'Salaire', align: 'r', render: (p) => fmt.wage(p.wage) },
        { key: 'explication', label: 'Pourquoi', sortable: false, render: (p) => h('div', { class: 'small muted', style: { maxWidth: '380px' } }, p.explication) },
      ],
    });
  }
  function searchTab(shortlistOnly = false) {
    const c = memo.crit;
    const out = h('div', {}, h('div', { class: 'skeleton' }));
    const run = async () => {
      const crit = { ...c, shortlist: shortlistOnly || undefined };
      try { const res = await api.post('/api/recruitment/search', crit);
        out.replaceChildren(h('div', { class: 'row small muted', style: { margin: '4px 0 10px' } }, `${res.total} joueur(s) sur ${needs.joueurs_lus} lus dans le jeu`, res.message && res.total ? ` · ${res.message}` : ''), resultTable(res));
      } catch (e) { toast(e.message, true); }
    };
    const roleSel = h('select', { onchange: (e) => { c.role = e.target.value || undefined; run(); } });
    const fillRoles = () => roleSel.replaceChildren(h('option', { value: '' }, 'Meilleur rôle du joueur'), ...kb.roles.filter(r => !c.poste || r.postes.includes(c.poste)).map(r => h('option', { value: r.id, selected: r.id === c.role }, r.nom)));
    fillRoles();
    const num = (key, ph, mult = 1) => h('input', { class: 'input', type: 'number', min: 0, placeholder: ph, value: c[key] ? c[key] / mult : '', style: { width: '120px' }, oninput: (e) => { c[key] = e.target.value ? Number(e.target.value) * mult : undefined; clearTimeout(num.t); num.t = setTimeout(run, 200); } });
    const form = h('div', { class: 'toolbar', style: { alignItems: 'flex-end' } },
      h('label', { class: 'field' }, 'Poste', h('select', { onchange: (e) => { c.poste = e.target.value || undefined; if (c.role && !kb.roles.find(r => r.id === c.role)?.postes.includes(c.poste)) c.role = undefined; fillRoles(); run(); } }, h('option', { value: '' }, 'Tous'), kb.postes.map(p => h('option', { value: p.id, selected: p.id === c.poste }, `${p.label} – ${p.nom}`)))),
      h('label', { class: 'field' }, 'Rôle recherché', roleSel),
      h('label', { class: 'field' }, 'Âge max', num('age_max', 'ex. 24')),
      h('label', { class: 'field' }, 'Budget max (M €)', num('valeur_max', 'ex. 2,5', 1e6)),
      h('label', { class: 'field' }, 'Salaire max (k €/sem.)', num('salaire_max', 'ex. 8', 1e3)),
      h('label', { class: 'field' }, 'Note minimale', num('note_min', 'ex. 12')),
      h('button', { class: 'btn ghost', onclick: () => { memo.crit = {}; show(memo.tab); } }, 'Réinitialiser'));
    run();
    return h('div', { class: 'card' }, h('h2', {}, shortlistOnly ? 'Shortlist annotée' : 'Recherche ciblée parmi les joueurs lus dans le jeu'), form, out);
  }
  function needsTab() {
    if (!needs.besoins.length) return h('div', { class: 'card' }, empty('✅', 'Aucun besoin prioritaire détecté', needs.reference == null ? 'Les besoins seront calculés quand les attributs d\'au moins 5 joueurs auront été lus.' : 'Chaque poste principal a au moins deux joueurs au niveau du onze type.'));
    const P = { 1: ['Priorité haute', 'bad'], 2: ['Priorité moyenne', 'mid'], 3: ['À anticiper', 'info'] };
    return h('div', { class: 'grid g3' }, needs.besoins.map(n => h('div', { class: 'card' },
      h('div', { class: 'row' }, h('h3', { style: { margin: 0 } }, n.nom), h('span', { class: 'spacer' }), tag(...P[n.priorite])),
      h('p', { class: 'muted' }, n.raison),
      h('div', { class: 'small' }, h('b', {}, 'Profil visé : '), n.niveau_vise != null ? `note ≥ ${fmt.num(n.niveau_vise - 0.5)} ` : '', `· rôles : ${n.roles.join(', ')}`),
      h('button', { class: 'btn small', style: { marginTop: '12px' }, onclick: () => { memo.crit = { poste: n.poste, note_min: n.niveau_vise != null ? Math.round((n.niveau_vise - 1) * 10) / 10 : undefined }; tabsEl.querySelectorAll('.tab')[0].click(); } }, 'Chercher ce profil'))));
  }
  function gemsTab() {
    if (!needs.pepites.length) return h('div', { class: 'card' }, empty('💎', 'Aucune pépite détectée', 'Les pépites sont des joueurs de 21 ans ou moins au potentiel élevé (4★+) ou déjà proches de votre niveau. Faites défiler la recherche de joueurs de FM avec les colonnes Âge et Potentiel visibles.'));
    return h('div', { class: 'grid g3' }, needs.pepites.map(g => h('div', { class: 'card idea', onclick: () => openPlayer(g.id) },
      h('div', { class: 'row' }, h('h3', { style: { margin: 0 } }, g.name), h('span', { class: 'spacer' }), noteBadge(g.note)),
      h('div', { class: 'muted small' }, `${g.age} ans · ${g.postes.join(' · ') || 'poste non lu'}${g.club ? ' · ' + g.club : ''}`),
      h('div', { class: 'row' }, stars(g.potential_stars), h('span', { class: 'spacer' }), h('b', {}, fmt.money(g.value))),
      h('div', { class: 'small' }, g.raison))));
  }
  const tabsEl = tabs([['recherche', 'Recherche ciblée'], ['besoins', `Besoins de l'effectif (${needs.besoins.length})`], ['pepites', `Pépites (${needs.pepites.length})`], ['shortlist', 'Shortlist']], memo.tab, show);
  root.append(tabsEl, body);
  show(memo.tab);
}
