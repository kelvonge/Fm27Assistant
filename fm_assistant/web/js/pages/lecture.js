// Lecture en direct : statut, scan guidé, calibrage (« voici ce que j'ai lu »), journal.
import { api } from '../api.js';
import { h, fmt, tag, toast, empty } from '../ui.js';

export const live = true;
const CHAMPS = { name: 'Nom', age: 'Âge', position: 'Poste', club: 'Club', nationality: 'Nationalité', value: 'Valeur', wage: 'Salaire', contract_end: 'Fin de contrat', ability_stars: 'Niveau (étoiles)', potential_stars: 'Potentiel (étoiles)', form: 'Forme / note moyenne', morale: 'Moral', condition: 'Condition', injury: 'Blessure / statut', apps: 'Matchs', goals: 'Buts', assists: 'Passes déc.', role: 'Rôle', foot: 'Pied', height: 'Taille', personality: 'Personnalité', team: 'Équipe', rank: 'Rang', played: 'Joués', won: 'Gagnés', drawn: 'Nuls', lost: 'Perdus', goals_for: 'Buts pour', goals_against: 'Buts contre', goal_diff: 'Différence', points: 'Points', date: 'Date', opponent: 'Adversaire', competition: 'Compétition', venue: 'Lieu', result: 'Résultat', job: 'Fonction' };
const ETAT = { actif: ['Lecture active', 'good'], arriere_plan: ['Jeu en arrière-plan', 'mid'], absent: ['Jeu non détecté', ''], pause: ['En pause', 'mid'], indisponible: ['Indisponible', 'bad'], arret: ['Arrêté', ''] };
let showBoxes = true;

export async function render(root, ctx) {
  const [last, guide, scans, settings] = await Promise.all([api.get('/api/capture/last'), api.get('/api/scan-guide'), api.get('/api/scans'), api.get('/api/settings')]);
  const st = ctx.status || await api.get('/api/status');
  const act = async (fn, msg) => { try { await fn(); if (msg) toast(msg); ctx.refresh(); } catch (e) { toast(e.message, true); } };

  if (settings.premier_lancement && st.compteurs.effectif === 0) {
    root.append(h('div', { class: 'card', style: { marginBottom: '16px', borderColor: 'var(--accent)' } },
      h('h3', { style: { fontSize: '19px' } }, 'Premier lancement : trois étapes'),
      h('ol', { class: 'clean', style: { lineHeight: 1.7 } },
        h('li', {}, 'Lancez Football Manager 27 et chargez votre partie (mode fenêtré ou fenêtré sans bordure recommandé).'),
        h('li', {}, 'Cliquez sur « Démarrer le scan guidé » puis visitez les écrans listés : chaque écran lu se coche tout seul.'),
        h('li', {}, 'Vérifiez dans « Ce que j\'ai lu » que les textes sont corrects ; corrigez si besoin, l\'assistant s\'en souviendra.')),
      h('div', { class: 'row', style: { marginTop: '10px' } },
        h('button', { class: 'btn', onclick: () => act(() => api.post('/api/scan-guide/start'), 'Scan guidé démarré : passez dans FM') }, 'Démarrer le scan guidé'),
        h('button', { class: 'btn ghost', onclick: async () => { await api.post('/api/demo/load'); location.hash = '#/dashboard'; location.reload(); } }, 'Découvrir avec la démonstration'))));
  }

  // ---- Statut
  const statusBox = h('div');
  const drawStatus = (s) => {
    const [label, cls] = ETAT[s.etat] || [s.etat, ''];
    statusBox.replaceChildren(
      h('div', { class: 'row', style: { marginBottom: '8px' } }, tag(label, cls), s.demo ? tag('données de démonstration chargées', 'info') : null),
      h('div', { class: 'status-big' }, s.message),
      h('dl', { class: 'kv', style: { marginTop: '12px' } },
        h('dt', {}, 'Fenêtre'), h('dd', {}, s.fenetre || '—'),
        h('dt', {}, 'Résolution lue'), h('dd', {}, s.resolution ? `${s.resolution[0]} × ${s.resolution[1]}` : '—'),
        h('dt', {}, 'Moteur de lecture'), h('dd', {}, s.ocr || 'chargé à la première lecture'),
        h('dt', {}, 'Lectures (session)'), h('dd', {}, s.lectures),
        h('dt', {}, 'Dernière lecture'), h('dd', {}, s.derniere_lecture ? s.derniere_lecture.replace('T', ' à ') : '—'),
        h('dt', {}, 'En base'), h('dd', {}, `${s.compteurs.effectif} joueurs dans l'effectif · ${s.compteurs.cible} cibles · ${s.compteurs.autre} autres`)),
      s.erreur && s.etat !== 'indisponible' ? h('div', { class: 'alert rouge', style: { marginTop: '10px' } }, s.erreur) : null,
      ...(s.ocr_erreurs || []).map(e => h('div', { class: 'alert rouge', style: { marginTop: '8px' } }, 'Moteur OCR indisponible — ' + e)),
      ...(s.avertissements || []).map(w => h('div', { class: 'alert orange', style: { marginTop: '8px' } }, w)),
      ...(s.avertissements_fichiers || []).map(w => h('div', { class: 'alert orange', style: { marginTop: '8px' } }, w)));
  };
  drawStatus(st);
  const onStatus = (e) => { if (statusBox.isConnected) drawStatus(e.detail); else document.removeEventListener('fma:status', onStatus); };
  document.addEventListener('fma:status', onStatus);
  const file = h('input', { type: 'file', accept: 'image/png,image/jpeg', hidden: true, onchange: async (e) => { const f = e.target.files[0]; if (!f) return; toast('Lecture de la capture…'); await act(async () => { await api.post('/api/capture/upload', await f.arrayBuffer()); }, 'Capture lue et enregistrée'); } });
  const statusCard = h('div', { class: 'card' }, h('h2', {}, 'Compagnon de lecture'), statusBox,
    h('div', { class: 'row', style: { marginTop: '14px' } },
      h('button', { class: 'btn', disabled: !st.plateforme_ok, onclick: () => act(() => api.post('/api/capture/scan-now'), 'Lecture demandée') }, 'Lire l\'écran maintenant'),
      h('button', { class: 'btn ghost', disabled: !st.plateforme_ok, onclick: () => act(() => api.put('/api/settings', { capture_active: !settings.capture_active }), settings.capture_active ? 'Lecture mise en pause' : 'Lecture relancée') }, settings.capture_active ? 'Mettre en pause' : 'Reprendre la lecture'),
      h('button', { class: 'btn ghost', title: 'Lire une capture d\'écran enregistrée (PNG/JPG) : utile pour tester ou calibrer sans le jeu', onclick: () => file.click() }, 'Importer une capture…'), file));

  // ---- Scan guidé
  const guideCard = h('div', { class: 'card' }, h('h2', {}, 'Scan complet guidé', h('span', { class: 'right' }, guide.termine ? tag('terminé', 'good') : tag(`${Math.round(guide.progression * 100)} %`))),
    h('div', { class: 'bar', style: { marginBottom: '12px' } }, h('i', { style: { width: `${guide.progression * 100}%` } })),
    h('div', { class: 'steps' }, guide.etapes.map((e, i) => h('div', { class: `step ${e.fait ? 'done' : ''}` }, h('div', { class: 'n' }, e.fait ? '✓' : i + 1),
      h('div', {}, h('b', {}, e.titre), h('div', { class: 'small muted' }, e.consigne)), h('span', { class: 'small muted' }, e.minimum ? `${Math.min(e.lus, 99)}/${e.minimum}` : (e.lus ? `${e.lus} lecture(s)` : ''))))),
    h('div', { class: 'row', style: { marginTop: '12px' } }, h('button', { class: 'btn ghost', onclick: () => act(() => api.post('/api/scan-guide/start'), 'Compteurs remis à zéro : visitez les écrans dans FM') }, 'Recommencer le scan'),
      h('span', { class: 'small muted' }, 'Ensuite, rien à faire : chaque écran que vous ouvrez en jouant met la base à jour.')));
  root.append(h('div', { class: 'grid g2', style: { marginBottom: '16px' } }, statusCard, guideCard));

  // ---- Calibrage : ce que j'ai lu
  root.append(calibration(last, st, act));

  // ---- Journal
  root.append(h('div', { class: 'card', style: { marginTop: '16px' } }, h('h2', {}, 'Journal des lectures'),
    scans.lectures.length ? h('div', { class: 'table-wrap', style: { maxHeight: '320px' } }, h('table', { class: 'data' },
      h('thead', {}, h('tr', {}, ['Heure', 'Date de jeu', 'Lecture', 'Source', 'Correction'].map(x => h('th', {}, x)))),
      h('tbody', {}, scans.lectures.map(s => h('tr', {}, h('td', { class: 'muted' }, (s.at || '').replace('T', ' ')), h('td', {}, fmt.date(s.game_date)), h('td', {}, s.summary || s.screen), h('td', { class: 'muted' }, s.source),
        h('td', {}, ['effectif', 'recherche', 'shortlist'].includes(s.screen) ? h('select', { title: 'Si cette liste n\'était pas la bonne (ex. effectif d\'un adversaire), reclassez les joueurs créés par cette lecture', onchange: (e) => e.target.value && act(() => api.post(`/api/scans/${s.id}/reassign`, { scope: e.target.value }), 'Joueurs reclassés') },
          h('option', { value: '' }, 'Reclasser…'), h('option', { value: 'effectif' }, 'C\'est mon effectif'), h('option', { value: 'autre' }, 'C\'est un autre club'), h('option', { value: 'cible' }, 'Ce sont des cibles')) : null))))))
      : h('div', { class: 'muted' }, 'Aucune lecture pour l\'instant.')));
}

function calibration(last, st, act) {
  if (!last.disponible) {
    return h('div', { class: 'card' }, h('h2', {}, 'Calibrage — ce que j\'ai lu'), empty('🎯', 'Aucune capture pour l\'instant',
      st.plateforme_ok ? 'Dès que FM sera au premier plan, la dernière capture apparaîtra ici avec les textes reconnus, pour vérification et correction.'
        : 'La lecture en direct nécessite Windows. Vous pouvez tout de même importer une capture d\'écran de FM (bouton « Importer une capture… ») pour tester la lecture.'));
  }
  const L = last.lecture, cal = last.calibrage, img = last.image;
  const correct = (body, msg) => act(async () => { await api.post('/api/calibration/correction', body); await api.post('/api/capture/reparse', {}); }, msg);
  const shot = h('div', { class: 'shot' }, h('img', { src: `/api/capture/last.png?t=${st.lectures}-${Date.now()}`, alt: 'Dernière capture' }));
  const drawBoxes = () => { shot.querySelectorAll('.tok').forEach(x => x.remove()); if (showBoxes) for (const t of last.tokens) shot.append(h('div', { class: `tok ${t.c < 0.75 ? 'lowc' : ''}`, title: `« ${t.t} » (confiance ${Math.round(t.c * 100)} %)`, style: { left: `${t.x / img.w * 100}%`, top: `${t.y / img.h * 100}%`, width: `${t.w / img.w * 100}%`, height: `${t.h / img.h * 100}%` } })); };
  drawBoxes();
  const screenSel = h('select', { onchange: (e) => e.target.value && act(() => api.post('/api/capture/reparse', { ecran: e.target.value }), 'Écran relu avec le type choisi') }, h('option', { value: '' }, 'Ce n\'est pas le bon écran…'), last.ecrans.map(s => h('option', { value: s.id }, s.nom)));
  const learnSel = h('select', {}, last.ecrans.map(s => h('option', { value: s.id, selected: s.id === L.screen }, s.nom)));
  const right = h('div', { class: 'calib-cols' },
    h('div', {}, h('div', { class: 'row' }, h('span', { class: 'muted' }, 'Écran reconnu :'), h('b', { style: { fontSize: '16px' } }, L.screen_name), L.screen ? tag(`confiance ${Math.round(L.confidence * 100)} %`, L.confidence >= 0.5 ? 'good' : 'mid') : tag('non reconnu', 'bad'), screenSel),
      h('div', { class: 'small muted', style: { marginTop: '4px' } }, `${L.resume || ''} · ${L.n_tokens} mots lus · date de jeu ${L.game_date ? fmt.date(L.game_date) : 'non lue sur cet écran'}`)),
    (L.warnings || []).length ? h('div', { class: 'stack', style: { gap: '6px' } }, L.warnings.map(w => h('div', { class: 'alert orange' }, w))) : null,
    h('div', {}, h('h2', {}, 'Apprendre à reconnaître cet écran'), h('div', { class: 'small muted', style: { marginBottom: '6px' } }, 'Si l\'écran est mal reconnu (skin, autre langue), choisissez son type puis cliquez le texte du haut de l\'écran qui l\'identifie :'),
      h('div', { class: 'row' }, learnSel, (L.titles || []).slice(0, 14).map(t => h('span', { class: 'chip click', onclick: () => correct({ type: 'titre', ecran: learnSel.value, texte: t }, `« ${t} » identifie désormais cet écran`) }, t))),
      Object.entries(cal.titres || {}).some(([, v]) => v.length) ? h('div', { class: 'row small', style: { marginTop: '6px' } }, h('span', { class: 'muted' }, 'Repères appris :'), Object.entries(cal.titres).flatMap(([sc, list]) => list.map(t => h('span', { class: 'chip on click', title: 'Cliquer pour oublier ce repère', onclick: () => correct({ type: 'titre_suppr', ecran: sc, texte: t }, 'Repère oublié') }, `${t} → ${last.ecrans.find(x => x.id === sc)?.nom || sc} ✕`)))) : null),
    (L.headers || []).length ? h('div', {}, h('h2', {}, 'Colonnes du tableau'), h('div', { class: 'small muted', style: { marginBottom: '6px' } }, 'Associez un champ aux en-têtes non reconnus (ou corrigez une association) :'),
      h('div', { class: 'row' }, L.headers.map(hd => h('label', { class: 'chip', style: { padding: '4px 6px 4px 10px', borderColor: hd.champ ? 'var(--line)' : 'var(--mid)' } }, hd.texte,
        h('select', { style: { padding: '2px 6px' }, onchange: (e) => correct({ type: 'colonne', texte: hd.texte, champ: e.target.value }, 'Colonne associée') },
          h('option', { value: '' }, hd.champ?.startsWith('attr:') ? 'attribut' : '— ignorée —'), last.champs.map(c => h('option', { value: c, selected: c === hd.champ }, CHAMPS[c] || c))))))) : null,
    (L.players || []).length ? h('div', {}, h('h2', {}, `Joueurs lus (${L.players.length})`, h('span', { class: 'right small muted' }, 'cliquez un nom mal lu pour le corriger')),
      h('div', { class: 'table-wrap', style: { maxHeight: '260px' } }, h('table', { class: 'data' },
        h('thead', {}, h('tr', {}, ['Nom', 'Âge', 'Poste', 'Valeur', 'Salaire', 'Contrat', 'Niv.', 'Pot.', 'Attributs'].map(x => h('th', {}, x)))),
        h('tbody', {}, L.players.map(p => h('tr', {},
          h('td', {}, h('span', { style: { cursor: 'text', borderBottom: '1px dashed var(--faint)' }, onclick: (e) => { const v = prompt(`Nom correct pour « ${p.name} » ?\n(la correction sera appliquée à chaque prochaine lecture)`, p.name); if (v && v !== p.name) correct({ type: 'texte', lu: p.name, correct: v }, 'Correction mémorisée'); } }, p.name)),
          h('td', {}, p.age ?? '—'), h('td', {}, p.positions || '—'), h('td', {}, fmt.money(p.value)), h('td', {}, fmt.wage(p.wage)), h('td', {}, fmt.date(p.contract_end)), h('td', {}, p.ability_stars ?? '—'), h('td', {}, p.potential_stars ?? '—'), h('td', {}, Object.keys(p.attributes || {}).length || '—'))))))) : null,
    L.doc ? h('div', {}, h('h2', {}, 'Données lues'), h('pre', { class: 'small', style: { background: 'var(--panel-2)', padding: '10px', borderRadius: '8px', maxHeight: '220px', overflow: 'auto', margin: 0, whiteSpace: 'pre-wrap' } }, JSON.stringify(L.doc[1], null, 1))) : null,
    h('div', {}, h('h2', {}, 'Réglages fins'),
      h('div', { class: 'row', style: { alignItems: 'flex-end' } },
        h('label', { class: 'field' }, 'Agrandissement avant lecture', h('select', { onchange: (e) => act(async () => { await api.put('/api/calibration', { echelle_ocr: Number(e.target.value) }); await api.post('/api/capture/reparse', {}); }, 'Agrandissement appliqué') }, [[0, 'Automatique'], [1, '×1 (grand écran)'], [1.35, '×1,35'], [1.7, '×1,7'], [2, '×2 (petit texte, zoom 85 %)'], [2.5, '×2,5']].map(([v, l]) => h('option', { value: v, selected: Number(cal.echelle_ocr) === v }, l)))),
        ...[['haut', 'Ignorer en haut (%)'], ['bas', 'en bas (%)'], ['gauche', 'à gauche (%)'], ['droite', 'à droite (%)']].map(([k, l]) => h('label', { class: 'field' }, l, h('input', { class: 'input', type: 'number', min: 0, max: 40, value: Math.round((cal.marges?.[k] || 0) * 100), style: { width: '90px' }, onchange: (e) => act(() => api.put('/api/calibration', { marges: { [k]: Number(e.target.value) / 100 } }), 'Marge enregistrée (appliquée à la prochaine capture)') }))),
        h('button', { class: `btn ${cal.valide ? 'ghost' : ''}`, onclick: () => act(() => api.put('/api/calibration', { valide: true, resolution: [img.w, img.h] }), 'Calibrage validé') }, cal.valide ? '✓ Calibrage validé' : 'La lecture est correcte : valider')),
      Object.keys(cal.remplacements || {}).length ? h('div', { class: 'row small', style: { marginTop: '8px' } }, h('span', { class: 'muted' }, 'Corrections de texte :'), Object.entries(cal.remplacements).map(([k, v]) => h('span', { class: 'chip on click', title: 'Cliquer pour supprimer', onclick: () => correct({ type: 'texte', lu: k, correct: '' }, 'Correction supprimée') }, `${k} → ${v} ✕`))) : null));
  return h('div', { class: 'card' }, h('h2', {}, 'Calibrage — ce que j\'ai lu', h('label', { class: 'right small', style: { cursor: 'pointer' } }, h('input', { type: 'checkbox', checked: showBoxes, onchange: (e) => { showBoxes = e.target.checked; drawBoxes(); } }), ' montrer les textes reconnus')),
    shot, h('div', { class: 'small muted', style: { margin: '6px 0 16px' } }, `Capture ${img.w} × ${img.h} — cadre vert : texte lu, cadre orange : lecture incertaine. Survolez un cadre pour voir le texte reconnu.`), right);
}
