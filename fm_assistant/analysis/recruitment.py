"""Recrutement : besoins de l'effectif, recherche ciblée, rapport qualité/prix, pépites."""
from __future__ import annotations

import math
from statistics import mean

from ..textutil import fmt_money
from .knowledge import KB
from .ratings import explain, roles_for_player, score_role, stars_estimate
from .squad import depth


def needs(enriched: list[dict], kb: KB, ref: float | None, game_date: str | None) -> list[dict]:
    """Profils prioritaires d'après les trous de l'effectif."""
    out = []
    for d in depth(enriched, kb, ref):
        if not d["principal"]:
            continue
        prio, why = None, d["message"]
        if d["statut"] in ("trou", "faible"):
            prio = 1
        elif d["statut"] == "juste":
            prio = 2
        starters = [c for c in d["joueurs"][:1] if c.get("age")]
        if prio is None and starters and starters[0]["age"] >= 31:
            prio, why = 3, f"Titulaire vieillissant ({starters[0]['name']}, {starters[0]['age']} ans) : préparez la relève."
        if prio is None:
            continue
        roles = [kb.roles[r]["nom"] for r in kb.roles_by_pos.get(d["poste"], [])[:4]]
        out.append({"poste": d["poste"], "label": d["label"], "nom": d["nom"], "priorite": prio, "raison": why,
                    "niveau_vise": round(ref, 1) if ref else None, "roles": roles})
    out.sort(key=lambda n: n["priorite"])
    return out


def _price_model(rows: list[tuple[float, float]]):
    """Régression note ~ a + b·log10(prix) sur les joueurs lus : sert d'étalon du marché."""
    if len(rows) < 8:
        return None
    xs = [math.log10(max(v, 1000)) for _, v in rows]
    ys = [n for n, _ in rows]
    mx, my = mean(xs), mean(ys)
    var = sum((x - mx) ** 2 for x in xs)
    if var < 1e-6:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    return (my - b * mx, b)


def search(pool: list[dict], crit: dict, kb: KB, ref: float | None) -> dict:
    """Classe les joueurs lus dans le jeu selon un besoin précis.

    crit : poste, role, age_max, age_min, valeur_max, salaire_max, note_min, shortlist.
    """
    pos, role_id = crit.get("poste") or None, crit.get("role") or None
    if role_id and role_id not in kb.roles:
        role_id = None
    results, hidden = [], {"sans_donnees": 0}
    for p in pool:
        if crit.get("shortlist") and not p.get("shortlist"):
            continue
        ppos = p.get("pos") or []
        if pos and pos not in ppos:
            continue
        if role_id and ppos and not set(kb.roles[role_id]["postes"]) & set(ppos):
            continue
        age = p.get("age")
        if crit.get("age_max") and (age is None or age > crit["age_max"]):
            if age is None:
                hidden["sans_donnees"] += 1
            continue
        if crit.get("age_min") and (age is None or age < crit["age_min"]):
            continue
        if crit.get("valeur_max") and p.get("value") is not None and p["value"] > crit["valeur_max"]:
            continue
        if crit.get("salaire_max") and p.get("wage") is not None and p["wage"] > crit["salaire_max"]:
            continue
        if role_id:
            sc = score_role(p.get("attributes"), role_id, kb)
        else:
            lst = roles_for_player(p, kb, [pos] if pos else None)
            sc = lst[0] if lst else None
        if sc:
            note, source, why = sc["note"], "attributs" if sc["fiable"] else "partielle", explain(p, sc)
        else:
            note = stars_estimate(p.get("ability_stars"), ref)
            source = "etoiles" if note is not None else None
            why = (f"Attributs non lus : note estimée d'après ses {p['ability_stars']:g} étoile(s), à confirmer en ouvrant son profil."
                   if note is not None else "Ni attributs ni étoiles lus : ouvrez son profil dans FM pour l'évaluer.")
        if crit.get("note_min") and (note is None or note < crit["note_min"]):
            continue
        results.append({
            "id": p["id"], "name": p["name"], "age": age, "club": p.get("club"), "positions": p.get("positions"),
            "postes": [kb.pos_label(x) for x in ppos], "value": p.get("value"), "wage": p.get("wage"),
            "contract_end": p.get("contract_end"), "ability_stars": p.get("ability_stars"),
            "potential_stars": p.get("potential_stars"), "shortlist": p.get("shortlist"), "note_perso": p.get("note_perso"),
            "note": note, "source": source, "role_nom": sc["nom"] if sc else None, "explication": why,
            "ecart_niveau": round(note - ref, 1) if note is not None and ref is not None else None,
        })
    model = _price_model([(r["note"], r["value"]) for r in results if r["note"] is not None and r["value"]])
    for r in results:
        r["qualite_prix"] = None
        if model and r["note"] is not None and r["value"]:
            expected = model[0] + model[1] * math.log10(max(r["value"], 1000))
            r["qualite_prix"] = round(r["note"] - expected, 2)
            if r["qualite_prix"] >= 0.8:
                r["explication"] += f" Bonne affaire : +{r['qualite_prix']:.1f} pt par rapport aux joueurs lus du même prix ({fmt_money(r['value'])})."
        elif r["note"] is not None and r["value"] == 0:
            r["qualite_prix"] = 3.0  # joueur libre
    results.sort(key=lambda r: (r["note"] is None, -(r["note"] or 0)))
    msg = None
    if not pool:
        msg = "Aucun joueur extérieur lu pour l'instant : ouvrez la recherche de joueurs ou votre shortlist dans FM."
    elif not model and len(results) >= 2:
        msg = "Rapport qualité/prix indisponible : il faut au moins 8 joueurs avec une note et une valeur lues."
    return {"resultats": results, "total": len(results), "message": msg, "reference": ref}


def gems(pool: list[dict], kb: KB, ref: float | None) -> list[dict]:
    """Pépites : jeunes au potentiel élevé ou déjà proches du niveau de l'équipe."""
    out = []
    for p in pool:
        age = p.get("age")
        if age is None or age > 21:
            continue
        lst = roles_for_player(p, kb)
        note = lst[0]["note"] if lst and lst[0]["fiable"] else None
        pot, cur = p.get("potential_stars"), p.get("ability_stars")
        reasons = []
        if pot is not None and pot >= 4:
            reasons.append(f"potentiel {pot:g}★")
        if pot is not None and cur is not None and pot - cur >= 1.5:
            reasons.append(f"marge de progression de {pot - cur:g}★")
        if note is not None and ref is not None and note >= ref - 1.5:
            reasons.append(f"déjà à {note:.1f}/20 à {age} ans (onze type : {ref:.1f})")
        if not reasons:
            continue
        out.append({"id": p["id"], "name": p["name"], "age": age, "club": p.get("club"), "value": p.get("value"),
                    "postes": [kb.pos_label(x) for x in p.get("pos") or []], "note": note, "potential_stars": pot,
                    "role_nom": lst[0]["nom"] if lst else None, "raison": "Pépite : " + ", ".join(reasons) + "."})
    out.sort(key=lambda g: (-(g["potential_stars"] or 0), -(g["note"] or 0)))
    return out[:20]
