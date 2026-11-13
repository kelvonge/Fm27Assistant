"""Normalisation du texte lu à l'écran : accents, montants, dates, postes.

Toutes les fonctions retournent None quand la valeur n'est pas lisible :
l'application préfère « inconnu » à une valeur inventée.
"""
from __future__ import annotations

import calendar
import difflib
import re
import unicodedata

_SPACES = re.compile(r"\s+")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str | None) -> str:
    """Minuscules, sans accents, espaces compactés, ponctuation de bord retirée."""
    if not s:
        return ""
    s = strip_accents(str(s)).lower().replace("’", "'").replace("`", "'")
    s = _SPACES.sub(" ", s).strip(" :;,|*•·-–—\t")
    return s


def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def best_match(text: str, candidates: dict[str, str], cutoff: float = 0.84) -> str | None:
    """Associe un texte lu à une clé connue (exact puis approché)."""
    t = norm(text)
    if not t:
        return None
    if t in candidates:
        return candidates[t]
    if len(t) < 4:
        return None
    best, score = None, cutoff
    for cand, key in candidates.items():
        if abs(len(cand) - len(t)) > 3:
            continue
        r = similar(t, cand)
        if r > score:
            best, score = key, r
    return best


_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8", "Z": "2", "g": "9"})


def parse_int(s, lo: int | None = None, hi: int | None = None) -> int | None:
    """Entier tolérant aux confusions OCR (O/0, l/1…), borné si demandé."""
    if s is None:
        return None
    t = str(s).strip()
    fixed = re.fullmatch(r"(-?\d{1,4})", t.translate(_DIGIT_FIX))
    if fixed:
        val = int(fixed.group(1))
    else:
        m = re.search(r"-?\d+", t)
        if not m:
            return None
        val = int(m.group(0))
    if lo is not None and val < lo:
        return None
    if hi is not None and val > hi:
        return None
    return val


def parse_float(s) -> float | None:
    if s is None:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


_MONEY = re.compile(r"(-?\d[\d\s  .,']*)\s*(mds?|md|m|k|b)?(?![a-z])", re.I)
_MULT = {"k": 1e3, "m": 1e6, "md": 1e9, "mds": 1e9, "b": 1e9}


def _number(txt: str, has_suffix: bool) -> float | None:
    t = re.sub(r"[\s  ']", "", txt).rstrip(".,")
    if not t or not re.search(r"\d", t):
        return None
    if has_suffix:
        # « 4,5 » ou « 4.5 » : séparateur décimal
        if t.count(",") + t.count(".") == 1:
            return float(t.replace(",", "."))
        return float(re.sub(r"[.,]", "", t))
    # Sans suffixe : un séparateur suivi de 3 chiffres est un séparateur de milliers
    if re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", t):
        return float(re.sub(r"[.,]", "", t))
    if re.fullmatch(r"-?\d+[.,]\d{1,2}", t):
        return float(t.replace(",", "."))
    try:
        return float(re.sub(r"[.,]", "", t))
    except ValueError:
        return None


def parse_money(s: str | None) -> dict | None:
    """« 4,5 M € », « €325K », « 12 500 € », « 4M € - 6M € » → {amount, min, max}."""
    if not s:
        return None
    t = strip_accents(str(s)).lower()
    t = re.sub(r"p/[sma]\b|/\s*(sem|mois|an)\w*|par (semaine|mois|an)|p/w|p/y", " ", t)
    vals = []
    for m in _MONEY.finditer(t):
        suffix = (m.group(2) or "").lower()
        n = _number(m.group(1), bool(suffix))
        if n is None:
            continue
        vals.append(n * _MULT.get(suffix, 1))
    if not vals:
        return None
    lo, hi = min(vals[:2]), max(vals[:2])
    return {"amount": (lo + hi) / 2, "min": lo, "max": hi}


def wage_period(s: str | None) -> str | None:
    t = norm(s)
    if re.search(r"p/s|/ ?sem|par semaine|p/w|/ ?w\b", t):
        return "semaine"
    if re.search(r"p/m|/ ?mois|par mois", t):
        return "mois"
    if re.search(r"p/a|/ ?an\b|par an|p/y", t):
        return "an"
    return None


def parse_wage(s: str | None, default_period: str = "semaine") -> float | None:
    """Salaire converti en montant hebdomadaire."""
    money = parse_money(s)
    if not money:
        return None
    period = wage_period(s) or default_period
    amount = money["amount"]
    if period == "mois":
        return amount * 12 / 52
    if period == "an":
        return amount / 52
    return amount


_MONTHS = {
    "jan": 1, "fev": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4, "mai": 5, "may": 5, "juin": 6, "jun": 6,
    "juil": 7, "jul": 7, "aou": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _month(word: str) -> int | None:
    w = norm(word).strip(".")
    for k in (w[:4], w[:3]):
        if k in _MONTHS:
            return _MONTHS[k]
    return None


_DATE_NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})\b")
_DATE_TXT = re.compile(r"\b(\d{1,2})(?:er)?\s+([A-Za-zÀ-ÿ]{3,10})\.?\s+(\d{4})\b")
_DATE_MY = re.compile(r"\b([A-Za-zÀ-ÿ]{3,10})\.?\s+(\d{4})\b")


def _iso(y: int, m: int, d: int) -> str | None:
    if not (1 <= m <= 12 and 1990 <= y <= 2150):
        return None
    last = calendar.monthrange(y, m)[1]
    if not 1 <= d <= last:
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def parse_date(s: str | None) -> str | None:
    """Date FR/EN → ISO (AAAA-MM-JJ). Format numérique supposé jour/mois/année."""
    if not s:
        return None
    t = str(s)
    m = _DATE_TXT.search(t)
    if m:
        mo = _month(m.group(2))
        if mo:
            return _iso(int(m.group(3)), mo, int(m.group(1)))
    m = _DATE_NUM.search(t)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        return _iso(y, int(m.group(2)), int(m.group(1)))
    m = _DATE_MY.search(t)
    if m:
        mo = _month(m.group(1))
        if mo:
            y = int(m.group(2))
            return _iso(y, mo, calendar.monthrange(y, mo)[1])
    return None


_LINES = {
    "gb": "GK", "gk": "GK", "g": "GK",
    "d": "D", "dl": "WB", "wb": "WB", "al": "WB",
    "md": "DM", "dm": "DM", "mdc": "DM",
    "m": "M", "mo": "AM", "am": "AM",
    "bt": "ST", "st": "ST", "bu": "ST", "at": "ST", "a": "ST", "s": "ST", "f": "ST",
}
_SIDES = {"d": "R", "r": "R", "g": "L", "l": "L", "c": "C"}
_POS_GROUP = re.compile(r"([A-Za-z/ ]+?)\s*(?:\(([A-Za-z ]+)\))?\s*(?:,|;|$)")


def parse_positions(s: str | None) -> list[str]:
    """« D (C), MD, M (C) » ou « AM (RL), ST (C) » → ['DC', 'DM', 'MC'] etc."""
    if not s:
        return []
    out: list[str] = []
    for m in _POS_GROUP.finditer(str(s).strip()):
        lines = [x for x in re.split(r"[/ ]+", m.group(1).strip().lower()) if x]
        sides = [_SIDES[c] for c in (m.group(2) or "").lower() if c in _SIDES]
        for token in lines:
            line = _LINES.get(token)
            if not line:
                continue
            if line in ("GK", "DM", "ST"):
                cands = [line]
            elif line == "WB":
                cands = [f"WB{sd}" for sd in sides if sd in "RL"] or ["WBR", "WBL"]
            else:
                cands = [f"{line}{sd}" for sd in (sides or ["C"])]
            for c in cands:
                if c not in out:
                    out.append(c)
    return out


def name_key(name: str | None) -> str:
    return re.sub(r"[^a-z ]", "", norm(name).replace("-", " ").replace("'", " ")).strip()


def names_compatible(a: str, b: str) -> bool:
    """Vrai si deux clés de nom désignent probablement le même joueur
    (« k mbappe » ↔ « kylian mbappe »)."""
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    if len(ta) < 2 or len(tb) < 2 or ta[-1] != tb[-1]:
        return False
    fa, fb = ta[0], tb[0]
    if len(fa) == 1 or len(fb) == 1:
        return fa[0] == fb[0]
    return False


def fmt_money(v: float | None, cur: str = "€") -> str:
    if v is None:
        return "inconnu"
    a = abs(v)
    if a >= 1e9:
        txt = f"{v / 1e9:.2f}".rstrip("0").rstrip(".") + " Md"
    elif a >= 1e6:
        txt = f"{v / 1e6:.1f}".rstrip("0").rstrip(".") + " M"
    elif a >= 1e3:
        txt = f"{v / 1e3:.0f} k"
    else:
        txt = f"{v:.0f}"
    return f"{txt.replace('.', ',')} {cur}"


def ordinal(n) -> str:
    """1 → « 1er », 2 → « 2e »."""
    if n is None:
        return "?"
    return f"{n}er" if n == 1 else f"{n}e"


def fr(x, decimals: int = 1) -> str:
    """Nombre au format français (virgule décimale) pour les phrases d'explication."""
    return f"{x:.{decimals}f}".replace(".", ",")
