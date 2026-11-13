"""Chargement et indexation de la base de connaissances (connaissances.json)."""
from __future__ import annotations

from .. import config

# Axes des radars : regroupements d'attributs lisibles d'un coup d'œil
AXES_JOUEUR = [
    ("Défense", ["tackling", "marking", "positioning"]),
    ("Physique", ["strength", "stamina", "balance"]),
    ("Vitesse", ["pace", "acceleration", "agility"]),
    ("Création", ["passing", "vision", "technique", "first_touch"]),
    ("Attaque", ["finishing", "off_the_ball", "dribbling"]),
    ("Mental", ["decisions", "composure", "concentration", "anticipation"]),
    ("Aérien", ["heading", "jumping"]),
    ("Pressing", ["work_rate", "teamwork", "aggression"]),
]
AXES_GARDIEN = [
    ("Arrêts", ["reflexes", "handling", "one_on_ones"]),
    ("Aérien", ["aerial_reach", "command_of_area", "jumping"]),
    ("Relance", ["kicking", "throwing", "passing", "first_touch"]),
    ("Sorties", ["rushing_out", "acceleration", "anticipation"]),
    ("Mental", ["concentration", "decisions", "composure", "positioning"]),
    ("Physique", ["agility", "strength", "balance"]),
]


class KB:
    def __init__(self, raw: dict, warning: str | None = None):
        self.raw = raw
        self.warning = warning
        self.attrs = {a["id"]: a for a in raw.get("attributs", [])}
        self.roles = {r["id"]: r for r in raw.get("roles", [])}
        self.formations = {f["id"]: f for f in raw.get("formations", [])}
        self.tactics = raw.get("tactiques", [])
        self.pos_labels = raw.get("postes", {})
        self.pos_names = raw.get("postes_noms", {})
        self.near = raw.get("postes_proches", {})
        self.near_penalty = float(raw.get("malus_poste_proche", 0.88))
        self.min_coverage = float(raw.get("couverture_minimale", 0.6))
        dw = raw.get("poids_defaut", {})
        self.w_key, self.w_sec = float(dw.get("cle", 3)), float(dw.get("secondaire", 1.5))
        self._weights: dict[str, dict[str, float]] = {}
        self.roles_by_pos: dict[str, list[str]] = {}
        for r in self.roles.values():
            for p in r.get("postes", []):
                self.roles_by_pos.setdefault(p, []).append(r["id"])

    def attr_name(self, attr_id: str) -> str:
        a = self.attrs.get(attr_id)
        return a["nom"] if a else attr_id

    def pos_label(self, pos: str) -> str:
        return self.pos_labels.get(pos, pos)

    def weights(self, role_id: str) -> dict[str, float]:
        """Poids de chaque attribut pour un rôle (clés, secondaires, surcharges)."""
        if role_id not in self._weights:
            r = self.roles[role_id]
            w = {a: self.w_sec for a in r.get("secondaires", []) if a in self.attrs}
            w.update({a: self.w_key for a in r.get("cles", []) if a in self.attrs})
            for a, v in (r.get("poids") or {}).items():
                if a in self.attrs:
                    try:
                        w[a] = float(v)
                    except (TypeError, ValueError):
                        pass
            self._weights[role_id] = {a: v for a, v in w.items() if v > 0}
        return self._weights[role_id]


def load_kb() -> KB:
    raw, warning = config.load_json("connaissances.json")
    try:
        return KB(raw, warning)
    except Exception as exc:  # structure cassée par une modification manuelle
        import json

        bundled = json.loads((config.resource_dir() / "data" / "connaissances.json").read_text(encoding="utf-8"))
        return KB(bundled, f"connaissances.json a une structure invalide ({exc}). La version d'origine est utilisée.")
