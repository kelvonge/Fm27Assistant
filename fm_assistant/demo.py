"""Données de démonstration : un club fictif complet pour tester sans le jeu.

Tout passe par les mêmes fonctions de fusion que la lecture réelle.
"""
from __future__ import annotations

import random

from .analysis.knowledge import KB
from .db import Database

CLUB, DIVISION = "FC Valmont", "Ligue 2"
DATES = ["2026-07-06", "2026-08-17", "2026-09-28", "2026-11-13"]

PRENOMS = ["Lucas", "Hugo", "Théo", "Nathan", "Enzo", "Mathis", "Yanis", "Noah", "Adam", "Léo", "Ibrahim", "Moussa", "Rayan",
           "Jules", "Antoine", "Maxime", "Kévin", "Baptiste", "Sofiane", "Amine", "Diego", "Marco", "Luka", "Jonas", "Mamadou",
           "Bilal", "Rémi", "Clément", "Florian", "Ousmane", "Nicolas", "Elias", "Tiago", "Pablo", "Sacha", "Malo", "Timéo"]
NOMS = ["Morel", "Lambert", "Faure", "Girard", "Bonnet", "Dupuis", "Fontaine", "Rousseau", "Blanc", "Guérin", "Diallo", "Traoré",
        "Benali", "Marchand", "Perrin", "Renard", "Colin", "Vidal", "Caron", "Picard", "Da Silva", "Kovac", "Meunier", "Lemaire",
        "Sanogo", "Haddad", "Barbier", "Aubert", "Roche", "Noël", "Camara", "Schmitt", "Leclerc", "Pires", "Navarro", "Mercier",
        "Charpentier", "Besson", "Koné", "Jacquet", "Poulain", "Texier", "Delorme", "Sissoko", "Brunet", "Lacroix", "Ferrand"]
CLUBS = ["AS Brévanne", "Stade Cornouaille", "US Montclar", "Olympique Sarlat", "RC Hautmont", "FC Lérins", "SC Vauban",
         "AC Garonne", "Entente Sainte-Aube", "US Rochebrune", "Étoile de Corbières", "FC Armor", "SO Beaulieu",
         "Racing Vézère", "AS Port-Blanc", "Union Saint-Lys", "CS Meyran", "Sporting Lauzun", "FC Thiérache"]

GK_ATTRS = ["aerial_reach", "command_of_area", "communication", "eccentricity", "handling", "kicking", "one_on_ones",
            "punching", "reflexes", "rushing_out", "throwing"]
PROFILES = {
    "GK": ({"anticipation": 1, "concentration": 2, "positioning": 2, "agility": 2, "passing": -3, "first_touch": -3}, "GB", ["GK"]),
    "DC": ({"heading": 3, "marking": 3, "tackling": 3, "positioning": 3, "strength": 3, "jumping": 3, "bravery": 2,
            "finishing": -5, "dribbling": -4, "flair": -4, "crossing": -4, "long_shots": -4, "vision": -2}, "D (C)", ["DC"]),
    "DR": ({"crossing": 1, "tackling": 2, "marking": 2, "pace": 2, "acceleration": 2, "stamina": 3, "work_rate": 2,
            "finishing": -4, "heading": -1, "long_shots": -3}, "D (D)", ["DR"]),
    "DL": ({"crossing": 1, "tackling": 2, "marking": 2, "pace": 2, "acceleration": 2, "stamina": 3, "work_rate": 2,
            "finishing": -4, "heading": -1, "long_shots": -3}, "D (G)", ["DL"]),
    "DM": ({"tackling": 3, "positioning": 3, "anticipation": 2, "passing": 1, "work_rate": 2, "stamina": 2, "strength": 1,
            "concentration": 2, "finishing": -4, "dribbling": -2, "flair": -3}, "MD", ["DM"]),
    "MC": ({"passing": 3, "first_touch": 2, "vision": 2, "decisions": 2, "teamwork": 2, "stamina": 2, "technique": 1,
            "heading": -2, "finishing": -1}, "M (C)", ["MC"]),
    "AMC": ({"passing": 2, "technique": 3, "vision": 3, "flair": 3, "first_touch": 3, "dribbling": 2, "off_the_ball": 2,
             "tackling": -5, "marking": -5, "heading": -3, "strength": -2}, "MO (C)", ["AMC"]),
    "AMR": ({"pace": 3, "acceleration": 3, "dribbling": 3, "crossing": 3, "technique": 2, "agility": 2, "flair": 1,
             "tackling": -4, "marking": -4, "heading": -3, "strength": -2}, "MO (D)", ["AMR"]),
    "AML": ({"pace": 3, "acceleration": 3, "dribbling": 3, "crossing": 2, "technique": 2, "agility": 2, "finishing": 1,
             "tackling": -4, "marking": -4, "heading": -3, "strength": -2}, "MO (G)", ["AML"]),
    "ST": ({"finishing": 4, "off_the_ball": 3, "composure": 2, "first_touch": 1, "heading": 1, "anticipation": 2,
            "tackling": -6, "marking": -6, "positioning": -3, "crossing": -2}, "BT (C)", ["ST"]),
}
EXTRA_POS = {"DC": [("D (C), MD", ["DC", "DM"])], "DR": [("D/DL (D)", ["DR", "WBR"])], "DL": [("D/DL (G)", ["DL", "WBL"])],
             "DM": [("MD, M (C)", ["DM", "MC"])], "MC": [("M (C), MO (C)", ["MC", "AMC"]), ("MD, M (C)", ["DM", "MC"])],
             "AMC": [("M/MO (C)", ["MC", "AMC"])], "AMR": [("M/MO (D)", ["MR", "AMR"]), ("MO (DG)", ["AMR", "AML"])],
             "AML": [("M/MO (G)", ["ML", "AML"]), ("MO (G), BT (C)", ["AML", "ST"])], "ST": [("MO (C), BT (C)", ["AMC", "ST"])]}


def _attrs(rng: random.Random, kb: KB, group: str, level: float) -> dict:
    boosts = PROFILES[group][0]
    out = {}
    for a, meta in kb.attrs.items():
        if meta["categorie"] == "gardien":
            if group == "GK":
                out[a] = level + 2.5 + rng.gauss(0, 1.6)
            continue
        base = level + boosts.get(a, 0) + rng.gauss(0, 1.9)
        if group == "GK" and meta["categorie"] == "technique":
            base -= 5
        out[a] = base
    return {a: int(max(1, min(20, round(v)))) for a, v in out.items()}


def _player(rng, kb, used, group, level, age, club=None, wage_scale=1.0):
    while True:
        name = f"{rng.choice(PRENOMS)} {rng.choice(NOMS)}"
        if name not in used:
            used.add(name)
            break
    label, pos = PROFILES[group][1], PROFILES[group][2]
    if group in EXTRA_POS and rng.random() < 0.45:
        label, pos = rng.choice(EXTRA_POS[group])
    quality = max(0.2, (level - 6) / 6)
    age_f = 1.25 if age <= 23 else (1.0 if age <= 28 else max(0.25, 1 - (age - 28) * 0.17))
    value = round(quality ** 3 * 2_600_000 * age_f * rng.uniform(0.7, 1.4), -4)
    wage = round(quality ** 2 * 9_000 * wage_scale * rng.uniform(0.75, 1.3), -2)
    cur = max(1.0, min(5.0, round((2.9 + (level - 10.5) * 0.75 + rng.uniform(-0.3, 0.3)) * 2) / 2))
    growth = max(0, 24 - age) * 0.28 * rng.uniform(0.3, 1.5)
    pot = max(cur, min(5.0, round((cur + growth) * 2) / 2))
    return {"name": name, "age": age, "positions": label, "pos": pos, "club": club, "value": value, "value_min": value * 0.9,
            "value_max": value * 1.15, "wage": wage, "contract_end": f"{rng.choice([2028, 2028, 2028, 2029, 2029, 2030])}-06-30",
            "ability_stars": cur, "potential_stars": pot, "form": round(rng.uniform(6.3, 7.5), 2),
            "morale": rng.choice(["Très bon", "Bon", "Bon", "Correct", "Excellent", "Moyen"]),
            "condition": rng.randint(82, 100), "attributes": _attrs(rng, kb, group, level),
            "foot": rng.choice(["Droit", "Droit", "Gauche", "Les deux"]), "height": rng.randint(170, 194)}


def load_demo(db: Database, kb: KB) -> dict:
    """Remplace le contenu de la base par la carrière de démonstration."""
    rng = random.Random(27)
    db.reset()
    db.update_settings({"club": CLUB, "division": DIVISION, "saison": "2026/2027", "style": "pressing",
                        "objectif": "Jouer les barrages de montée", "accent": "#2fd08c", "premier_lancement": False})
    used: set[str] = set()
    plan = [("GK", 12.4, 29), ("GK", 10.6, 21), ("GK", 9.4, 18),
            ("DC", 12.6, 28), ("DC", 12.0, 31), ("DC", 11.3, 24), ("DC", 10.2, 19),
            ("DR", 12.1, 26), ("DR", 10.4, 20), ("DL", 11.8, 27),
            ("DM", 12.8, 30), ("DM", 11.2, 22), ("MC", 13.0, 27), ("MC", 12.2, 25), ("MC", 11.4, 33), ("MC", 10.3, 18),
            ("AMC", 12.9, 24), ("AMC", 10.8, 19), ("AMR", 12.5, 23), ("AMR", 11.0, 20), ("AML", 12.3, 28), ("AML", 10.5, 17),
            ("ST", 13.1, 29), ("ST", 12.0, 32), ("ST", 11.1, 21), ("ST", 9.9, 18)]
    squad = [_player(rng, kb, used, g, lvl - 1.0, age, CLUB) for g, lvl, age in plan]
    # Quelques situations parlantes : fin de contrat d'un cadre, blessure, gros salaire sur le banc
    squad[12]["contract_end"] = "2027-03-31"
    squad[3]["contract_end"] = "2027-06-30"
    squad[14]["contract_end"] = "2027-06-30"
    squad[23]["wage"] = 21_000
    squad[9]["injury"] = "Blessé – entorse de la cheville (3 semaines)"
    squad[9]["condition"] = 61
    # Défenseurs centraux plutôt lents → alerte « ligne haute »
    squad[3]["attributes"].update(pace=9, acceleration=8)
    squad[4]["attributes"].update(pace=8, acceleration=9)
    ids = []
    # Historique : les jeunes progressent, les anciens déclinent légèrement
    for step, gd in enumerate(DATES):
        scan = db.add_scan("effectif", gd, f"Démonstration – effectif au {gd}", "demo")
        for p in squad:
            rec = dict(p)
            back = len(DATES) - 1 - step
            delta = (-0.45 if p["age"] <= 21 else (-0.15 if p["age"] <= 24 else (0.2 if p["age"] >= 31 else 0))) * back
            hr = random.Random(hash((p["name"], step)) & 0xFFFF)
            rec["attributes"] = {a: int(max(1, min(20, round(v + delta + (hr.uniform(-0.45, 0.45) if back else 0)))))
                                 for a, v in p["attributes"].items()}
            rec["value"] = round(p["value"] * (1 + delta * 0.12), -4)
            rec["form"] = round(max(6.0, min(8.2, p["form"] + hr.uniform(-0.3, 0.3) * (1 if back else 0))), 2)
            pid, _ = db.upsert_player(rec, "effectif", scan, gd)
            if step == 0:
                ids.append(pid)
    db.set_meta("game_date", DATES[-1])
    gd = DATES[-1]
    # Cibles de recrutement
    scan = db.add_scan("recherche", gd, "Démonstration – recherche de joueurs (48 joueurs)", "demo")
    groups = ["GK", "DC", "DC", "DR", "DL", "DL", "DM", "MC", "MC", "AMC", "AMR", "AML", "ST", "ST", "DL", "DR"]
    for i in range(48):
        g = groups[i % len(groups)]
        age = rng.choice([17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 33])
        lvl = rng.uniform(8.8, 12.6) - (1.2 if age <= 19 else 0)
        t = _player(rng, kb, used, g, lvl, age, rng.choice(CLUBS), wage_scale=1.1)
        t["shortlist"] = i % 4 == 0
        if i % 7 == 3:  # joueurs seulement vus dans une liste : pas d'attributs lus
            t.pop("attributes")
        if i % 11 == 5:
            t["value"], t["value_min"], t["value_max"], t["club"] = 0, 0, 0, "Sans club"
        db.upsert_player(t, "cible", scan, gd)
    # Prochain adversaire : effectif partiellement lu
    opp = "AS Brévanne"
    scan = db.add_scan("effectif", gd, f"Démonstration – effectif de {opp}", "demo")
    for g, lvl, age in [("GK", 12.0, 30), ("DC", 12.4, 29), ("DC", 11.9, 33), ("DR", 11.5, 25), ("DL", 11.6, 24),
                        ("DM", 12.2, 28), ("MC", 12.0, 26), ("AMC", 12.6, 27), ("AMR", 12.8, 22), ("AML", 12.7, 23), ("ST", 13.2, 25)]:
        o = _player(rng, kb, used, g, lvl - 1.0, age, opp)
        if g in ("ST", "AMR", "AML"):
            o["attributes"].update(pace=16, acceleration=16)
        if g == "DC":
            o["attributes"].update(pace=9, acceleration=9)
        db.upsert_player(o, "autre", scan, gd)
    # Tactique lue
    by_pos = lambda pos, n: [p["name"] for p in squad if pos in p["pos"]][:n]
    xi = [("gardien", by_pos("GK", 1)[0]), ("defenseur_central", squad[3]["name"]), ("defenseur_relanceur", squad[4]["name"]),
          ("lateral_offensif", squad[7]["name"]), ("arriere_lateral", squad[9]["name"]),
          ("meneur_recule", squad[10]["name"]), ("box_to_box", squad[12]["name"]),
          ("meneur_avance", squad[16]["name"]), ("ailier", squad[18]["name"]), ("attaquant_interieur", squad[20]["name"]),
          ("attaquant_pivot", squad[22]["name"])]
    db.save_document("tactique", {
        "formation": "4-2-3-1", "mentalite": "Positive",
        "instructions": ["Pressing beaucoup plus intense", "Ligne défensive plus haute", "Contre-pressing", "Passes plus courtes", "Tempo plus élevé"],
        "joueurs": [{"role": r, "joueur": n, "x": 0.5, "y": 0.5} for r, n in xi]}, gd)
    # Finances (historique pour le graphique)
    for step, d in enumerate(DATES):
        db.save_document("finances", {"balance": 3_400_000 - step * 420_000, "transfer_budget": 1_250_000,
                                      "wage_budget": 165_000, "wage_bill": 148_000 + step * 2_500}, d)
    # Classement
    teams = [CLUB] + CLUBS
    rng.shuffle(teams)
    rows = []
    for t in teams:
        w = rng.randint(2, 9)
        d_ = rng.randint(1, 5)
        l_ = 14 - w - d_ if 14 - w - d_ >= 0 else 0
        gf = w * 2 + d_ + rng.randint(0, 5)
        ga = l_ * 2 + d_ + rng.randint(0, 4)
        rows.append({"team": t, "played": w + d_ + l_, "won": w, "drawn": d_, "lost": l_, "goals_for": gf,
                     "goals_against": ga, "goal_diff": gf - ga, "points": w * 3 + d_})
    rows.sort(key=lambda r: (-r["points"], -r["goal_diff"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    db.save_document("classement", rows, gd)
    # Calendrier
    fixtures = [{"date": "2026-10-31", "opponent": "US Montclar", "competition": DIVISION, "venue": "domicile", "result": "2-1"},
                {"date": "2026-11-07", "opponent": "FC Lérins", "competition": DIVISION, "venue": "exterieur", "result": "0-0"},
                {"date": "2026-11-14", "opponent": opp, "competition": DIVISION, "venue": "exterieur"},
                {"date": "2026-11-21", "opponent": "SC Vauban", "competition": "Coupe nationale", "venue": "domicile"},
                {"date": "2026-11-28", "opponent": "Olympique Sarlat", "competition": DIVISION, "venue": "domicile"}]
    db.save_document("calendrier", fixtures, gd)
    db.save_document("staff", [
        {"name": "Gérald Maubert", "job": "Entraîneur adjoint", "age": 51, "contract_end": "2028-06-30"},
        {"name": "Aurélien Costes", "job": "Entraîneur des gardiens", "age": 44, "contract_end": "2027-06-30"},
        {"name": "Samir Belkacem", "job": "Préparateur physique", "age": 38, "contract_end": "2027-06-30"},
        {"name": "Yves Le Goff", "job": "Recruteur principal", "age": 57, "contract_end": "2029-06-30"},
        {"name": "Hélène Vasseur", "job": "Kinésithérapeute", "age": 35, "contract_end": "2028-06-30"}], gd)
    db.set_meta("demo", True)
    return {"joueurs": len(squad), "cibles": 48, "club": CLUB}
