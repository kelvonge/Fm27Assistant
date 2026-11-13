"""Contrats & finances : échéances, joueurs à prolonger ou à vendre, masse salariale."""
from __future__ import annotations

from datetime import date
from statistics import median

from ..textutil import fmt_money
from .knowledge import KB
from .squad import depth, reliable_note


def months_left(contract_end: str | None, game_date: str | None) -> int | None:
    if not contract_end or not game_date:
        return None
    try:
        a, b = date.fromisoformat(game_date), date.fromisoformat(contract_end)
    except ValueError:
        return None
    return (b.year - a.year) * 12 + (b.month - a.month)


def contracts(enriched: list[dict], kb: KB, ref: float | None, game_date: str | None, finances: dict | None) -> dict:
    ranks: dict[int, int] = {}
    for d in depth(enriched, kb, ref):
        for i, c in enumerate(d["joueurs"]):
            ranks[c["id"]] = min(ranks.get(c["id"], 99), i + 1)
    wages = [p["wage"] for p in enriched if p.get("wage")]
    med_wage = median(wages) if wages else None
    rows, sell = [], []
    for p in enriched:
        note, age, rank = reliable_note(p), p.get("age"), ranks.get(p["id"], 99)
        ml = months_left(p.get("contract_end"), game_date)
        row = {"id": p["id"], "name": p["name"], "age": age, "postes": [kb.pos_label(x) for x in p.get("pos") or []],
               "wage": p.get("wage"), "value": p.get("value"), "contract_end": p.get("contract_end"), "mois_restants": ml,
               "note": note, "rang_poste": rank if rank < 99 else None, "action": None, "raison": None, "urgence": 0}
        key_player = note is not None and ref is not None and note >= ref - 0.5
        young_talent = age is not None and age <= 23 and (p.get("potential_stars") or 0) >= 3.5
        if ml is not None and ml <= 18:
            row["urgence"] = 2 if ml <= 6 else 1
            when = "dans moins de 6 mois : il peut déjà signer ailleurs gratuitement" if ml <= 6 else f"dans {ml} mois"
            if key_player or young_talent:
                row["action"] = "prolonger"
                row["raison"] = f"Contrat qui expire {when}. " + ("Titulaire au niveau du onze type" if key_player else "Jeune à fort potentiel") + " : à prolonger en priorité."
            elif age is not None and age >= 32:
                row["action"] = "laisser partir"
                row["raison"] = f"Contrat qui expire {when}. À {age} ans et hors du onze type, une prolongation courte au maximum."
            elif note is None:
                row["action"] = "à évaluer"
                row["raison"] = f"Contrat qui expire {when}. Attributs non lus : impossible de juger son importance."
            else:
                row["action"] = "vendre" if ml > 6 else "laisser partir"
                row["raison"] = f"Contrat qui expire {when}. Joueur de complément ({note:.1f}) : " + ("vendez-le maintenant pour récupérer une indemnité." if ml > 6 else "ne prolongez que s'il accepte un salaire réduit.")
        reasons = []
        if note is not None and ref is not None:
            if rank >= 3 and note < ref - 2:
                reasons.append(f"{rank if rank < 99 else 'dernier'}e choix à son poste avec {note:.1f} (onze type : {ref:.1f})")
            if med_wage and p.get("wage") and p["wage"] >= 2 * med_wage and note < ref - 1:
                reasons.append(f"salaire élevé ({fmt_money(p['wage'])}/sem., médiane {fmt_money(med_wage)}) pour un non-titulaire")
            if age is not None and age >= 31 and note < ref and p.get("value"):
                reasons.append(f"{age} ans : sa valeur ({fmt_money(p['value'])}) ne fera que baisser")
        if reasons and row["action"] not in ("prolonger",):
            sell.append({**row, "action": "vendre", "raison": "À vendre : " + " ; ".join(reasons) + "."})
        rows.append(row)
    expiring = sorted([r for r in rows if r["urgence"]], key=lambda r: (r["mois_restants"], -(r["note"] or 0)))
    bill = sum(wages) if wages else None
    fin = dict(finances or {})
    notes = []
    if not game_date:
        notes.append("Date de jeu non lue : les échéances ne peuvent pas être calculées.")
    missing_c = sum(1 for p in enriched if not p.get("contract_end"))
    if missing_c:
        notes.append(f"{missing_c} joueur(s) sans date de fin de contrat lue (ajoutez la colonne Contrat à la vue Effectif).")
    missing_w = sum(1 for p in enriched if not p.get("wage"))
    if missing_w:
        notes.append(f"{missing_w} joueur(s) sans salaire lu : la masse salariale calculée est incomplète.")
    marge = None
    if fin.get("wage_budget") and (fin.get("wage_bill") or bill):
        marge = fin["wage_budget"] - (fin.get("wage_bill") or bill)
    return {
        "echeances": expiring, "a_vendre": sorted(sell, key=lambda r: -(r["wage"] or 0)),
        "tous": sorted(rows, key=lambda r: -(r["wage"] or 0)),
        "masse_salariale_lue": bill, "salaire_median": med_wage, "finances": fin or None, "marge_salariale": marge,
        "economie_ventes": sum(r["wage"] or 0 for r in sell) or None, "notes": notes,
    }
