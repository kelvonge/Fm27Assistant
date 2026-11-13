"""Tableau de bord carrière : synthèse et alertes."""
from __future__ import annotations

from statistics import mean

from ..textutil import fmt_money, norm
from .contracts import contracts
from .knowledge import KB
from .squad import depth, division_benchmark, strengths


def dashboard(enriched: list[dict], ref: float | None, kb: KB, settings: dict, game_date: str | None,
              finances: dict | None, table: list[dict] | None, tactic_check: dict, counts: dict) -> dict:
    ages = [p["age"] for p in enriched if p.get("age")]
    con = contracts(enriched, kb, ref, game_date, finances)
    dep = depth(enriched, kb, ref)
    bench = division_benchmark(settings.get("division", ""), kb)
    level = {"onze_type": ref, "repere": None, "verdict": None}
    if ref is None:
        level["verdict"] = "Niveau non calculable : il faut les attributs d'au moins 5 joueurs (ouvrez leurs profils dans FM)."
    elif not bench:
        level["verdict"] = ("Renseignez votre division dans Réglages pour comparer votre effectif au niveau habituel du championnat."
                            if not settings.get("division") else
                            "Division non répertoriée dans connaissances.json (section niveaux_division) : comparaison indisponible.")
    else:
        diff = ref - bench["niveau"]
        level["repere"] = bench
        if diff >= 1:
            v = "nettement au-dessus du niveau habituel"
        elif diff >= 0.3:
            v = "au-dessus du niveau habituel"
        elif diff > -0.3:
            v = "dans la moyenne"
        elif diff > -1:
            v = "en dessous du niveau habituel"
        else:
            v = "nettement en dessous du niveau habituel"
        level["verdict"] = f"Onze type à {ref:.1f}/20, {v} de la division (repère estimé : {bench['niveau']:.1f})."
        level["ecart"] = round(diff, 2)
    my_row = None
    if table and settings.get("club"):
        c = norm(settings["club"])
        my_row = next((r for r in table if norm(r.get("team")) == c or c in norm(r.get("team")) or norm(r.get("team")) in c), None)
    alerts = []
    for r in con["echeances"]:
        if r["urgence"] == 2 and r["action"] == "prolonger":
            alerts.append({"niveau": "rouge", "texte": f"{r['name']} : contrat qui expire dans {r['mois_restants']} mois, à prolonger d'urgence.", "lien": "contrats"})
    for d in dep:
        if d["principal"] and d["statut"] in ("trou", "faible"):
            alerts.append({"niveau": "orange", "texte": f"Poste {d['nom'].lower()} : {d['message']}", "lien": "recrutement"})
    injured = [p for p in enriched if p.get("injury")]
    if injured:
        alerts.append({"niveau": "orange", "texte": f"{len(injured)} joueur(s) signalé(s) indisponible(s) : " + ", ".join(p["name"] for p in injured[:4]) + ".", "lien": "effectif"})
    for a in tactic_check.get("alertes", []):
        alerts.append({"niveau": "orange", "texte": a["message"], "lien": "tactique"})
    if con["marge_salariale"] is not None and con["marge_salariale"] < 0:
        alerts.append({"niveau": "rouge", "texte": f"Budget salarial dépassé de {fmt_money(-con['marge_salariale'])} par semaine.", "lien": "contrats"})
    if finances and finances.get("balance") is not None and finances["balance"] < 0:
        alerts.append({"niveau": "rouge", "texte": f"Solde du club négatif ({fmt_money(finances['balance'])}).", "lien": "contrats"})
    no_attr = sum(1 for p in enriched if not p.get("attributes"))
    if enriched and no_attr:
        alerts.append({"niveau": "info", "texte": f"{no_attr} joueur(s) de l'effectif sans attributs lus : ouvrez leurs profils dans FM pour compléter l'analyse.", "lien": "lecture"})
    return {
        "club": settings.get("club") or None, "division": settings.get("division") or None,
        "saison": settings.get("saison") or None, "objectif": settings.get("objectif") or None,
        "style": settings.get("style") or None, "date_jeu": game_date,
        "effectif": {"joueurs": len(enriched), "age_moyen": round(mean(ages), 1) if ages else None,
                     "avec_attributs": len(enriched) - no_attr,
                     "valeur_totale": sum(p["value"] for p in enriched if p.get("value")) or None},
        "niveau": level, "masse_salariale": con["finances"].get("wage_bill") if con["finances"] and con["finances"].get("wage_bill") else con["masse_salariale_lue"],
        "masse_source": "écran Finances" if con["finances"] and con["finances"].get("wage_bill") else ("somme des salaires lus" if con["masse_salariale_lue"] else None),
        "finances": finances, "marge_salariale": con["marge_salariale"],
        "echeances": con["echeances"][:8], "classement": my_row, "equipes": len(table) if table else None,
        "profondeur": [{"label": d["label"], "nom": d["nom"], "statut": d["statut"], "nb": len(d["joueurs"])} for d in dep if d["principal"]],
        "forces": strengths(enriched, kb), "alertes": alerts, "compteurs": counts, "vide": not enriched,
    }
