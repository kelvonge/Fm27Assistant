"""Développement des jeunes : plan de progression et prêts conseillés."""
from __future__ import annotations

from ..textutil import fr
from .knowledge import KB
from .ratings import roles_for_player
from .squad import depth


def youth_plan(enriched: list[dict], kb: KB, ref: float | None, max_age: int = 21) -> dict:
    ranks: dict[int, int] = {}
    for d in depth(enriched, kb, ref):
        for i, c in enumerate(d["joueurs"]):
            ranks[c["id"]] = min(ranks.get(c["id"], 99), i + 1)
    training = kb.raw.get("entrainement", {})
    out, unknown_age = [], 0
    for p in enriched:
        age = p.get("age")
        if age is None:
            unknown_age += 1
            continue
        if age > max_age:
            continue
        roles = roles_for_player(p, kb)
        best = roles[0] if roles else None
        note = best["note"] if best and best["fiable"] else None
        pot, cur = p.get("potential_stars"), p.get("ability_stars")
        item = {"id": p["id"], "name": p["name"], "age": age, "postes": [kb.pos_label(x) for x in p.get("pos") or []],
                "note": note, "role_nom": best["nom"] if best else None, "ability_stars": cur, "potential_stars": pot,
                "rang_poste": ranks.get(p["id"]), "axes": [], "decision": None, "raison": None}
        if best:
            weights = kb.weights(best["role"])
            attrs = p["attributes"]
            keys = sorted((a for a in weights if weights[a] >= kb.w_key and a in attrs), key=lambda a: attrs[a])
            for a in keys[:3]:
                item["axes"].append({"attr": a, "nom": kb.attr_name(a), "val": attrs[a],
                                     "travail": training.get(a, "Entraînement individuel ciblé")})
            item["plan"] = (f"Former comme {best['nom']} (entraînement individuel sur ce rôle). Priorités : "
                            + ", ".join(f"{x['nom']} ({x['val']})" for x in item["axes"]) + ".") if item["axes"] else None
        else:
            item["plan"] = None
        gap = ref - note if note is not None and ref is not None else None
        rank = ranks.get(p["id"], 99)
        if gap is None:
            item["decision"], item["raison"] = "à évaluer", "Attributs non lus : ouvrez son profil dans FM pour obtenir un plan."
        elif gap <= 1.0:
            item["decision"] = "intégrer"
            item["raison"] = f"Déjà au niveau du groupe ({fr(note)} pour un onze type à {fr(ref)}) : donnez-lui du temps de jeu en équipe première."
        elif age <= 17:
            item["decision"] = "garder"
            item["raison"] = f"Trop jeune pour un prêt utile ({age} ans) : équipe de jeunes, mentor et entraînement individuel."
        elif gap <= 2.5 and rank <= 2:
            item["decision"] = "rotation"
            item["raison"] = f"Doublure crédible ({fr(note)}) : remplaçant et matchs de coupe, plutôt qu'un prêt."
        else:
            item["decision"] = "prêt"
            item["raison"] = (f"À {fr(note)} pour un onze type à {fr(ref)} et {rank if rank < 99 else 'loin'}e choix à son poste, "
                              "il ne jouera pas ici : un prêt avec statut de titulaire accélérera sa progression.")
            if pot is not None and pot < 3:
                item["raison"] += f" Potentiel limité ({pot:g}★) : envisagez une vente avec pourcentage à la revente."
        out.append(item)
    order = {"intégrer": 0, "rotation": 1, "prêt": 2, "garder": 3, "à évaluer": 4}
    out.sort(key=lambda x: (order[x["decision"]], -(x["potential_stars"] or 0), -(x["note"] or 0)))
    msg = None
    if not out:
        msg = "Aucun jeune de 21 ans ou moins dans l'effectif lu." + (f" ({unknown_age} joueur(s) sans âge lu.)" if unknown_age else "")
    return {"jeunes": out, "message": msg, "reference": ref, "age_inconnu": unknown_age}
