"""Reconstruction de la mise en page à partir des mots lus : lignes, cellules, tableaux.

Aucune position n'est codée en dur : tout est déduit de l'alignement des
textes, ce qui rend la lecture indépendante de la résolution, du zoom et du skin.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..textutil import norm
from .ocr import Token


@dataclass
class Cell:
    text: str
    x: float
    y: float
    w: float
    h: float
    conf: float = 1.0
    tokens: list[Token] = field(default_factory=list)

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def group_rows(tokens: list[Token]) -> list[list[Token]]:
    """Regroupe les mots situés sur la même ligne de texte."""
    rows: list[dict] = []
    for t in sorted(tokens, key=lambda t: (t.cy, t.x)):
        placed = False
        for r in reversed(rows[-6:]):
            if abs(t.cy - r["cy"]) <= 0.5 * min(t.h, r["h"]) + 1:
                r["items"].append(t)
                n = len(r["items"])
                r["cy"] += (t.cy - r["cy"]) / n
                r["h"] += (t.h - r["h"]) / n
                placed = True
                break
        if not placed:
            rows.append({"cy": t.cy, "h": t.h, "items": [t]})
    rows.sort(key=lambda r: r["cy"])
    return [sorted(r["items"], key=lambda t: t.x) for r in rows]


def merge_cells(row: list[Token], gap_ratio: float = 0.75) -> list[Cell]:
    """Fusionne les mots proches en cellules (« Kylian » + « Mbappé »)."""
    cells: list[Cell] = []
    for t in row:
        if cells:
            c = cells[-1]
            if t.x - c.x1 <= gap_ratio * max(t.h, c.h):
                y0, y1 = min(c.y, t.y), max(c.y1, t.y1)
                sep = "" if t.x - c.x1 < -1 else " "
                c.text = f"{c.text}{sep}{t.text}"
                c.w = t.x1 - c.x
                c.y, c.h = y0, y1 - y0
                c.conf = min(c.conf, t.conf)
                c.tokens.append(t)
                continue
        cells.append(Cell(t.text, t.x, t.y, t.w, t.h, t.conf, [t]))
    return cells


def build_lines(tokens: list[Token]) -> list[list[Cell]]:
    return [merge_cells(r) for r in group_rows(tokens)]


@dataclass
class Column:
    text: str
    field: str | None
    x0: float
    x1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


def detect_header(lines: list[list[Cell]], aliases: dict[str, list[str]], wanted: list[str],
                  extra: dict[str, str] | None = None, min_hits: int = 2) -> tuple[int, list[Column]] | None:
    """Trouve la ligne d'en-têtes d'un tableau.

    aliases : champ → libellés possibles (normalisés) ; wanted : champs
    autorisés sur cet écran, par ordre de priorité ; extra : libellés appris
    au calibrage ou noms d'attributs (libellé normalisé → champ).
    """
    extra = extra or {}
    best: tuple[int, int, list[Column]] | None = None
    for i, line in enumerate(lines):
        if len(line) < min_hits:
            continue
        used: set[str] = set()
        cols: list[Column] = []
        hits = 0
        for c in line:
            label = norm(c.text)
            fld = extra.get(label)
            if fld is None:
                for f in wanted:
                    if f not in used and label in aliases.get(f, ()):
                        fld = f
                        break
            if fld and fld not in used:
                used.add(fld)
                hits += 1
            else:
                fld = None
            cols.append(Column(c.text, fld, c.x, c.x1))
        if hits >= min_hits and (best is None or hits > best[0]):
            best = (hits, i, cols)
    if best is None:
        return None
    return best[1], best[2]


def read_table(lines: list[list[Cell]], header_index: int, columns: list[Column]) -> list[dict[int, Cell]]:
    """Range chaque cellule sous la colonne la mieux alignée (gauche, centre ou droite)."""
    out: list[dict[int, Cell]] = []
    for line in lines[header_index + 1:]:
        row: dict[int, Cell] = {}
        for c in line:
            idx = min(range(len(columns)), key=lambda k: min(
                abs(c.x - columns[k].x0), abs(c.cx - columns[k].cx), abs(c.x1 - columns[k].x1)))
            if idx in row:
                prev = row[idx]
                row[idx] = Cell(f"{prev.text} {c.text}", prev.x, min(prev.y, c.y), c.x1 - prev.x,
                                max(prev.y1, c.y1) - min(prev.y, c.y), min(prev.conf, c.conf), prev.tokens + c.tokens)
            else:
                row[idx] = c
        if row:
            out.append(row)
    return out


def right_of(line: list[Cell], cell: Cell, max_dist: float | None = None) -> Cell | None:
    """Première cellule à droite sur la même ligne."""
    cands = [c for c in line if c.x >= cell.x1 - 1 and c is not cell]
    if not cands:
        return None
    c = min(cands, key=lambda c: c.x)
    if max_dist is not None and c.x - cell.x1 > max_dist:
        return None
    return c


def below(lines: list[list[Cell]], line_index: int, cell: Cell) -> Cell | None:
    """Cellule juste en dessous, alignée à gauche ou centrée (libellé au-dessus de sa valeur)."""
    for line in lines[line_index + 1: line_index + 3]:
        for c in line:
            if c.y - cell.y1 > 3.0 * cell.h:
                return None
            if abs(c.x - cell.x) <= cell.h * 0.8 or abs(c.cx - cell.cx) <= cell.h * 0.8:
                return c
    return None
