"""Enregistrement d'une lecture dans la base : fusion sans doublons + historique."""
from __future__ import annotations

from ..db import Database
from ..textutil import name_key, norm

DOC_KEYS = {"classement": "team", "staff": "name"}


def _merge_rows(old: list[dict], new: list[dict], key) -> list[dict]:
    """Fusionne deux lectures partielles d'une même liste (défilement)."""
    index = {key(r): dict(r) for r in old}
    for r in new:
        k = key(r)
        index[k] = {**index.get(k, {}), **{a: b for a, b in r.items() if b is not None}}
    return list(index.values())


def _other_club_in_titles(db: Database, parsed: dict, my_club: str) -> str | None:
    """Si le titre de l'écran cite une autre équipe connue, ce n'est pas mon effectif."""
    table = db.document("classement")
    if not table or not my_club:
        return None
    titles = " | ".join(norm(t) for t in parsed.get("titles", []))
    if norm(my_club) in titles:
        return None
    for row in table["data"]:
        team = norm(row.get("team"))
        if len(team) >= 4 and team != norm(my_club) and team in titles:
            return row["team"]
    return None


def ingest(db: Database, parsed: dict, source: str = "capture") -> dict:
    """Retourne {scan_id, resume, joueurs, nouveaux}."""
    screen = parsed.get("screen")
    game_date = parsed.get("game_date")
    if game_date:
        db.set_meta("game_date", game_date)
    else:
        game_date = db.game_date()
    if screen is None:
        return {"scan_id": None, "resume": "Écran non reconnu", "joueurs": 0, "nouveaux": 0}
    settings = db.settings()
    scan_id = db.add_scan(screen, game_date, "", source)
    updated = created = 0
    summary = parsed.get("screen_name", screen)
    players = parsed.get("players") or []
    if players:
        scope = None
        club = None
        if screen == "effectif":
            other = _other_club_in_titles(db, parsed, settings.get("club", ""))
            scope, club = ("autre", other) if other else ("effectif", settings.get("club") or None)
        elif screen in ("recherche", "shortlist"):
            scope = "cible"
        for rec in players:
            rec = dict(rec)
            if screen == "shortlist":
                rec["shortlist"] = True
            if club and not rec.get("club"):
                rec["club"] = club
            sc = scope
            if screen == "profil":
                # Profil : on ne change pas le groupe d'un joueur connu ; un inconnu
                # du même club que moi rejoint l'effectif, sinon c'est une cible.
                mine = settings.get("club") and rec.get("club") and norm(rec["club"]) == norm(settings["club"])
                sc = "effectif" if mine else None
            elif sc == "cible" and settings.get("club") and rec.get("club") and norm(rec["club"]) == norm(settings["club"]):
                sc = "effectif"
            try:
                _, was_created = db.upsert_player(rec, sc, scan_id, game_date)
            except ValueError:
                continue
            updated += 1
            created += int(was_created)
        if screen == "profil":
            p = players[0]
            summary = f"Profil joueur – {p.get('name')} ({len(p.get('attributes') or {})} attributs)"
        else:
            summary = f"{parsed.get('screen_name')} – {updated} joueur{'s' if updated > 1 else ''} à jour"
            if created:
                summary += f" (dont {created} nouveau{'x' if created > 1 else ''})"
    doc = parsed.get("doc")
    if doc:
        kind, data = doc
        if kind in DOC_KEYS and isinstance(data, list):
            old = db.document(kind, game_date or "")
            k = DOC_KEYS[kind]
            data = _merge_rows(old["data"] if old else [], data, lambda r: name_key(r.get(k)))
            if kind == "classement":
                data.sort(key=lambda r: (r.get("rank") is None, r.get("rank") or 0, -(r.get("points") or 0)))
        elif kind == "calendrier":
            old = db.document(kind)  # le calendrier couvre toute la saison : fusion entre dates de jeu
            data = _merge_rows(old["data"] if old else [], data, lambda r: (r.get("date"), name_key(r.get("opponent"))))
            data.sort(key=lambda r: r.get("date") or "")
        elif kind == "finances":
            old = db.document(kind, game_date or "")
            data = {**(old["data"] if old else {}), **data}
        db.save_document(kind, data, game_date)
        n = len(data) if isinstance(data, list) else len([v for v in data.values() if v])
        unit = {"classement": "équipes", "calendrier": "matchs", "staff": "membres", "finances": "montants", "tactique": "éléments"}[kind]
        if kind == "tactique":
            n = len(data.get("joueurs") or [])
            summary = f"Tactique – {data.get('formation') or 'formation non lue'}, {n} rôle{'s' if n > 1 else ''} lu{'s' if n > 1 else ''}"
        else:
            summary = f"{parsed.get('screen_name')} – {n} {unit}"
    if not players and not doc:
        summary = f"{parsed.get('screen_name')} – rien de lisible"
    db.update_scan(scan_id, summary)
    return {"scan_id": scan_id, "resume": summary, "joueurs": updated, "nouveaux": created}
