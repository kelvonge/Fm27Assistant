"""Lecture visuelle quand le texte ne suffit pas : étoiles et barres d'attributs.

Ces lectures sont approximatives ; elles sont marquées comme telles dans les
données (attr_source = « barres ») pour que l'interface puisse le signaler.
"""
from __future__ import annotations

import numpy as np


def _crop(img: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> np.ndarray | None:
    h, w = img.shape[:2]
    x0, x1 = int(max(0, x0)), int(min(w, x1))
    y0, y1 = int(max(0, y0)), int(min(h, y1))
    if x1 - x0 < 6 or y1 - y0 < 4:
        return None
    return img[y0:y1, x0:x1]


def _runs(mask_cols: np.ndarray, max_gap: int = 1) -> list[tuple[int, int]]:
    """Segments consécutifs de colonnes actives (petits trous tolérés)."""
    runs, start, gap = [], None, 0
    for i, on in enumerate(mask_cols):
        if on:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                runs.append((start, i - gap + 1))
                start, gap = None, 0
    if start is not None:
        runs.append((start, len(mask_cols) - gap))
    return runs


def star_groups(img: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float, float]]:
    """Repère les rangées d'étoiles dorées d'une ligne de tableau.

    Retourne des groupes (x début, x fin, nombre d'étoiles — demies comprises),
    en coordonnées de l'image. Les étoiles vides/grises ne sont pas comptées.
    """
    import cv2

    crop = _crop(img, x0, y0, x1, y1)
    if crop is None:
        return []
    off = int(max(0, x0))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gold = (hsv[:, :, 0] >= 12) & (hsv[:, :, 0] <= 36) & (hsv[:, :, 1] > 110) & (hsv[:, :, 2] > 140)
    cols = gold.sum(axis=0) >= max(2, crop.shape[0] * 0.12)
    runs = [(a, b) for a, b in _runs(cols) if b - a >= 3]
    if not runs:
        return []
    unit = max(b - a for a, b in runs)
    row_h = crop.shape[0]
    if unit < row_h * 0.25 or unit > row_h * 2.2:
        return []  # trop fin ou trop large pour être des étoiles (texte coloré, bandeau…)
    groups, cur = [], [runs[0]]
    for r in runs[1:]:
        if r[0] - cur[-1][1] > 0.9 * unit:
            groups.append(cur)
            cur = [r]
        else:
            cur.append(r)
    groups.append(cur)
    out = []
    for g in groups:
        total = sum(max(0.5, round((b - a) / unit * 2) / 2) for a, b in g)
        if 0.5 <= total <= 5:
            out.append((off + g[0][0], off + g[-1][1], total))
    return out


def count_stars(img: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> float | None:
    """Nombre d'étoiles dans une zone ne contenant qu'une seule rangée."""
    groups = star_groups(img, x0, y0, x1, y1)
    return groups[0][2] if len(groups) == 1 else None


def bar_value(img: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> int | None:
    """Estime un attribut (1-20) d'après la longueur d'une barre horizontale.

    La barre est la partie nettement colorée ; le rail, s'il existe, est la
    partie restante d'une couleur différente du fond.
    """
    import cv2

    crop = _crop(img, x0, y0, x1, y1)
    if crop is None:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).astype(np.int16)
    border = np.concatenate([hsv[0], hsv[-1]])
    bg_v = float(np.median(border[:, 2]))
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    filled = (sat > 90) & (val > 90)
    track = (np.abs(val - bg_v) > 14) & ~filled
    rows = filled.sum(axis=1)
    if rows.max() < 6:
        return None
    band = rows >= rows.max() * 0.6  # lignes de pixels où se trouve la barre
    f_cols = filled[band].mean(axis=0) > 0.5
    t_cols = track[band].mean(axis=0) > 0.5
    f_runs = _runs(f_cols, 2)
    if not f_runs:
        return None
    a, b = max(f_runs, key=lambda r: r[1] - r[0])
    if b - a < 4:
        return None
    end = b
    for ta, tb in _runs(t_cols, 2):
        if ta >= b - 2 and ta - end <= 4:
            end = tb
    total = end - a
    if end == b:
        # Pas de rail visible : impossible de connaître l'échelle sans calibrage
        return None
    ratio = (b - a) / max(1, total)
    return int(max(1, min(20, round(ratio * 20))))
