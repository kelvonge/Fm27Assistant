import { api } from '../api.js';
import { h, empty, toast } from '../ui.js';

const history = [];
export async function render(root, ctx) {
  const st = await api.get('/api/chat/status');
  if (!st.disponible) { root.append(h('div', { class: 'card' }, empty('💬', 'Chat local indisponible', 'Ollama n\'est pas lancé sur ce PC ou aucun modèle n\'est installé. Le guide d\'installation explique comment l\'ajouter (facultatif, gratuit, hors ligne).'))); return; }
  const log = h('div', { class: 'chat-log' });
  const draw = () => { log.replaceChildren(...(history.length ? history.map(m => h('div', { class: `msg ${m.role === 'user' ? 'user' : 'bot'}` }, m.content)) : [h('div', { class: 'muted', style: { margin: 'auto', textAlign: 'center', maxWidth: '520px' } }, 'Posez une question sur votre carrière : « Qui vendre cet hiver ? », « Quel milieu titulariser ? »… Le modèle local répond uniquement à partir des données lues dans votre partie. Rien ne sort de votre PC.')])); log.scrollTop = log.scrollHeight; };
  const model = h('select', { onchange: (e) => ctx.setSettings({ modele_chat: e.target.value }) }, st.modeles.map(m => h('option', { value: m, selected: m === ctx.settings.modele_chat }, m)));
  const input = h('input', { class: 'input', placeholder: 'Votre question…', style: { flex: 1 } });
  const send = async () => {
    const q = input.value.trim(); if (!q) return;
    input.value = ''; history.push({ role: 'user', content: q }); draw();
    const wait = h('div', { class: 'msg bot muted' }, 'Le modèle réfléchit… (cela peut prendre un moment sur un PC sans carte graphique)'); log.append(wait); log.scrollTop = log.scrollHeight;
    try { const r = await api.post('/api/chat', { modele: model.value, messages: history }); history.push({ role: 'assistant', content: r.reponse }); }
    catch (e) { toast(e.message, true); history.pop(); input.value = q; }
    draw();
  };
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
  draw();
  root.append(h('div', { class: 'card chat' }, h('div', { class: 'row', style: { marginBottom: '10px' } }, h('span', { class: 'muted small' }, 'Modèle'), model, h('span', { class: 'spacer' }), h('button', { class: 'btn ghost small', onclick: () => { history.length = 0; draw(); } }, 'Effacer')), log, h('div', { class: 'row', style: { flexWrap: 'nowrap' } }, input, h('button', { class: 'btn', onclick: send }, 'Envoyer'))));
}
