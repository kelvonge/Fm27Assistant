// Fiche joueur (tiroir latéral) + liste de comparaison partagée entre les pages.
import { api } from './api.js';
import { h, fmt, noteBadge, playerNote, attrClass, stars, tag, toast, initials, radarChart, lineChart, noteClass } from './ui.js';

export const compare = {
  ids: [],
  toggle(id) { const i = this.ids.indexOf(id); if (i >= 0) this.ids.splice(i, 1); else { if (this.ids.length >= 4) this.ids.shift(); this.ids.push(id); } document.dispatchEvent(new CustomEvent('fma:compare')); },
  has(id) { return this.ids.includes(id); },
};
const CATS = [['technique', 'Technique'], ['mental', 'Mental'], ['physique', 'Physique'], ['gardien', 'Gardien']];
const SCOPES = { effectif: 'Mon effectif', cible: 'Cible de recrutement', autre: 'Autre club' };

export function closePlayer() { const d = document.getElementById('drawer'); d.hidden = true; d.replaceChildren(); }

export async function openPlayer(id) {
  const d = document.getElementById('drawer');
  const panel = h('div', { class: 'panel' }, h('div', { class: 'skeleton' }));
  d.replaceChildren(h('div', { class: 'veil', onclick: closePlayer }), panel);
  d.hidden = false;
  let p;
  try { p = await api.get(`/api/players/${id}`); } catch (e) { toast(e.message, true); closePlayer(); return; }
  const a = p.analyse || {};
  const refresh = () => { document.dispatchEvent(new CustomEvent('fma:refresh')); };
  const save = async (patch, msg) => { try { await api.patch(`/api/players/${id}`, patch); if (msg) toast(msg); refresh(); } catch (e) { toast(e.message, true); } };

  const hero = h('div', { class: 'hero' },
    h('div', { class: 'avatar' }, initials(p.name)),
    h('div', { style: { flex: 1, minWidth: 0 } },
      h('h2', {}, p.name),
      h('div', { class: 'muted' }, [p.age ? `${p.age} ans` : 'âge non lu', p.positions || 'poste non lu', p.club].filter(Boolean).join(' · ')),
      h('div', { class: 'row', style: { marginTop: '6px' } }, tag(SCOPES[p.scope] || p.scope, p.scope === 'effectif' ? 'good' : 'info'),
        p.shortlist ? tag('Shortlist', 'mid') : null, p.injury ? tag(p.injury, 'bad') : null,
        p.game_date ? h('span', { class: 'small faint' }, `lu le ${fmt.date(p.game_date)} (date de jeu)`) : null)),
    h('button', { class: 'btn ghost icon', onclick: closePlayer, title: 'Fermer' }, '✕'));

  const facts = h('div', { class: 'grid g4', style: { marginBottom: '14px' } },
    h('div', { class: 'card kpi' }, h('div', { class: 'label' }, 'Meilleur rôle'), h('div', { class: 'row' }, playerNote(p), h('b', {}, a.role_nom || '—'))),
    h('div', { class: 'card kpi' }, h('div', { class: 'label' }, 'Valeur'), h('div', { class: 'value', style: { fontSize: '19px' } }, fmt.money(p.value))),
    h('div', { class: 'card kpi' }, h('div', { class: 'label' }, 'Salaire'), h('div', { class: 'value', style: { fontSize: '19px' } }, fmt.wage(p.wage))),
    h('div', { class: 'card kpi' }, h('div', { class: 'label' }, 'Fin de contrat'), h('div', { class: 'value', style: { fontSize: '19px' } }, fmt.date(p.contract_end))));

  const blocks = [hero, facts];
  if (a.explication) blocks.push(h('div', { class: 'explain', style: { marginBottom: '14px' } }, a.explication));
  else blocks.push(h('div', { class: 'explain', style: { marginBottom: '14px', borderColor: 'var(--mid)' } },
    a.source === 'etoiles' ? `Attributs non lus. Note estimée d'après ses ${p.ability_stars} étoile(s) par rapport à votre onze type : ouvrez son profil dans FM pour une analyse réelle.`
      : 'Attributs non lus : ouvrez le profil de ce joueur dans FM (page des attributs) pour obtenir ses notes par rôle.'));

  if (a.radar || (a.roles || []).length) {
    blocks.push(h('div', { class: 'grid g2', style: { marginBottom: '14px' } },
      h('div', { class: 'card' }, h('h2', {}, 'Profil'), a.radar ? radarChart([{ name: p.name, axes: a.radar.axes }], 290) : h('div', { class: 'muted' }, 'Radar indisponible.')),
      h('div', { class: 'card' }, h('h2', {}, 'Notes par rôle'), h('div', { class: 'stack', style: { gap: '9px' } }, (a.roles || []).map(r =>
        h('div', { title: `Points forts : ${r.forts.map(f => `${f.nom} ${f.val}`).join(', ')}${r.manquants.length ? `\nNon lus : ${r.manquants.join(', ')}` : ''}` },
          h('div', { class: 'row', style: { justifyContent: 'space-between', flexWrap: 'nowrap' } }, h('span', {}, r.nom, r.fiable ? null : h('span', { class: 'faint small' }, ` (partiel ${Math.round(r.couverture * 100)} %)`)), h('b', { class: `num ${noteClass(r.note).replace('n', 'a')}` }, fmt.num(r.note, 2))),
          h('div', { class: 'bar' }, h('i', { style: { width: `${r.note / 20 * 100}%` } }))))))));
  }
  // Attributs (cliquer une valeur pour la corriger)
  const known = p.attributs_detail.filter(x => x.val != null);
  if (known.length) {
    const grid = h('div', { class: 'attr-grid' });
    for (const [cat, label] of CATS) {
      const items = p.attributs_detail.filter(x => x.categorie === cat && (x.val != null || cat !== 'gardien'));
      if (!items.some(x => x.val != null)) continue;
      grid.append(h('h4', {}, label));
      for (const it of items) {
        const b = h('b', { class: `${attrClass(it.val)} ${it.source && it.source !== 'exact' ? 'approx' : ''}`, style: { cursor: 'pointer' },
          title: it.val == null ? 'Non lu – cliquer pour saisir' : (it.source === 'barres' ? 'Lu d\'après une barre (approximatif)' : it.source === 'plage' ? 'Plage de recrutement (milieu de la fourchette)' : 'Cliquer pour corriger'),
          onclick: () => {
            const inp = h('input', { class: 'input', type: 'number', min: 1, max: 20, value: it.val ?? '', style: { width: '56px', padding: '1px 5px' } });
            const done = async () => { const v = parseInt(inp.value, 10); if (v >= 1 && v <= 20 && v !== it.val) { await save({ data: { attributes: { [it.id]: v }, attr_source: { ...(p.attr_source || {}), [it.id]: 'exact' } } }); openPlayer(id); } else b.replaceChildren(it.val ?? '—'); };
            inp.addEventListener('blur', done); inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') inp.blur(); });
            b.replaceChildren(inp); inp.focus();
          } }, it.val ?? '—');
        grid.append(h('div', { class: 'attr' }, h('span', { class: it.val == null ? 'faint' : '' }, it.nom), b));
      }
    }
    blocks.push(h('div', { class: 'card', style: { marginBottom: '14px' } }, h('h2', {}, 'Attributs', h('span', { class: 'right small muted' }, `${known.length} lus · cliquez une valeur pour la corriger`)), grid));
  }
  const hist = (p.historique || []).filter(x => x.date);
  if (hist.length >= 2) {
    blocks.push(h('div', { class: 'card', style: { marginBottom: '14px' } }, h('h2', {}, 'Évolution (par date de jeu)'),
      lineChart([{ name: 'Note dans son meilleur rôle', points: hist.map(x => ({ x: x.date, y: x.note })) }], { format: v => fmt.num(v, 1) }),
      hist.some(x => x.value) ? h('div', { style: { marginTop: '10px' } }, lineChart([{ name: 'Valeur', color: '#4ea3f2', points: hist.map(x => ({ x: x.date, y: x.value })) }], { height: 150, format: fmt.money })) : null));
  }
  const note = h('textarea', { rows: 2, placeholder: 'Votre note personnelle sur ce joueur (prix demandé, rôle envisagé…)' }, p.note_perso || '');
  note.value = p.note_perso || '';
  const scopeSel = h('select', { onchange: (e) => save({ scope: e.target.value }, 'Groupe mis à jour') }, Object.entries(SCOPES).map(([k, v]) => h('option', { value: k, selected: k === p.scope }, v)));
  const cmpBtn = h('button', { class: 'btn ghost' }, compare.has(id) ? 'Retirer du comparateur' : 'Ajouter au comparateur');
  cmpBtn.onclick = () => { compare.toggle(id); cmpBtn.textContent = compare.has(id) ? 'Retirer du comparateur' : 'Ajouter au comparateur'; toast(compare.has(id) ? 'Ajouté au comparateur (onglet Effectif → Comparateur)' : 'Retiré du comparateur'); };
  blocks.push(h('div', { class: 'card' }, h('h2', {}, 'Suivi'),
    h('div', { class: 'stack' }, note,
      h('div', { class: 'row' },
        h('button', { class: 'btn', onclick: () => save({ data: { note_perso: note.value || null } }, 'Note enregistrée') }, 'Enregistrer la note'),
        cmpBtn,
        h('button', { class: 'btn ghost', onclick: async () => { await save({ shortlist: !p.shortlist }, p.shortlist ? 'Retiré de la shortlist' : 'Ajouté à la shortlist'); openPlayer(id); } }, p.shortlist ? 'Retirer de la shortlist' : 'Ajouter à la shortlist'),
        h('span', { class: 'spacer' }), scopeSel,
        h('button', { class: 'btn ghost', title: 'Supprimer cette fiche de la base locale (le jeu n\'est pas modifié)', onclick: async () => { if (confirm(`Supprimer la fiche de ${p.name} ? Elle sera recréée si le joueur est relu dans FM.`)) { await api.del(`/api/players/${id}`); closePlayer(); refresh(); } } }, 'Supprimer')))));
  panel.replaceChildren(...blocks);
}
