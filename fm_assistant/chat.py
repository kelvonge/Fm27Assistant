"""Chat optionnel avec un modèle local via Ollama (http://127.0.0.1:11434).

Aucune donnée ne quitte le PC. Si Ollama n'est pas installé ou ne tourne
pas, le module est simplement masqué dans l'interface.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .textutil import fmt_money

OLLAMA = "http://127.0.0.1:11434"


def _get(path: str, timeout: float = 0.7):
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def status() -> dict:
    try:
        tags = _get("/api/tags")
    except (urllib.error.URLError, OSError, ValueError):
        return {"disponible": False, "modeles": []}
    models = [m.get("name") for m in tags.get("models", []) if m.get("name")]
    return {"disponible": bool(models), "modeles": models, "ollama": True}


def build_context(enriched: list[dict], settings: dict, game_date: str | None, finances: dict | None,
                  tactic: dict | None, table_row: dict | None, alerts: list[dict]) -> str:
    """Résumé compact des données lues, fourni au modèle comme seule source."""
    lines = [
        "Tu es l'assistant de carrière Football Manager de l'utilisateur. Réponds en français, de façon concise et concrète.",
        "Appuie-toi UNIQUEMENT sur les données ci-dessous, lues dans sa partie. Si une information manque, dis-le clairement au lieu d'inventer.",
        f"Club : {settings.get('club') or 'non renseigné'} | Division : {settings.get('division') or 'non renseignée'} | "
        f"Saison : {settings.get('saison') or '?'} | Date de jeu : {game_date or 'inconnue'} | Style voulu : {settings.get('style') or 'non précisé'}",
    ]
    if table_row:
        lines.append(f"Classement : {table_row.get('rank')}e, {table_row.get('points')} pts en {table_row.get('played')} matchs.")
    if finances:
        lines.append("Finances : " + ", ".join(f"{k}={fmt_money(v)}" for k, v in finances.items() if v is not None))
    if tactic:
        lines.append(f"Tactique lue : {tactic.get('formation')} | mentalité {tactic.get('mentalite')} | consignes : {', '.join(tactic.get('instructions') or [])}")
    lines.append("Effectif (nom | âge | postes | meilleur rôle et note /20 | valeur | salaire hebdo | fin de contrat) :")
    for p in sorted(enriched, key=lambda p: -((p.get('analyse') or {}).get('note') or 0)):
        an = p.get("analyse") or {}
        note = f"{an.get('role_nom')} {an['note']:.1f}" if an.get("note") is not None and an.get("role_nom") else "non évalué"
        lines.append(f"- {p['name']} | {p.get('age') or '?'} | {'/'.join(an.get('postes') or []) or '?'} | {note} | "
                     f"{fmt_money(p.get('value'))} | {fmt_money(p.get('wage'))} | {p.get('contract_end') or '?'}"
                     + (" | BLESSÉ" if p.get("injury") else ""))
    if alerts:
        lines.append("Alertes actuelles : " + " ; ".join(a["texte"] for a in alerts[:8]))
    return "\n".join(lines)


def chat(model: str, context: str, messages: list[dict], timeout: float = 180) -> str:
    payload = {"model": model, "stream": False, "options": {"temperature": 0.3},
               "messages": [{"role": "system", "content": context}] + messages[-12:]}
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data.get("message") or {}).get("content", "").strip()
