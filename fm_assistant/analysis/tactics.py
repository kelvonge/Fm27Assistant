"""Assistant tactique : meilleur XI, tactiques adaptées, incohérences, avant-match."""
from __future__ import annotations

from statistics import mean

from ..textutil import name_key, names_compatible, norm, ordinal, fr
from .knowledge import KB
from .ratings import score_role
from .squad import reliable_note, team_attributes


def hungarian(cost: list[list[float]]) -> list[int]:
    """Affectation optimale (coût minimal). cost : n lignes × m colonnes, n ≤ m.
    Retourne pour chaque ligne l'indice de colonne choisi."""
    n, m = len(cost), len(cost[0])
    INF = float("inf")
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    res = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            res[p[j] - 1] = j - 1
    return res


def slot_fit(player: dict, slot: dict, kb: KB) -> dict | None:
    """Meilleure façon d'utiliser un joueur à un emplacement : rôle, note, hors-poste éventuel."""
    attrs = player.get("attributes")
    if not attrs:
        return None
    ppos = player.get("pos") or []
    best = None
    for pos in slot["postes"]:
        if pos in ppos:
            factor = 1.0
        elif any(pos in kb.near.get(pp, []) for pp in ppos):
            factor = kb.near_penalty
        else:
            continue
        for rid in kb.roles_by_pos.get(pos, []):
            sc = score_role(attrs, rid, kb)
            if not sc or not sc["fiable"]:
                continue
            val = sc["note"] * factor
            if best is None or val > best["valeur"]:
                best = {"valeur": round(val, 2), "note": sc["note"], "role": rid, "role_nom": sc["nom"],
                        "poste": pos, "hors_poste": factor < 1, "forts": sc["forts"]}
    return best


def best_xi(players: list[dict], formation: dict, kb: KB) -> dict:
    """Onze optimal pour une formation (affectation globale, pas poste par poste)."""
    slots = formation["postes"]
    available = [p for p in players if p.get("attributes") and not p.get("injury")]
    fits = [[slot_fit(p, s, kb) for p in available] for s in slots]
    BIG = 1000.0
    m = max(len(available), len(slots))
    cost = [[(BIG if j >= len(available) or fits[i][j] is None else 20 - fits[i][j]["valeur"]) for j in range(m)]
            for i in range(len(slots))]
    assign = hungarian(cost) if available else [-1] * len(slots)
    chosen: set[int] = set()
    out = []
    for i, s in enumerate(slots):
        j = assign[i]
        fit = fits[i][j] if 0 <= j < len(available) else None
        entry = {"id": s["id"], "postes": s["postes"], "label": kb.pos_label(s["postes"][0]), "x": s["x"], "y": s["y"],
                 "joueur": None, "remplacant": None}
        if fit:
            p = available[j]
            chosen.add(j)
            entry.update(joueur={"id": p["id"], "name": p["name"], "age": p.get("age")}, role=fit["role"],
                         role_nom=fit["role_nom"], note=fit["note"], valeur=fit["valeur"], hors_poste=fit["hors_poste"],
                         raison=", ".join(f"{f['nom']} {f['val']}" for f in fit["forts"]))
        out.append(entry)
    # Doublure de chaque emplacement : meilleur joueur non titulaire
    for i, entry in enumerate(out):
        alts = [(fits[i][j]["valeur"], j) for j in range(len(available)) if j not in chosen and fits[i][j]]
        if alts:
            val, j = max(alts)
            f = fits[i][j]
            entry["remplacant"] = {"id": available[j]["id"], "name": available[j]["name"], "note": f["note"],
                                   "role_nom": f["role_nom"], "hors_poste": f["hors_poste"]}
    notes = [e["valeur"] for e in out if e.get("joueur")]
    return {
        "formation": formation["id"], "postes": out, "complet": len(notes) == len(slots),
        "note": round(mean(notes), 2) if notes else None, "titulaires": len(notes),
        "indisponibles": [p["name"] for p in players if p.get("injury")],
        "non_evalues": [p["name"] for p in players if not p.get("attributes")],
    }


def profile_fit(means: dict[str, float], tactic: dict, kb: KB) -> dict | None:
    """Adéquation de l'équipe aux exigences d'un style (moyenne pondérée /20)."""
    req = {a: w for a, w in tactic.get("exigences", {}).items() if a in means}
    if len(req) < max(3, len(tactic.get("exigences", {})) * 0.6):
        return None
    score = sum(means[a] * w for a, w in req.items()) / sum(req.values())
    ranked = sorted(req, key=lambda a: -means[a])
    fmt = lambda a: {"nom": kb.attr_name(a), "val": means[a]}
    return {"score": round(score, 2), "atouts": [fmt(a) for a in ranked[:3]], "limites": [fmt(a) for a in ranked[-2:][::-1]]}


def suggest_tactics(enriched: list[dict], kb: KB, style: str = "", limit: int = 3) -> dict:
    means = team_attributes(enriched, top=16)
    if len(means) < 15:
        return {"suggestions": [], "message": "Pas assez d'attributs lus pour recommander une tactique : ouvrez les profils d'au moins 11 joueurs."}
    overall = mean(means.values())
    xi_cache: dict[str, dict] = {}
    out = []
    for t in kb.tactics:
        fit = profile_fit(means, t, kb)
        if not fit:
            continue
        best = None
        for fid in t.get("formations", []):
            if fid not in kb.formations:
                continue
            if fid not in xi_cache:
                xi_cache[fid] = best_xi(enriched, kb.formations[fid], kb)
            xi = xi_cache[fid]
            if xi["note"] is None:
                continue
            val = xi["note"] - (0 if xi["complet"] else 1.5 * (11 - xi["titulaires"]))
            if best is None or val > best[0]:
                best = (val, xi)
        if not best:
            continue
        wanted = bool(style) and (norm(style) in norm(t["nom"]) or norm(t.get("style", "")) in norm(style))
        total = (fit["score"] - overall) * 1.0 + (best[0] - overall) * 0.6 + (0.4 if wanted else 0)
        atouts = ", ".join(f"{a['nom']} {fr(a['val'])}" for a in fit["atouts"])
        limites = ", ".join(f"{a['nom']} {fr(a['val'])}" for a in fit["limites"])
        why = (f"Votre équipe a le profil pour ce style : {atouts} en moyenne (moyenne générale {fr(overall)}). "
               f"Points à surveiller : {limites}. Le {best[1]['formation']} donne un onze noté {fr(best[1]['note'])}/20.")
        if wanted:
            why += " Correspond au style de jeu que vous avez indiqué."
        out.append({"id": t["id"], "nom": t["nom"], "description": t["description"], "mentalite": t.get("mentalite"),
                    "instructions": t.get("instructions", []), "formation": best[1]["formation"], "xi": best[1],
                    "adequation": fit["score"], "score": round(total, 2), "explication": why, "style_voulu": wanted})
    out.sort(key=lambda s: -s["score"])
    return {"suggestions": out[:limit], "message": None, "moyenne": round(overall, 2)}


def match_player(name: str | None, players: list[dict]) -> dict | None:
    if not name:
        return None
    key = name_key(name)
    for p in players:
        if name_key(p["name"]) == key:
            return p
    last = key.split()[-1] if key else ""
    cands = [p for p in players if names_compatible(name_key(p["name"]), key) or name_key(p["name"]).split()[-1:] == [last]]
    return cands[0] if len(cands) == 1 else None


def check_tactic(tactic: dict | None, enriched: list[dict], kb: KB) -> dict:
    """Incohérences entre la tactique lue dans le jeu et les joueurs alignés."""
    if not tactic:
        return {"lue": False, "alertes": [], "roles": [],
                "message": "Tactique non lue : ouvrez l'écran Tactique dans FM pour obtenir l'analyse de cohérence."}
    alerts, roles = [], []
    lineup = []
    for item in tactic.get("joueurs") or []:
        p = match_player(item.get("joueur"), enriched)
        role = kb.roles.get(item.get("role"))
        if not p or not role:
            if item.get("joueur") and not p:
                roles.append({"joueur": item["joueur"], "role_nom": role["nom"] if role else item.get("role"),
                              "statut": "inconnu", "message": "Joueur non retrouvé dans l'effectif lu."})
            continue
        lineup.append((p, role))
        cur = score_role(p.get("attributes"), role["id"], kb)
        if not cur:
            roles.append({"joueur": p["name"], "id": p["id"], "role_nom": role["nom"], "statut": "inconnu",
                          "message": "Attributs non lus : ouvrez son profil."})
            continue
        alts = [s for s in (score_role(p["attributes"], rid, kb) for pos in role["postes"] for rid in kb.roles_by_pos.get(pos, []))
                if s and s["fiable"] and s["role"] != role["id"]]
        alt = max(alts, key=lambda s: s["note"]) if alts else None
        entry = {"joueur": p["name"], "id": p["id"], "role_nom": role["nom"], "note": cur["note"], "statut": "ok", "message": None}
        if alt and alt["note"] - cur["note"] >= 0.8:
            forts = ", ".join(f"{f['nom']} {f['val']}" for f in alt["forts"])
            entry.update(statut="mieux", alternative=alt["nom"], gain=round(alt["note"] - cur["note"], 1),
                         message=f"{p['name']} serait meilleur en {alt['nom']} ({fr(alt['note'])} contre {fr(cur['note'])}) car {forts}.")
        if not set(role["postes"]) & set(p.get("pos") or []) and p.get("pos"):
            entry["statut"] = "hors_poste"
            entry["message"] = f"{p['name']} n'a aucun poste naturel compatible avec le rôle {role['nom']}." + (" " + entry["message"] if entry["message"] else "")
        roles.append(entry)
    instr = [norm(i) for i in tactic.get("instructions") or []]
    for rule in kb.raw.get("incoherences", []):
        triggers = [norm(x) for x in rule.get("si_instructions", [])]
        active = [i for i in instr if any(t == i or t in i for t in triggers)]
        if not active:
            continue
        wanted = rule.get("postes", ["*"])
        if lineup:
            group = [p for p, role in lineup if "*" in wanted and "GK" not in role["postes"] or set(wanted) & set(role["postes"])]
        else:
            group = [p for p in enriched if p.get("attributes") and ("*" in wanted and "GK" not in (p.get("pos") or []) or set(wanted) & set(p.get("pos") or []))]
            group.sort(key=lambda p: -(reliable_note(p) or 0))
            group = group[: 10 if "*" in wanted else 3]
        group = [p for p in group if any(a in (p.get("attributes") or {}) for a in rule["attributs"])]
        vals = [mean(p["attributes"][a] for a in rule["attributs"] if a in p["attributes"]) for p in group]
        if not vals:
            continue
        avg = mean(vals)
        bad = avg < rule["seuil"] if rule.get("sens", "<") == "<" else avg > rule["seuil"]
        if bad:
            names = ", ".join(p["name"] for p in group[:4])
            attrs = " / ".join(kb.attr_name(a) for a in rule["attributs"])
            alerts.append({"id": rule["id"], "message": rule["message"], "conseil": rule.get("conseil"),
                           "detail": f"{attrs} : {fr(avg)} en moyenne (seuil {rule['seuil']}) — {names}.",
                           "base": "titulaires lus sur l'écran Tactique" if lineup else "meilleurs joueurs de l'effectif (onze non lu)"})
    return {"lue": True, "formation": tactic.get("formation"), "mentalite": tactic.get("mentalite"),
            "instructions": tactic.get("instructions") or [], "alertes": alerts, "roles": roles, "message": None}


def prematch(fixtures: list[dict] | None, table: list[dict] | None, others: list[dict], enriched: list[dict],
             kb: KB, my_club: str, game_date: str | None) -> dict:
    """Conseils d'avant-match, uniquement à partir de ce qui a été lu à l'écran."""
    if not fixtures:
        return {"disponible": False, "message": "Calendrier non lu : ouvrez l'écran Calendrier pour connaître le prochain adversaire."}
    upcoming = [f for f in fixtures if not f.get("result") and (not game_date or (f.get("date") or "") >= game_date)]
    if not upcoming:
        return {"disponible": False, "message": "Aucun match à venir dans le calendrier lu."}
    nxt = upcoming[0]
    opp = nxt.get("opponent") or ""
    out = {"disponible": True, "match": nxt, "adversaire": opp, "conseils": [], "manques": []}
    row = lambda club: next((r for r in table or [] if club and (norm(r.get("team")) == norm(club) or norm(club) in norm(r.get("team")) or norm(r.get("team")) in norm(club))), None)
    mine, theirs = row(my_club), row(opp)
    if not table:
        out["manques"].append("Classement non lu : impossible de situer l'adversaire.")
    elif not theirs:
        out["manques"].append(f"{opp} n'apparaît pas dans le classement lu (autre compétition ?).")
    elif not mine:
        out["manques"].append("Votre club n'a pas été retrouvé dans le classement : renseignez son nom exact dans Réglages.")
    else:
        out["classement"] = {"moi": mine, "eux": theirs}
        gap = (theirs.get("rank") or 0) - (mine.get("rank") or 0)
        n = len(table)
        away = nxt.get("venue") == "exterieur"
        if gap >= max(4, n // 4):
            out["conseils"].append({"titre": "Vous êtes favori", "texte": f"{opp} est {ordinal(theirs['rank'])}, vous êtes {ordinal(mine['rank'])}. Attendez-vous à un bloc bas : jouez large, soyez patient, et gardez une mentalité positive" + (" même à l'extérieur." if away else ".")})
        elif gap <= -max(4, n // 4):
            out["conseils"].append({"titre": "Adversaire supérieur", "texte": f"{opp} est {ordinal(theirs['rank'])}, vous êtes {ordinal(mine['rank'])}. Resserrez les lignes, baissez la mentalité d'un cran et misez sur les transitions" + (" : à l'extérieur, un nul est un bon résultat." if away else ".")})
        else:
            out["conseils"].append({"titre": "Match équilibré", "texte": f"{opp} ({ordinal(theirs['rank'])}) est proche de vous au classement ({ordinal(mine['rank'])}). Gardez votre plan habituel" + (" avec un peu plus de prudence à l'extérieur." if away else " et imposez votre jeu à domicile.")})
        pl = theirs.get("played") or 0
        if pl >= 5 and theirs.get("goals_for") is not None and theirs.get("goals_against") is not None:
            gf, ga = theirs["goals_for"] / pl, theirs["goals_against"] / pl
            if gf >= 1.8:
                out["conseils"].append({"titre": "Attaque prolifique", "texte": f"{opp} marque {fr(gf)} but(s) par match : évitez la ligne très haute et gardez un milieu de couverture."})
            if ga >= 1.6:
                out["conseils"].append({"titre": "Défense perméable", "texte": f"{opp} encaisse {fr(ga)} but(s) par match : pressez haut et multipliez les centres et les tirs."})
            elif ga <= 0.8:
                out["conseils"].append({"titre": "Défense solide", "texte": f"{opp} n'encaisse que {fr(ga)} but(s) par match : soignez les coups de pied arrêtés et travaillez le ballon jusque dans la surface."})
    squad = [p for p in others if p.get("club") and (norm(p["club"]) == norm(opp) or norm(opp) in norm(p["club"])) and p.get("attributes")]
    if len(squad) < 5:
        out["manques"].append(f"Joueurs de {opp} non lus : ouvrez son effectif et quelques profils dans FM pour des conseils sur ses points forts.")
    else:
        grp = lambda poses: [p for p in squad if set(poses) & set(p.get("pos") or [])]
        avg = lambda ps, attrs: mean([mean(p["attributes"][a] for a in attrs if a in p["attributes"]) for p in ps if any(a in p["attributes"] for a in attrs)] or [0])
        fw, cb = grp(["ST", "AMR", "AML"]), grp(["DC"])
        my_cb = [p for p in enriched if "DC" in (p.get("pos") or []) and p.get("attributes")]
        my_fw = [p for p in enriched if set(["ST", "AMR", "AML"]) & set(p.get("pos") or []) and p.get("attributes")]
        if fw and my_cb:
            a, b = avg(fw, ["pace", "acceleration"]), avg(my_cb, ["pace", "acceleration"])
            if a and b and a - b >= 1.5:
                out["conseils"].append({"titre": "Attaquants rapides en face", "texte": f"Leurs attaquants sont plus rapides ({fr(a)}) que vos centraux ({fr(b)}) : baissez la ligne défensive et évitez le hors-jeu."})
        if cb and my_fw:
            a, b = avg(cb, ["pace", "acceleration"]), avg(my_fw, ["pace", "acceleration"])
            if a and b and b - a >= 1.5:
                out["conseils"].append({"titre": "Défense adverse lente", "texte": f"Leurs centraux sont lents ({fr(a)}) face à vos attaquants ({fr(b)}) : jouez dans les espaces, dans le dos de la défense."})
            a, b = avg(cb, ["jumping", "heading"]), avg(my_fw, ["jumping", "heading"])
            if a and b and a - b >= 2:
                out["conseils"].append({"titre": "Dominés dans les airs", "texte": f"Leurs centraux dominent de la tête ({fr(a)} contre {fr(b)}) : privilégiez les centres à ras de terre et le jeu au sol."})
        out["effectif_adverse_lu"] = len(squad)
    return out
