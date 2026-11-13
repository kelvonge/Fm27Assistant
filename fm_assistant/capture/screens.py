"""Reconnaissance de l'écran affiché à partir des textes lus (titres + indices + colonnes)."""
from __future__ import annotations

import re

from ..textutil import norm
from .layout import Cell

FORMATION_RE = re.compile(r"(?<![\d-])([3-5](?:-[0-5]){2,4})(?![\d-])")


def _contains(haystack: str, phrase: str) -> bool:
    """Présence d'une expression en mots entiers."""
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", haystack) is not None


def classify(lines: list[list[Cell]], img_h: int, cfg: dict, learned: dict[str, list[str]],
             attr_hits: int = 0, role_hits: int = 0) -> tuple[str | None, float, dict]:
    """Retourne (id écran ou None, confiance 0-1, détail des scores).

    attr_hits / role_hits : nombre de libellés d'attributs / de rôles vus,
    signatures fortes du profil joueur et de l'écran tactique.
    """
    if not lines:
        return None, 0.0, {}
    top_limit = img_h * 0.24
    top_text = " | ".join(norm(c.text) for line in lines for c in line if c.cy <= top_limit)
    all_text = " | ".join(norm(c.text) for line in lines for c in line)
    header_labels = {norm(c.text) for line in lines for c in line}
    aliases = cfg.get("colonnes", {})
    scores: dict[str, float] = {}
    for sc in cfg.get("ecrans", []):
        sid = sc["id"]
        s = 0.0
        for kw in sc.get("titres", []):
            if _contains(top_text, kw):
                s += 3
            elif _contains(all_text, kw):
                s += 1
        for kw in learned.get(sid, []):
            if _contains(top_text, kw):
                s += 6
            elif _contains(all_text, kw):
                s += 3
        s += sum(1 for kw in sc.get("indices", []) if _contains(all_text, kw))
        cols = sc.get("colonnes", [])
        if cols:
            found = sum(1 for f in cols if header_labels & set(aliases.get(f, ())))
            if found == len(cols):
                s += 2.5
            elif s and found == 0:
                s *= 0.5  # le titre est là mais pas le tableau attendu
        if any(_contains(top_text, kw) for kw in sc.get("exclut", [])):
            s *= 0.3
        scores[sid] = s
    if attr_hits >= 10:
        scores["profil"] = scores.get("profil", 0) + attr_hits * 0.8
    if role_hits >= 4:
        scores["tactique"] = scores.get("tactique", 0) + role_hits * 0.7
    if FORMATION_RE.search(all_text):
        scores["tactique"] = scores.get("tactique", 0) + 1.5
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < 2.5:
        return None, 0.0, scores
    best, s1 = ranked[0]
    s2 = ranked[1][1] if len(ranked) > 1 else 0
    conf = max(0.05, min(1.0, (s1 - s2) / max(s1, 1) * 0.6 + min(s1, 10) / 10 * 0.4))
    return best, round(conf, 2), scores
