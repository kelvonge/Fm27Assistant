// Appels à l'API locale. Toute erreur devient un message lisible.
async function call(method, url, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) {
    if (body instanceof Blob || body instanceof ArrayBuffer) {
      opt.body = body; opt.headers['Content-Type'] = 'application/octet-stream';
    } else { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  }
  let res;
  try { res = await fetch(url, opt); } catch (e) { throw new Error("L'application ne répond pas. Est-elle toujours ouverte ?"); }
  if (!res.ok) {
    let msg = `Erreur ${res.status}`;
    try { const j = await res.json(); if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch (e) { /* pas de JSON */ }
    throw new Error(msg);
  }
  return res.json();
}
export const api = {
  get: (u) => call('GET', u), post: (u, b) => call('POST', u, b ?? {}), put: (u, b) => call('PUT', u, b),
  patch: (u, b) => call('PATCH', u, b), del: (u) => call('DELETE', u),
};
