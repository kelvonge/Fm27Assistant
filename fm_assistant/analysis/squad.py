"""Analyse de l'effectif : niveau de référence, profondeur par poste, forces et faiblesses."""
from __future__ import annotations

from statistics import mean

from ..textutil import fr
from .knowledge import AXES_JOUEUR, KB
from .ratings import best_role_at, enrich

POS_ORDER = ["GK", "DR", "DC", "DL", "WBR", "WBL", "DM", "MC", "MR", "ML", "AMR", "AMC", "AML", "ST"]
CORE_POS = ["GK", "DR", "DC", "DL", "DM", "MC", "AMR", "AMC", "AML", "ST"]


def reliable_note(p: dict) -> float | None:
    an = p.get("analyse") or {}
    return an.get("note") if an.get("source") == "attributs" and an.get("fiable") else None


def reference_level(enriched: list[dict]) -> float | None:
    """Niveau du onze type : moyenne des 11 meilleures notes fiables."""
    notes = sorted((n for n in (reliable_note(p) for p in enriched) if n is not None), reverse=True)
    if len(notes) < 5:
        return None
    return round(mean(notes[:11]), 2)


def enrich_all(players: list[dict], kb: KB) -> tuple[list[dict], float | None]:
    first = [enrich(p, kb) for p in players]
    ref = reference_level(first)
    return [enrich(p, kb, ref) for p in players], ref


def depth(enriched: list[dict], kb: KB, ref: float | None) -> list[dict]:
    """Pour chaque poste : joueurs classés par note à ce poste + diagnostic."""
    out = []
    for pos in POS_ORDER:
        cands = []
        for p in enriched:
            if pos not in (p.get("pos") or []):
                continue
            sc = best_role_at(p, pos, kb)
            cands.append({
                "id": p["id"], "name": p["name"], "age": p.get("age"),
                "note": sc["note"] if sc and sc["fiable"] else None, "role": sc["nom"] if sc else None,
                "blesse": bool(p.get("injury")),
            })
        cands.sort(key=lambda c: -(c["note"] or 0))
        rated = [c for c in cands if c["note"] is not None]
        if not cands:
            if pos not in CORE_POS:
                continue
            status, msg = "trou", "Aucun joueur lu à ce poste."
        elif not rated:
            status, msg = "inconnu", "Joueurs présents mais attributs non lus : ouvrez leurs profils."
        elif ref is None:
            status, msg = "inconnu", "Niveau de référence indisponible."
        else:
            good = [c for c in rated if c["note"] >= ref - 1.0]
            if len(good) >= 2:
                status, msg = "solide", f"{len(good)} joueurs au niveau du onze type."
            elif len(good) == 1 and len(rated) >= 2:
                status, msg = "juste", "Un seul joueur au niveau ; la doublure est en dessous."
            elif len(good) == 1:
                status, msg = "juste", "Un titulaire au niveau mais aucune doublure."
            else:
                status, msg = "faible", f"Meilleur joueur à {fr(rated[0]['note'])}, sous le niveau du onze type ({fr(ref)})."
        out.append({"poste": pos, "label": kb.pos_label(pos), "nom": kb.pos_names.get(pos, pos),
                    "joueurs": cands, "statut": status, "message": msg, "principal": pos in CORE_POS})
    return out


def team_attributes(enriched: list[dict], top: int = 18) -> dict[str, float]:
    """Moyenne de chaque attribut sur les meilleurs joueurs de champ."""
    field = [p for p in enriched if p.get("attributes") and "GK" not in (p.get("pos") or [])]
    field.sort(key=lambda p: -(reliable_note(p) or 0))
    sums: dict[str, list[float]] = {}
    for p in field[:top]:
        for a, v in p["attributes"].items():
            if isinstance(v, (int, float)):
                sums.setdefault(a, []).append(v)
    return {a: round(mean(v), 2) for a, v in sums.items() if len(v) >= 3}


def strengths(enriched: list[dict], kb: KB) -> dict:
    means = team_attributes(enriched)
    means = {a: v for a, v in means.items() if a in kb.attrs and kb.attrs[a]["categorie"] != "gardien"
             and a not in ("corners", "free_kicks", "penalties", "long_throws")}
    if len(means) < 8:
        return {"forts": [], "faibles": [], "radar": None, "moyenne": None}
    avg = mean(means.values())
    ranked = sorted(means.items(), key=lambda kv: -kv[1])
    fmt = lambda kv: {"attr": kv[0], "nom": kb.attr_name(kv[0]), "val": kv[1], "ecart": round(kv[1] - avg, 1)}
    axes = []
    for label, keys in AXES_JOUEUR:
        vals = [means[k] for k in keys if k in means]
        axes.append({"axe": label, "val": round(mean(vals), 1) if vals else None})
    return {"forts": [fmt(x) for x in ranked[:5]], "faibles": [fmt(x) for x in ranked[-5:][::-1]],
            "radar": {"axes": axes}, "moyenne": round(avg, 2)}


def division_benchmark(division: str, kb: KB) -> dict | None:
    d = (division or "").lower()
    if not d:
        return None
    best = None
    for lvl in kb.raw.get("niveaux_division", []):
        for kw in lvl.get("mots_cles", []):
            if kw in d and (best is None or len(kw) > best[0]):
                best = (len(kw), lvl)
    return best[1] if best else None
