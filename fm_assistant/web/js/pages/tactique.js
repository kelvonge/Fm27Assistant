import { api } from '../api.js';
import { h, fmt, tabs, pitch, noteBadge, tag, empty } from '../ui.js';
import { openPlayer } from '../player.js';

let memo = { tab: 'xi', formation: null };

export async function render(root, ctx) {
  if (ctx.params.onglet) memo.tab = ctx.params.onglet;
  let data = await api.get('/api/tactics' + (memo.formation ? `?formation=${encodeURIComponent(memo.formation)}` : ''));
  memo.formation = data.formation;
  const body = h('div');
  const show = (tab) => {
    memo.tab = tab;
    body.replaceChildren({ xi: xiTab, conseils: suggestTab, coherence: coherenceTab, match: matchTab }[tab]());
  };
  const reload = async (f) => { memo.formation = f; data = await api.get(`/api/tactics?formation=${encodeURIComponent(f)}`); show(memo.tab); };

  function xiPanel(xi) {
    return h('div', { class: 'stack', style: { gap: '6px' } }, xi.postes.map(p => h('div', { class: 'row', style: { flexWrap: 'nowrap', cursor: p.joueur ? 'pointer' : 'default', padding: '5px 0', borderBottom: '1px solid var(--line-soft)' }, onclick: () => p.joueur && openPlayer(p.joueur.id), title: p.raison },
      h('span', { class: 'tag', style: { width: '44px', textAlign: 'center' } }, p.label),
      h('div', { style: { flex: 1, minWidth: 0 } },
        h('div', { class: 'pname' }, p.joueur ? p.joueur.name : h('span', { style: { color: 'var(--bad)' } }, 'Aucun joueur évalué'), p.hors_poste ? h('span', { class: 'small', style: { color: 'var(--mid)' }, title: 'Aligné à un poste proche de son poste naturel (malus appliqué)' }, ' · hors poste') : null),
        h('div', { class: 'psub' }, p.joueur ? `${p.role_nom} — ${p.raison}` : 'Lisez plus de profils ou recrutez'),
        p.remplacant ? h('div', { class: 'psub faint' }, `Doublure : ${p.remplacant.name} (${p.remplacant.role_nom}, ${fmt.num(p.remplacant.note)})`) : null),
      noteBadge(p.joueur ? p.note : null))));
  }
  function xiTab() {
    const xi = data.xi;
    if (!xi.titulaires) return h('div', { class: 'card' }, empty('🧩', 'Meilleur XI indisponible', 'Aucun joueur de l\'effectif n\'a d\'attributs lus. Ouvrez les profils de vos joueurs dans FM : le onze se construira automatiquement.', h('button', { class: 'btn', onclick: () => ctx.navigate('lecture') }, 'Lecture en direct')));
    const chips = h('div', { class: 'row' }, data.formations.map(f => h('span', { class: `chip click ${f === data.formation ? 'on' : ''}`, onclick: () => reload(f) }, f)));
    const notes = [];
    if (!xi.complet) notes.push(`Onze incomplet : ${11 - xi.titulaires} poste(s) sans joueur évalué.`);
    if (xi.indisponibles.length) notes.push(`Indisponibles écartés : ${xi.indisponibles.join(', ')}.`);
    if (xi.non_evalues.length) notes.push(`${xi.non_evalues.length} joueur(s) non évalués faute d'attributs lus (${xi.non_evalues.slice(0, 5).join(', ')}${xi.non_evalues.length > 5 ? '…' : ''}).`);
    return h('div', { class: 'grid g-main' },
      h('div', { class: 'card' }, h('h2', {}, `Meilleur XI en ${xi.formation}`, h('span', { class: 'right' }, noteBadge(xi.note, { title: 'Note moyenne du onze' }))), h('div', { class: 'toolbar' }, chips), pitch(xi, (p) => p.joueur && openPlayer(p.joueur.id)),
        h('p', { class: 'small muted', style: { marginTop: '10px' } }, 'Affectation optimale de tout l\'effectif (un joueur par poste, meilleur rôle possible). Contour pointillé = joueur hors de son poste naturel.')),
      h('div', { class: 'card' }, h('h2', {}, 'Titulaires, rôles et doublures'), xiPanel(xi), notes.length ? h('div', { class: 'small muted', style: { marginTop: '10px' } }, notes.map(n => h('div', {}, '• ' + n))) : null));
  }
  function suggestTab() {
    const s = data.suggestions;
    if (!s.suggestions.length) return h('div', { class: 'card' }, empty('🧠', 'Recommandations indisponibles', s.message || 'Pas assez de données.'));
    return h('div', { class: 'stack', style: { gap: '16px' } }, s.suggestions.map((t, i) => h('div', { class: 'card' },
      h('div', { class: 'grid g-main' },
        h('div', {},
          h('div', { class: 'row' }, h('h3', { style: { margin: 0, fontSize: '18px' } }, `${i + 1}. ${t.nom}`), tag(t.formation, 'info'), t.style_voulu ? tag('votre style', 'good') : null, h('span', { class: 'spacer' }), h('span', { class: 'muted small' }, 'Adéquation'), noteBadge(t.adequation, { title: 'Moyenne pondérée des attributs exigés par ce style' })),
          h('p', { class: 'muted' }, t.description), h('div', { class: 'explain' }, t.explication),
          h('h2', { style: { marginTop: '14px' } }, `Consignes conseillées · mentalité ${t.mentalite}`), h('div', { class: 'row' }, t.instructions.map(x => h('span', { class: 'chip' }, x))),
          h('h2', { style: { marginTop: '14px' } }, 'Onze proposé'), h('div', { class: 'row', style: { gap: '6px' } }, t.xi.postes.map(p => h('span', { class: 'pchip', title: p.joueur ? p.role_nom : '', onclick: () => p.joueur && openPlayer(p.joueur.id) }, h('b', { class: 'faint' }, p.label), p.joueur ? p.joueur.name : '—', noteBadge(p.joueur ? p.note : null))))),
        h('div', {}, pitch(t.xi, (p) => p.joueur && openPlayer(p.joueur.id)))))));
  }
  function coherenceTab() {
    const c = data.coherence;
    if (!c.lue) return h('div', { class: 'card' }, empty('📋', 'Tactique non lue', c.message));
    const ST = { ok: ['adapté', 'good'], mieux: ['rôle à revoir', 'mid'], hors_poste: ['hors poste', 'bad'], inconnu: ['non évalué', ''] };
    return h('div', { class: 'grid g2' },
      h('div', { class: 'card' }, h('h2', {}, 'Tactique lue dans le jeu'),
        h('dl', { class: 'kv' }, h('dt', {}, 'Formation'), h('dd', {}, c.formation || 'non lue'), h('dt', {}, 'Mentalité'), h('dd', {}, c.mentalite || 'non lue')),
        h('div', { class: 'row', style: { margin: '10px 0' } }, c.instructions.length ? c.instructions.map(x => h('span', { class: 'chip' }, x)) : h('span', { class: 'muted' }, 'Aucune consigne d\'équipe reconnue.')),
        h('h2', { style: { marginTop: '14px' } }, 'Incohérences détectées'),
        c.alertes.length ? h('div', { class: 'stack' }, c.alertes.map(a => h('div', { class: 'alert orange' }, h('div', {}, h('b', {}, a.message), h('div', { class: 'small muted' }, a.detail), a.conseil ? h('div', { style: { marginTop: '4px' } }, '→ ' + a.conseil) : null, h('div', { class: 'small faint' }, `Calculé sur : ${a.base}`)))))
          : h('div', { class: 'explain' }, 'Aucune incohérence entre vos consignes et les joueurs alignés.')),
      h('div', { class: 'card' }, h('h2', {}, 'Joueurs ↔ rôles'),
        c.roles.length ? h('div', { class: 'stack', style: { gap: '8px' } }, c.roles.map(r => h('div', { class: 'row', style: { flexWrap: 'nowrap', alignItems: 'flex-start', cursor: r.id ? 'pointer' : 'default' }, onclick: () => r.id && openPlayer(r.id) },
          noteBadge(r.note ?? null), h('div', { style: { flex: 1 } }, h('div', {}, h('b', {}, r.joueur), h('span', { class: 'muted' }, ` — ${r.role_nom}`)), r.message ? h('div', { class: 'small muted' }, r.message) : null), tag(...ST[r.statut]))))
          : h('div', { class: 'muted' }, 'Aucun rôle lu sur le terrain : affichez la vue du terrain dans l\'écran Tactique de FM.')));
  }
  function matchTab() {
    const m = data.avant_match;
    if (!m.disponible) return h('div', { class: 'card' }, empty('📅', 'Avant-match indisponible', m.message));
    return h('div', { class: 'grid g-main' },
      h('div', { class: 'card' }, h('h2', {}, 'Conseils pour le prochain match'),
        h('h3', { style: { fontSize: '20px' } }, `${m.match.venue === 'exterieur' ? 'Déplacement chez' : 'Réception de'} ${m.adversaire}`),
        h('p', { class: 'muted' }, `${fmt.date(m.match.date)}${m.match.competition ? ' · ' + m.match.competition : ''}`),
        m.conseils.length ? h('div', { class: 'stack' }, m.conseils.map(c => h('div', { class: 'explain' }, h('b', {}, c.titre + ' — '), c.texte))) : h('p', { class: 'muted' }, 'Pas assez d\'informations lues pour donner un conseil fondé.'),
        m.manques.length ? h('div', { style: { marginTop: '12px' } }, h('h2', {}, 'Pour aller plus loin'), m.manques.map(x => h('div', { class: 'alert', style: { marginBottom: '6px' } }, x))) : null),
      h('div', { class: 'card' }, h('h2', {}, 'Au classement'),
        m.classement ? h('table', { class: 'data' }, h('thead', {}, h('tr', {}, ['', 'Rang', 'J', 'Pts', 'BP', 'BC'].map(x => h('th', { class: x ? 'r' : '' }, x)))),
          h('tbody', {}, [['Vous', m.classement.moi], [m.adversaire, m.classement.eux]].map(([n, r]) => h('tr', {}, h('td', {}, h('b', {}, n)), [fmt.ord(r.rank), r.played, r.points, r.goals_for, r.goals_against].map(v => h('td', { class: 'r' }, v ?? '—'))))))
          : h('p', { class: 'muted' }, 'Comparaison indisponible.'),
        m.effectif_adverse_lu ? h('p', { class: 'small muted' }, `${m.effectif_adverse_lu} joueur(s) adverses lus avec attributs.`) : null));
  }
  root.append(tabs([['xi', 'Meilleur XI'], ['conseils', 'Tactiques conseillées'], ['coherence', 'Cohérence de ma tactique'], ['match', 'Avant-match']], memo.tab, show), body);
  show(memo.tab);
}
