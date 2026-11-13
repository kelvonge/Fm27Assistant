"""Notes par rôle : moyenne pondérée des attributs lus, avec explication en clair.

Une note n'est calculée qu'à partir d'attributs réellement lus. « couverture »
indique la part (pondérée) des attributs du rôle qui étaient disponibles ; en
dessous du seuil de la base de connaissances, la note est marquée non fiable.
"""
from __future__ import annotations

from ..textutil import fr
from .knowledge import AXES_GARDIEN, AXES_JOUEUR, KB


def score_role(attrs: dict | None, role_id: str, kb: KB) -> dict | None:
    if not attrs:
        return None
    weights = kb.weights(role_id)
    total_w = sum(weights.values())
    num = den = 0.0
    details = []
    for a, w in weights.items():
        v = attrs.get(a)
        if isinstance(v, (int, float)):
            num += v * w
            den += w
            details.append((a, v, w))
    if den == 0 or total_w == 0:
        return None
    coverage = den / total_w
    role = kb.roles[role_id]
    details.sort(key=lambda d: (-d[1], -d[2]))
    keys = [d for d in details if d[2] >= kb.w_key]
    return {
        "role": role_id, "nom": role["nom"], "note": round(num / den, 2), "couverture": round(coverage, 2),
        "fiable": coverage >= kb.min_coverage,
        "forts": [{"attr": a, "nom": kb.attr_name(a), "val": v} for a, v, _ in (keys or details)[:3]],
        "faibles": [{"attr": a, "nom": kb.attr_name(a), "val": v} for a, v, _ in sorted(keys or details, key=lambda d: d[1])[:2]],
        "manquants": [kb.attr_name(a) for a in weights if a not in attrs],
    }


def roles_for_player(player: dict, kb: KB, positions: list[str] | None = None) -> list[dict]:
    """Toutes les notes de rôle d'un joueur à ses postes (ou aux postes demandés), triées."""
    attrs = player.get("attributes")
    if not attrs:
        return []
    pos = positions if positions is not None else (player.get("pos") or [])
    role_ids: list[str] = []
    for p in pos:
        for r in kb.roles_by_pos.get(p, []):
            if r not in role_ids:
                role_ids.append(r)
    if not pos:  # poste inconnu : gardien si attributs de gardien, sinon tous les rôles de champ
        gk = "reflexes" in attrs or "handling" in attrs
        role_ids = [r for r, obj in kb.roles.items() if ("GK" in obj["postes"]) == gk]
    scores = [s for s in (score_role(attrs, r, kb) for r in role_ids) if s]
    scores.sort(key=lambda s: (-int(s["fiable"]), -s["note"]))
    return scores


def best_role_at(player: dict, pos: str, kb: KB) -> dict | None:
    scores = roles_for_player(player, kb, [pos])
    return scores[0] if scores else None


def stars_estimate(stars: float | None, ref: float | None) -> float | None:
    """Note approximative d'après les étoiles : 3★ ≈ niveau moyen du onze type.

    Les étoiles de FM sont relatives à votre effectif, d'où le besoin d'une référence.
    """
    if stars is None or ref is None:
        return None
    return round(max(1.0, min(20.0, ref + (stars - 3.0) * 1.2)), 2)


def explain(player: dict, score: dict, alt: dict | None = None) -> str:
    """« X convient mieux en Meneur de jeu reculé car Passes 16, Vision du jeu 15, Sang-froid 14 »."""
    name = player.get("name", "Ce joueur")
    forts = ", ".join(f"{f['nom']} {f['val']}" for f in score["forts"])
    if alt and alt["role"] != score["role"] and score["note"] - alt["note"] >= 0.3:
        txt = f"{name} convient mieux en {score['nom']} ({fr(score['note'])}) qu'en {alt['nom']} ({fr(alt['note'])}) car {forts}"
    else:
        txt = f"{name} est le plus à l'aise en {score['nom']} ({fr(score['note'])}/20) car {forts}"
    low = [f for f in score["faibles"] if f["val"] <= score["note"] - 2]
    if low:
        txt += " ; point faible pour ce rôle : " + ", ".join(f"{f['nom']} {f['val']}" for f in low)
    if not score["fiable"]:
        txt += f" (note partielle : {int(score['couverture'] * 100)} % des attributs du rôle ont été lus)"
    return txt + "."


def radar(player: dict) -> dict | None:
    attrs = player.get("attributes") or {}
    if not attrs:
        return None
    axes = AXES_GARDIEN if "GK" in (player.get("pos") or []) or ("reflexes" in attrs and "tackling" not in attrs) else AXES_JOUEUR
    out = []
    for label, keys in axes:
        vals = [attrs[k] for k in keys if isinstance(attrs.get(k), (int, float))]
        out.append({"axe": label, "val": round(sum(vals) / len(vals), 1) if vals else None})
    return {"axes": out} if any(a["val"] is not None for a in out) else None


def enrich(player: dict, kb: KB, ref: float | None = None, full: bool = False) -> dict:
    """Ajoute le bloc « analyse » à une fiche joueur."""
    p = dict(player)
    scores = roles_for_player(player, kb)
    best = scores[0] if scores else None
    an: dict = {"postes": [kb.pos_label(x) for x in player.get("pos") or []]}
    if best:
        an.update(note=best["note"], role=best["role"], role_nom=best["nom"], fiable=best["fiable"],
                  couverture=best["couverture"], source="attributs")
        approx = [k for k, v in (player.get("attr_source") or {}).items() if v != "exact"]
        if approx:
            an["approx"] = len(approx)
    else:
        est = stars_estimate(player.get("ability_stars"), ref)
        an.update(note=est, role=None, role_nom=None, fiable=False, couverture=0,
                  source="etoiles" if est is not None else None)
    if full:
        an["roles"] = scores[:8]
        an["radar"] = radar(player)
        if best:
            an["explication"] = explain(player, best, scores[1] if len(scores) > 1 else None)
    p["analyse"] = an
    return p
