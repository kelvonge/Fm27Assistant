"""Transformation des textes lus en données structurées, écran par écran.

Principe : une valeur illisible reste absente (None) et un avertissement est
ajouté ; rien n'est deviné.
"""
from __future__ import annotations

import re
from datetime import date

import numpy as np

from ..textutil import (best_match, norm, parse_date, parse_float, parse_int, parse_money, parse_positions,
                        parse_wage, _month)
from . import visual
from .calibration import Calibration
from .layout import Cell, below, build_lines, detect_header, read_table, right_of
from .ocr import Token
from .screens import FORMATION_RE, classify

PLAYER_SCREENS = ("effectif", "recherche", "shortlist")
_NUM_RE = re.compile(r"^\d{1,2}$")
_RANGE_RE = re.compile(r"^(\d{1,2})\s*[-–]\s*(\d{1,2})$")
_TRAIL_NUM = re.compile(r"^(.*?\D)[\s:]*?(\d{1,2}(?:\s*[-–]\s*\d{1,2})?)$")
_POS_CELL = re.compile(r"^[A-Za-z/ ]{1,7}(\s*\([A-Za-z ]{1,4}\))?(\s*[,;]\s*[A-Za-z/ ]{1,7}(\s*\([A-Za-z ]{1,4}\))?)*$")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:er)?\s+([A-Za-zÀ-ÿ]{3,10})\.?(?!\s*\d{4})")
_SCORE = re.compile(r"\b(\d{1,2})\s*[-–:]\s*(\d{1,2})\b")


class Knowledge4Parse:
    """Index de recherche (libellé normalisé → identifiant) tirés de la base de connaissances."""

    def __init__(self, kb: dict, cfg: dict):
        self.attr = {}
        self.attr_name = {}
        for a in kb["attributs"]:
            self.attr_name[a["id"]] = a["nom"]
            for label in [a["nom"], a.get("en", "")] + a.get("alias", []):
                if label:
                    self.attr[norm(label)] = a["id"]
        self.role = {}
        for r in kb["roles"]:
            for label in (r["nom"], r.get("en", "")):
                if label:
                    self.role[norm(label)] = r["id"]
        t = cfg.get("tactique", {})
        self.mentality = {norm(m): m for m in t.get("mentalites", [])}
        self.instruction = {norm(i): i for i in t.get("instructions", [])}
        self.cfg = cfg


def find_game_date(lines: list[list[Cell]], img_h: int, img_w: int) -> str | None:
    """Date de jeu affichée dans le bandeau supérieur."""
    cands = []
    for line in lines:
        cells = [c for c in line if c.cy <= img_h * 0.13]
        if not cells:
            continue
        for c in cells:
            d = parse_date(c.text)
            if d:
                cands.append((c.x, d))
        joined = parse_date(" ".join(c.text for c in cells))
        if joined and not any(d == joined for _, d in cands):
            cands.append((cells[-1].x, joined))
    if not cands:
        return None
    return max(cands)[1]  # la date du jeu est le plus souvent à droite du bandeau


def _clean_name(text: str) -> str:
    t = re.sub(r"^[\d.\s#]+", "", text).strip(" -–|•*")
    t = re.sub(r"\s{2,}", " ", t)
    return t


def _looks_like_name(text: str) -> bool:
    letters = sum(ch.isalpha() for ch in text)
    return letters >= 3 and letters >= len(text.replace(" ", "")) * 0.7


def _attr_value(text: str) -> tuple[int | None, str]:
    """« 16 » → (16, exact) ; « 12-15 » (joueur peu observé) → (14, plage)."""
    t = text.strip()
    m = _RANGE_RE.match(t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= b <= 20:
            return round((a + b) / 2), "plage"
        return None, ""
    v = parse_int(t, 1, 20) if len(t) <= 2 else None
    return (v, "exact") if v is not None else (None, "")


# ---------------------------------------------------------------- tableaux de joueurs
def parse_player_table(lines, img, kp: Knowledge4Parse, calib: Calibration, screen: str, settings: dict) -> dict:
    cfg = kp.cfg
    extra = {k: f"attr:{v}" for k, v in kp.attr.items() if len(k) > 3}
    extra.update(calib.data["colonnes"])
    found = detect_header(lines, cfg["colonnes"], cfg["champs_ecran"][screen], extra, min_hits=2)
    out = {"players": [], "headers": [], "warnings": []}
    if not found:
        out["warnings"].append("En-têtes du tableau introuvables : vérifiez que la ligne de titres des colonnes est visible, ou associez les colonnes dans le calibrage.")
        return out
    hi, cols = found
    out["headers"] = [{"texte": c.text, "champ": c.field} for c in cols]
    if not any(c.field == "name" for c in cols):
        out["warnings"].append("Colonne « Nom » non reconnue : associez-la dans le calibrage.")
        return out
    period = settings.get("periode_salaire", "semaine")
    skipped = 0
    for row in read_table(lines, hi, cols):
        rec: dict = {}
        attrs: dict = {}
        src: dict = {}
        for idx, cell in row.items():
            f = cols[idx].field
            if not f:
                continue
            txt = calib.fix(cell.text.strip())
            if f == "name":
                rec["name"] = _clean_name(txt)
            elif f == "age":
                rec["age"] = parse_int(txt, 14, 50)
            elif f == "position":
                pos = parse_positions(txt)
                if pos:
                    rec["positions"], rec["pos"] = txt, pos
            elif f in ("club", "nationality", "morale", "injury", "role", "foot", "personality"):
                if any(ch.isalnum() for ch in txt):
                    rec[f] = txt
            elif f == "value":
                m = parse_money(txt)
                if m:
                    rec["value"], rec["value_min"], rec["value_max"] = m["amount"], m["min"], m["max"]
            elif f == "wage":
                rec["wage"] = parse_wage(txt, period)
            elif f == "contract_end":
                rec["contract_end"] = parse_date(txt)
            elif f in ("ability_stars", "potential_stars"):
                v = parse_float(txt)
                if v is not None and 0 < v <= 5:
                    rec[f] = v
            elif f == "form":
                v = parse_float(txt)
                if v is not None and 1 <= v <= 10:
                    rec["form"] = v
            elif f == "condition":
                rec["condition"] = parse_int(txt, 0, 100)
            elif f in ("apps", "goals", "assists"):
                rec[f] = parse_int(txt, 0, 999)
            elif f == "height":
                rec["height"] = parse_int(txt, 140, 220)
            elif f.startswith("attr:"):
                v, s = _attr_value(txt)
                if v is not None:
                    attrs[f[5:]] = v
                    src[f[5:]] = s
        name = rec.get("name") or ""
        if not _looks_like_name(name) or (rec.get("age") is None and not rec.get("pos") and len(row) < 3):
            skipped += 1
            continue
        # Étoiles : ce sont des icônes, pas du texte → comptage visuel dans la cellule
        star_cols = [c for c in cols if c.field in ("ability_stars", "potential_stars") and rec.get(c.field) is None]
        if img is not None and star_cols:
            cells = list(row.values())
            y0, y1 = min(c.y for c in cells), max(c.y1 for c in cells)
            h = y1 - y0
            groups = visual.star_groups(img, min(c.x0 for c in star_cols) - 6 * h, y0, max(c.x0 for c in star_cols) + 7 * h, y1)
            # Chaque rangée va à la colonne la mieux alignée (à gauche ou centrée), sans supposer l'alignement
            for col in star_cols:
                best = None
                for gx0, gx1, n in groups:
                    dist = min(abs(gx0 - col.x0), abs((gx0 + gx1) / 2 - col.cx))
                    other = min((min(abs(gx0 - o.x0), abs((gx0 + gx1) / 2 - o.cx)) for o in star_cols if o is not col), default=1e9)
                    if dist < 4 * h and dist <= other and (best is None or dist < best[0]):
                        best = (dist, n)
                if best:
                    rec[col.field] = best[1]
        if attrs:
            rec["attributes"], rec["attr_source"] = attrs, src
        out["players"].append({k: v for k, v in rec.items() if v is not None})
    if skipped > 3 and not out["players"]:
        out["warnings"].append("Aucune ligne de joueur lisible sous les en-têtes.")
    return out


# ---------------------------------------------------------------- profil joueur
def _split_trailing_numbers(lines, kp: Knowledge4Parse):
    """« Passes 16 » lu en une seule cellule → libellé + valeur."""
    out = []
    for line in lines:
        new = []
        for c in line:
            m = _TRAIL_NUM.match(c.text.strip())
            if m and best_match(m.group(1), kp.attr, 0.86):
                wl = c.w * len(m.group(1)) / max(1, len(c.text))
                new.append(Cell(m.group(1).strip(), c.x, c.y, wl, c.h, c.conf))
                new.append(Cell(m.group(2).strip(), c.x + wl + 2, c.y, c.w - wl - 2, c.h, c.conf))
            else:
                new.append(c)
        out.append(new)
    return out


def count_attribute_labels(lines, kp: Knowledge4Parse) -> int:
    seen = set()
    for line in lines:
        for c in line:
            m = _TRAIL_NUM.match(c.text.strip())
            a = best_match(m.group(1) if m else c.text, kp.attr, 0.86)
            if a:
                seen.add(a)
    return len(seen)


def parse_profile(lines, img, kp: Knowledge4Parse, calib: Calibration, img_w: int, img_h: int, settings: dict) -> dict:
    out = {"players": [], "warnings": [], "headers": []}
    lines = _split_trailing_numbers(lines, kp)
    attrs: dict = {}
    src: dict = {}
    labels: list[tuple[str, Cell, list[Cell]]] = []
    for line in lines:
        for c in line:
            a = best_match(calib.fix(c.text), kp.attr, 0.86)
            if a:
                labels.append((a, c, line))
    for a, c, line in labels:
        nxt = right_of(line, c, max_dist=c.h * 14)
        if nxt is None:
            continue
        v, s = _attr_value(calib.fix(nxt.text))
        if v is not None and (a not in attrs or s == "exact"):
            attrs[a], src[a] = v, s
    if len(attrs) < 5 and len(labels) >= 10 and img is not None:
        # Aucun chiffre : le jeu affiche peut-être des barres → lecture par longueur
        for a, c, line in labels:
            nxt = right_of(line, c)
            x_end = nxt.x - 4 if nxt is not None else min(img_w, c.x1 + c.h * 30)
            v = visual.bar_value(img, c.x1 + 4, c.y - 2, x_end, c.y1 + 2)
            if v is not None:
                attrs[a], src[a] = v, "barres"
        if attrs:
            out["warnings"].append("Attributs lus d'après la longueur des barres : valeurs approximatives.")
    rec: dict = {}
    # Nom : le plus grand texte du haut de l'écran qui ressemble à un nom
    cands = []
    for line in lines:
        for c in line:
            if c.cy > img_h * 0.3:
                continue
            t = _clean_name(calib.fix(c.text))
            if not _looks_like_name(t) or len(t.split()) > 5 or parse_date(t):
                continue
            n = norm(t)
            if best_match(t, kp.attr, 0.86) or any(n == kw or n.startswith(kw + " ") for sc in kp.cfg["ecrans"] for kw in sc["titres"]):
                continue
            cands.append((c.h, -c.y, t))
    if cands:
        rec["name"] = max(cands)[2]
    period = settings.get("periode_salaire", "semaine")
    info = kp.cfg.get("profil", {})
    all_labels = [al for aliases in info.values() for al in aliases]
    for li, line in enumerate(lines):
        for c in line:
            for fld, aliases in info.items():
                if fld in rec:
                    continue
                hit, inline = _label_hit(c.text, aliases)
                if not hit:
                    continue
                vals = [inline] if inline else []
                # Valeur à droite du libellé, ou juste en dessous (libellé au-dessus de sa valeur)
                for x in (right_of(line, c, max_dist=c.h * 16), below(lines, li, c)):
                    if x is not None and not _label_hit(x.text, all_labels)[0]:
                        vals.append(calib.fix(x.text))
                for v in vals:
                    parsed = _profile_value(fld, v, period)
                    if parsed is not None:
                        if fld == "position":
                            rec["positions"], rec["pos"] = v, parsed
                        elif fld == "value":
                            rec["value"], rec["value_min"], rec["value_max"] = parsed["amount"], parsed["min"], parsed["max"]
                        else:
                            rec[fld] = parsed
                        break
                break
    if "pos" not in rec:
        for line in lines:
            for c in line:
                t = c.text.strip()
                if c.cy < img_h * 0.45 and _POS_CELL.match(t) and t.upper() == t and ("(" in t or t in ("GB", "GK", "BT", "ST", "MD", "DM")):
                    pos = parse_positions(t)
                    if pos:
                        rec["positions"], rec["pos"] = t, pos
                        break
            if "pos" in rec:
                break
    if attrs:
        rec["attributes"], rec["attr_source"] = attrs, src
    if not rec.get("name"):
        out["warnings"].append("Nom du joueur introuvable sur le profil.")
        return out
    if len(attrs) < 10:
        out["warnings"].append(f"Seulement {len(attrs)} attribut(s) lu(s) : ouvrez la page qui affiche les attributs.")
    out["players"].append(rec)
    return out


def _label_hit(text: str, aliases: list[str]) -> tuple[bool, str]:
    """Le texte est-il l'un des libellés attendus ? Retourne (trouvé, valeur sur la même cellule).

    Tolère l'espace avalé par l'OCR sur les petites polices (« Expirele »).
    """
    label = norm(text)
    compact = label.replace(" ", "")
    for al in aliases:
        if label == al or compact == al.replace(" ", ""):
            return True, ""
        if label.startswith(al + " "):
            return True, text.strip()[len(al):].strip(" :")
    return False, ""


def _profile_value(fld: str, text: str, period: str):
    if fld == "age":
        return parse_int(text, 14, 50)
    if fld == "value":
        return parse_money(text)
    if fld == "wage":
        return parse_wage(text, period)
    if fld == "contract_end":
        return parse_date(text)
    if fld == "height":
        v = parse_float(text)
        if v is None:
            return None
        return int(v * 100) if v < 3 else (int(v) if 140 <= v <= 220 else None)
    if fld == "condition":
        return parse_int(text, 0, 100)
    if fld == "form":
        v = parse_float(text)
        return v if v is not None and 1 <= v <= 10 else None
    if fld == "position":
        return parse_positions(text) or None
    t = text.strip()
    return t if _looks_like_name(t) else None


# ---------------------------------------------------------------- tactique
def count_role_labels(lines, kp: Knowledge4Parse) -> int:
    return sum(1 for line in lines for c in line if best_match(c.text, kp.role, 0.88))


def parse_tactic(lines, kp: Knowledge4Parse, calib: Calibration, img_w: int, img_h: int) -> dict:
    tactic: dict = {"formation": None, "mentalite": None, "instructions": [], "joueurs": []}
    warnings = []
    cells = [c for line in lines for c in line]
    for c in cells:
        m = FORMATION_RE.search(c.text)
        if m and tactic["formation"] is None:
            tactic["formation"] = m.group(1)
        t = calib.fix(c.text)
        ment = kp.mentality.get(norm(t))
        if ment and tactic["mentalite"] is None:
            tactic["mentalite"] = ment
        ins = best_match(t, kp.instruction, 0.9)
        if ins and ins not in tactic["instructions"]:
            tactic["instructions"].append(ins)
    for c in cells:
        role = best_match(calib.fix(c.text), kp.role, 0.88)
        if not role:
            continue
        # Nom du joueur : texte le plus proche au-dessus ou en dessous du rôle
        best = None
        for o in cells:
            if o is c or not _looks_like_name(o.text) or best_match(o.text, kp.role, 0.88):
                continue
            dy = abs(o.cy - c.cy)
            if dy < c.h * 0.4 or dy > c.h * 3.2 or abs(o.cx - c.cx) > max(c.w, o.w) * 0.75:
                continue
            if norm(o.text) in kp.instruction or norm(o.text) in kp.mentality:
                continue
            if best is None or dy < best[0]:
                best = (dy, o)
        tactic["joueurs"].append({
            "role": role, "joueur": _clean_name(calib.fix(best[1].text)) if best else None,
            "x": round(c.cx / img_w, 3), "y": round(c.cy / img_h, 3),
        })
    if not tactic["formation"]:
        warnings.append("Formation non lue (ex. « 4-2-3-1 ») : elle sera déduite si possible.")
    if not tactic["joueurs"]:
        warnings.append("Aucun rôle reconnu sur le terrain. Les noms de rôles peuvent être ajustés dans connaissances.json.")
    return {"doc": ("tactique", tactic), "warnings": warnings, "players": [], "headers": []}


# ---------------------------------------------------------------- finances
def parse_finances(lines, kp: Knowledge4Parse, calib: Calibration, settings: dict) -> dict:
    fin: dict = {}
    period = settings.get("periode_salaire", "semaine")
    for li, line in enumerate(lines):
        for c in line:
            for fld, aliases in kp.cfg.get("finances", {}).items():
                if fld in fin:
                    continue
                hit, inline = _label_hit(c.text, aliases)
                if not hit:
                    continue
                cands = [inline] if inline else []
                cands += [x.text for x in (right_of(line, c), below(lines, li, c)) if x is not None]
                for txt in cands:
                    txt = calib.fix(txt).strip()
                    m = parse_money(txt)
                    if not m:
                        continue
                    if fld in ("wage_budget", "wage_bill"):
                        fin[fld] = parse_wage(txt, period)  # ramené à la semaine
                    else:
                        neg = txt.startswith(("-", "−", "–", "("))
                        fin[fld] = -abs(m["amount"]) if neg else m["amount"]
                    break
    warnings = [] if fin else ["Aucun montant financier reconnu (solde, budgets)."]
    return {"doc": ("finances", fin) if fin else None, "warnings": warnings, "players": [], "headers": []}


# ---------------------------------------------------------------- classement
def parse_league_table(lines, kp: Knowledge4Parse, calib: Calibration) -> dict:
    cfg = kp.cfg
    found = detect_header(lines, cfg["colonnes"], cfg["champs_ecran"]["classement"], calib.data["colonnes"], min_hits=3)
    rows_out, headers, warnings = [], [], []
    num_fields = ("rank", "played", "won", "drawn", "lost", "goals_for", "goals_against", "goal_diff", "points")
    if found:
        hi, cols = found
        headers = [{"texte": c.text, "champ": c.field} for c in cols]
        for row in read_table(lines, hi, cols):
            rec = {}
            for idx, cell in row.items():
                f = cols[idx].field
                if f == "team":
                    rec["team"] = _clean_name(calib.fix(cell.text))
                elif f in num_fields:
                    rec[f] = parse_int(cell.text.replace("+", ""), -200, 400)
            if rec.get("team") and _looks_like_name(rec["team"]) and rec.get("points") is not None:
                rows_out.append(rec)
    if not rows_out:
        # Secours sans en-têtes : « 1  Équipe  12 8 2 2 24 10 +14 26 »
        for line in lines:
            nums = [parse_int(c.text.replace("+", ""), -200, 400) for c in line if re.fullmatch(r"[+-]?\d{1,3}", c.text.strip())]
            names = [c.text for c in line if _looks_like_name(c.text)]
            if len(nums) >= 6 and names:
                rec = {"team": _clean_name(calib.fix(max(names, key=len))), "rank": nums[0], "played": nums[1],
                       "won": nums[2], "drawn": nums[3], "lost": nums[4], "points": nums[-1]}
                if len(nums) >= 8:
                    rec["goals_for"], rec["goals_against"] = nums[5], nums[6]
                rows_out.append(rec)
        if rows_out:
            warnings.append("Classement lu sans en-têtes : vérifiez les colonnes.")
    for i, r in enumerate(rows_out):
        if r.get("rank") is None:
            r["rank"] = (rows_out[i - 1].get("rank") or i) + 1 if i else None
    if not rows_out:
        warnings.append("Classement illisible.")
    return {"doc": ("classement", rows_out) if rows_out else None, "warnings": warnings, "players": [], "headers": headers}


# ---------------------------------------------------------------- calendrier
def _date_with_ref(text: str, ref: str | None) -> str | None:
    d = parse_date(text)
    if d:
        return d
    m = _DAY_MONTH.search(text)
    if not m or not ref:
        return None
    mo = _month(m.group(2))
    if not mo:
        return None
    ry, rm = int(ref[:4]), int(ref[5:7])
    year = ry + (1 if mo < rm - 5 else (-1 if mo > rm + 6 else 0))  # saison à cheval sur deux années
    try:
        return date(year, mo, int(m.group(1))).isoformat()
    except ValueError:
        return None


def _venue(text: str) -> str | None:
    n = norm(text).strip("()")
    if n in ("d", "dom", "dom.", "domicile", "h", "home"):
        return "domicile"
    if n in ("e", "ext", "ext.", "exterieur", "a", "away"):
        return "exterieur"
    if n in ("n", "neutre", "neutral"):
        return "neutre"
    return None


def parse_fixtures(lines, kp: Knowledge4Parse, calib: Calibration, ref_date: str | None) -> dict:
    cfg = kp.cfg
    found = detect_header(lines, cfg["colonnes"], cfg["champs_ecran"]["calendrier"], calib.data["colonnes"], min_hits=2)
    out, headers, warnings = [], [], []
    body = lines
    cols = None
    if found:
        hi, cols = found
        headers = [{"texte": c.text, "champ": c.field} for c in cols]
        table = read_table(lines, hi, cols)
        for row in table:
            rec = {}
            for idx, cell in row.items():
                f = cols[idx].field
                txt = calib.fix(cell.text.strip())
                if f == "date":
                    rec["date"] = _date_with_ref(txt, ref_date)
                elif f == "opponent":
                    rec["opponent"] = _clean_name(txt)
                elif f == "competition":
                    rec["competition"] = txt
                elif f == "venue":
                    rec["venue"] = _venue(txt)
                elif f == "result":
                    m = _SCORE.search(txt)
                    if m:
                        rec["result"] = f"{m.group(1)}-{m.group(2)}"
            if rec.get("date") and rec.get("opponent"):
                out.append(rec)
    if not out:
        for line in body:
            d = next((x for x in (_date_with_ref(c.text, ref_date) for c in line) if x), None)
            if not d:
                continue
            rec = {"date": d}
            texts = []
            for c in line:
                t = calib.fix(c.text.strip())
                if _date_with_ref(t, ref_date):
                    continue
                v = _venue(t)
                m = _SCORE.fullmatch(t)
                if v and "venue" not in rec:
                    rec["venue"] = v
                elif m:
                    rec["result"] = f"{m.group(1)}-{m.group(2)}"
                elif _looks_like_name(t):
                    texts.append(t)
            if texts:
                rec["opponent"] = _clean_name(texts[0])
                if len(texts) > 1:
                    rec["competition"] = texts[1]
                out.append(rec)
        if out:
            warnings.append("Calendrier lu sans en-têtes : adversaire = premier texte après la date.")
    if not out:
        warnings.append("Aucun match lisible (date + adversaire).")
    return {"doc": ("calendrier", out) if out else None, "warnings": warnings, "players": [], "headers": headers}


# ---------------------------------------------------------------- staff
def parse_staff(lines, kp: Knowledge4Parse, calib: Calibration, settings: dict) -> dict:
    cfg = kp.cfg
    found = detect_header(lines, cfg["colonnes"], cfg["champs_ecran"]["staff"], calib.data["colonnes"], min_hits=2)
    out, headers, warnings = [], [], []
    if found:
        hi, cols = found
        headers = [{"texte": c.text, "champ": c.field} for c in cols]
        for row in read_table(lines, hi, cols):
            rec = {}
            for idx, cell in row.items():
                f = cols[idx].field
                txt = calib.fix(cell.text.strip())
                if f == "name":
                    rec["name"] = _clean_name(txt)
                elif f == "job":
                    rec["job"] = txt
                elif f == "age":
                    rec["age"] = parse_int(txt, 18, 90)
                elif f == "contract_end":
                    rec["contract_end"] = parse_date(txt)
                elif f == "wage":
                    rec["wage"] = parse_wage(txt, settings.get("periode_salaire", "semaine"))
                elif f == "nationality":
                    rec["nationality"] = txt
            if rec.get("name") and _looks_like_name(rec["name"]):
                out.append({k: v for k, v in rec.items() if v is not None})
    if not out:
        warnings.append("Liste du staff illisible (colonnes Nom / Fonction attendues).")
    return {"doc": ("staff", out) if out else None, "warnings": warnings, "players": [], "headers": headers}


# ---------------------------------------------------------------- point d'entrée
def parse_frame(tokens: list[Token], img: np.ndarray | None, img_w: int, img_h: int, kp: Knowledge4Parse,
                calib: Calibration, settings: dict, ref_date: str | None = None, force_screen: str | None = None) -> dict:
    """Analyse complète d'une capture : type d'écran + données structurées."""
    lines = build_lines(tokens)
    game_date = find_game_date(lines, img_h, img_w)
    attr_hits = count_attribute_labels(lines, kp)
    role_hits = count_role_labels(lines, kp)
    screen, conf, scores = classify(lines, img_h, kp.cfg, calib.data["titres"], attr_hits, role_hits)
    if force_screen:
        screen, conf = force_screen, 1.0
    names = {s["id"]: s["nom"] for s in kp.cfg["ecrans"]}
    result = {
        "screen": screen, "screen_name": names.get(screen, "Écran non reconnu"), "confidence": conf,
        "game_date": game_date, "players": [], "doc": None, "warnings": [], "headers": [],
        "titles": [c.text for line in lines for c in line if c.cy <= img_h * 0.24 and _looks_like_name(c.text)][:40],
        "n_tokens": len(tokens),
    }
    if screen is None:
        if len(tokens) > 15:
            result["warnings"].append("Écran non reconnu. S'il s'agit d'un écran utile, indiquez-le dans le calibrage.")
        return result
    ref = game_date or ref_date
    if screen in PLAYER_SCREENS:
        part = parse_player_table(lines, img, kp, calib, screen, settings)
    elif screen == "profil":
        part = parse_profile(lines, img, kp, calib, img_w, img_h, settings)
    elif screen == "tactique":
        part = parse_tactic(lines, kp, calib, img_w, img_h)
    elif screen == "finances":
        part = parse_finances(lines, kp, calib, settings)
    elif screen == "classement":
        part = parse_league_table(lines, kp, calib)
    elif screen == "calendrier":
        part = parse_fixtures(lines, kp, calib, ref)
    elif screen == "staff":
        part = parse_staff(lines, kp, calib, settings)
    else:
        part = {}
    for k in ("players", "doc", "warnings", "headers"):
        if part.get(k):
            result[k] = part[k]
    return result
