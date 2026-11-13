import { api } from '../api.js';
import { h, toast } from '../ui.js';

const PRESETS = ['#2fd08c', '#4ea3f2', '#ef5a52', '#f2c14e', '#b06cf5', '#ff8a3d', '#e84a8a', '#35c9c9', '#d9dee6'];
export async function render(root, ctx) {
  const [s, kb] = await Promise.all([api.get('/api/settings'), api.get('/api/knowledge')]);
  const save = async (patch, msg = 'Enregistré') => { try { await ctx.setSettings(patch); toast(msg); } catch (e) { toast(e.message, true); } };
  const text = (key, label, ph, hint) => h('label', { class: 'field' }, label, h('input', { class: 'input', value: s[key] || '', placeholder: ph, onchange: (e) => save({ [key]: e.target.value.trim() }) }), hint ? h('span', { class: 'small faint', style: { fontSize: '12px' } }, hint) : null);
  const color = h('input', { type: 'color', value: s.accent, style: { width: '46px', height: '36px', padding: 0, border: 0, background: 'none', cursor: 'pointer' }, oninput: (e) => ctx.setSettings({ accent: e.target.value }) });
  root.append(h('div', { class: 'grid g2' },
    h('div', { class: 'card' }, h('h2', {}, 'Ma carrière'), h('div', { class: 'stack' },
      text('club', 'Club', 'ex. FC Nantes', 'Le nom exact affiché dans le jeu : il sert à vous retrouver dans le classement et à distinguer votre effectif des autres.'),
      text('division', 'Division', 'ex. Ligue 1', 'Sert à comparer votre effectif au niveau habituel du championnat.'),
      text('saison', 'Saison', 'ex. 2026/2027'),
      h('label', { class: 'field' }, 'Style de jeu voulu', h('select', { onchange: (e) => save({ style: e.target.value }) }, h('option', { value: '' }, 'Pas de préférence'), kb.tactiques.map(t => h('option', { value: t.style, selected: t.style === s.style }, t.nom)))),
      text('objectif', 'Objectif de la saison / du board', 'ex. Se qualifier pour l\'Europe'),
      h('label', { class: 'field' }, 'Couleur du club (accent de l\'interface)', h('div', { class: 'row' }, color, PRESETS.map(c => h('span', { title: c, style: { width: '26px', height: '26px', borderRadius: '8px', background: c, cursor: 'pointer', border: '2px solid var(--line)' }, onclick: () => { color.value = c; ctx.setSettings({ accent: c }); } })))))),
    h('div', { class: 'card' }, h('h2', {}, 'Lecture du jeu'), h('div', { class: 'stack' },
      h('label', { class: 'field' }, 'Titre de la fenêtre du jeu (mots recherchés, séparés par des virgules)', h('input', { class: 'input', value: (s.fenetre || []).join(', '), onchange: (e) => save({ fenetre: e.target.value.split(',').map(x => x.trim()).filter(Boolean) }) })),
      h('label', { class: 'field' }, 'Intervalle entre deux captures (secondes)', h('input', { class: 'input', type: 'number', min: 0.3, max: 10, step: 0.1, value: s.intervalle, onchange: (e) => save({ intervalle: Number(e.target.value) || 1 }) })),
      h('label', { class: 'field' }, 'Moteur de lecture (OCR)', h('select', { onchange: (e) => save({ ocr: e.target.value }) }, [['auto', 'Automatique (RapidOCR, sinon OCR Windows)'], ['rapidocr', 'RapidOCR'], ['windows', 'OCR intégré à Windows']].map(([v, l]) => h('option', { value: v, selected: v === s.ocr }, l)))),
      h('label', { class: 'field' }, 'Période des salaires quand le jeu ne la précise pas', h('select', { onchange: (e) => save({ periode_salaire: e.target.value }) }, [['semaine', 'Par semaine'], ['mois', 'Par mois'], ['an', 'Par an']].map(([v, l]) => h('option', { value: v, selected: v === s.periode_salaire }, l)))),
      h('p', { class: 'small muted' }, 'L\'assistant ne fait que photographier la fenêtre du jeu : il ne lit ni ne modifie jamais votre sauvegarde.'))),
    h('div', { class: 'card' }, h('h2', {}, 'Base de connaissances'), h('p', { class: 'muted' }, 'Rôles, attributs clés et poids, profils tactiques, règles d\'incohérence, repères de niveau par division et défis sont dans des fichiers JSON modifiables avec le Bloc-notes.'),
      h('dl', { class: 'kv' }, h('dt', {}, 'Dossier'), h('dd', { style: { wordBreak: 'break-all' } }, kb.dossier), h('dt', {}, 'Contenu'), h('dd', {}, `${kb.roles.length} rôles · ${kb.attributs.length} attributs · ${kb.formations.length} formations · ${kb.tactiques.length} styles`)),
      kb.avertissement ? h('div', { class: 'alert orange', style: { marginTop: '10px' } }, kb.avertissement) : null,
      h('div', { class: 'row', style: { marginTop: '12px' } },
        h('button', { class: 'btn ghost', onclick: () => api.post('/api/open-data-folder') }, 'Ouvrir le dossier de données'),
        h('button', { class: 'btn ghost', onclick: async () => { const r = await api.post('/api/knowledge/reload'); toast(r.avertissements.length ? r.avertissements[0] : 'Fichiers rechargés', r.avertissements.length > 0); ctx.refresh(); } }, 'Recharger après modification'))),
    h('div', { class: 'card' }, h('h2', {}, 'Données'), h('p', { class: 'muted' }, 'Tout est stocké sur ce PC dans une base SQLite. Rien n\'est envoyé sur Internet.'),
      h('div', { class: 'row' },
        h('button', { class: 'btn ghost', onclick: async () => { if (confirm('Remplacer les données actuelles par la carrière de démonstration ?')) { await api.post('/api/demo/load'); location.hash = '#/dashboard'; location.reload(); } } }, 'Charger la démonstration'),
        h('button', { class: 'btn danger', onclick: async () => { if (confirm('Effacer tous les joueurs et documents lus ? Les réglages et le calibrage sont conservés.')) { await api.post('/api/data/reset'); toast('Données effacées'); location.reload(); } } }, 'Tout effacer')),
      h('p', { class: 'small faint', style: { marginTop: '14px' } }, `FM Assistant 27 – version ${ctx.status?.version || ''} · 100 % local et gratuit`))));
}
