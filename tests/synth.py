"""Fabrique de fausses captures d'écran « façon FM » pour tester la chaîne OCR sans le jeu."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
BG, PANEL, FG, DIM = (22, 25, 33), (30, 34, 45), (232, 234, 240), (150, 156, 170)


def font(size: int):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


class Screen:
    def __init__(self, w=1920, h=1080, title="", date="Ven. 13 nov. 2026", club="FC Valmont"):
        self.w, self.h = w, h
        self.s = h / 1080
        self.img = Image.new("RGB", (w, h), BG)
        self.d = ImageDraw.Draw(self.img)
        self.d.rectangle([0, 0, w, int(70 * self.s)], fill=PANEL)
        self.text(40, 18, title, 30)
        self.text(w - int(330 * self.s) / self.s, 24, date, 20)
        self.text(40, 86, club, 18, DIM)

    def text(self, x, y, txt, size=18, fill=FG, anchor="la"):
        self.d.text((int(x * self.s) if x <= 1920 else int(x), int(y * self.s)), str(txt), font=font(max(9, int(size * self.s))), fill=fill, anchor=anchor)

    def stars(self, x, y, n):
        s = self.s
        for i in range(int(n)):
            self.d.rectangle([int((x + i * 20) * s), int(y * s), int((x + i * 20 + 15) * s), int((y + 15) * s)], fill=(240, 190, 40))
        if n % 1:
            i = int(n)
            self.d.rectangle([int((x + i * 20) * s), int(y * s), int((x + i * 20 + 7) * s), int((y + 15) * s)], fill=(240, 190, 40))

    def array(self) -> np.ndarray:
        return np.ascontiguousarray(np.array(self.img)[:, :, ::-1])  # BGR


def squad_screen(players, w=1920, h=1080, title="Effectif", with_club=False) -> np.ndarray:
    sc = Screen(w, h, title)
    cols = [("Nom", 60), ("Poste", 420), ("Âge", 640), ("Niveau", 720), ("Potentiel", 860), ("Valeur", 1010), ("Salaire", 1210),
            ("Contrat", 1400), ("Moral", 1560)]
    if with_club:
        cols.append(("Club", 1700))
    for label, x in cols:
        sc.text(x, 150, label, 17, DIM)
    for i, p in enumerate(players):
        y = 192 + i * 34
        sc.text(60, y, p["name"])
        sc.text(420, y, p["positions"])
        sc.text(640, y, p["age"])
        sc.stars(720, y + 3, p["ability_stars"])
        sc.stars(860, y + 3, p["potential_stars"])
        sc.text(1010, y, p["value_txt"])
        sc.text(1210, y, p["wage_txt"])
        sc.text(1400, y, p["contract_txt"])
        sc.text(1560, y, p["morale"])
        if with_club:
            sc.text(1700, y, p.get("club", ""))
    return sc.array()


def profile_screen(name, positions, attrs_by_col, info, w=1920, h=1080, bars=False) -> np.ndarray:
    sc = Screen(w, h, "Profil")
    sc.text(60, 120, name, 44)
    sc.text(60, 180, positions, 20)
    x = 60
    for label, value in info:
        sc.text(x, 230, label, 15, DIM)
        sc.text(x, 254, value, 19)
        x += 300
    for ci, (heading, rows) in enumerate(attrs_by_col):
        x0 = 60 + ci * 460
        sc.text(x0, 330, heading, 22, DIM)
        for ri, (label, val) in enumerate(rows):
            y = 376 + ri * 38
            sc.text(x0, y, label)
            if bars:
                s = sc.s
                sc.d.rectangle([int((x0 + 250) * s), int((y + 6) * s), int((x0 + 250 + 150) * s), int((y + 18) * s)], fill=(70, 76, 92))
                sc.d.rectangle([int((x0 + 250) * s), int((y + 6) * s), int((x0 + 250 + 150 * val / 20) * s), int((y + 18) * s)], fill=(60, 200, 120))
            else:
                sc.text(x0 + 330, y, val)
    return sc.array()


def tactic_screen(formation, mentality, instructions, lineup, w=1920, h=1080) -> np.ndarray:
    sc = Screen(w, h, "Tactique")
    sc.text(60, 130, formation, 28)
    sc.text(300, 136, "Mentalité", 16, DIM)
    sc.text(420, 134, mentality, 20)
    for i, ins in enumerate(instructions):
        sc.text(1400, 220 + i * 40, ins, 18)
    s = sc.s
    sc.d.rectangle([int(60 * s), int(200 * s), int(1300 * s), int(1040 * s)], fill=(28, 70, 48))
    for name, role, x, y in lineup:
        sc.text(60 + x * 1240, 210 + (1 - y) * 780, name, 17, anchor="ma")
        sc.text(60 + x * 1240, 236 + (1 - y) * 780, role, 15, (200, 220, 205), anchor="ma")
    return sc.array()


def finances_screen(rows, w=1920, h=1080) -> np.ndarray:
    sc = Screen(w, h, "Finances")
    for i, (label, value) in enumerate(rows):
        sc.text(80, 200 + i * 60, label, 20, DIM)
        sc.text(520, 200 + i * 60, value, 22)
    return sc.array()


def table_screen(rows, w=1920, h=1080) -> np.ndarray:
    sc = Screen(w, h, "Classement")
    heads = [("Pos", 60), ("Équipe", 140), ("J", 700), ("G", 770), ("N", 840), ("P", 910), ("BP", 980), ("BC", 1050), ("Diff", 1120), ("Pts", 1210)]
    for label, x in heads:
        sc.text(x, 150, label, 17, DIM)
    for i, r in enumerate(rows):
        y = 192 + i * 34
        for (label, x), v in zip(heads, r):
            sc.text(x, y, v)
    return sc.array()


def fixtures_screen(rows, w=1920, h=1080) -> np.ndarray:
    sc = Screen(w, h, "Calendrier")
    heads = [("Date", 60), ("Adversaire", 320), ("Lieu", 760), ("Compétition", 900), ("Résultat", 1300)]
    for label, x in heads:
        sc.text(x, 150, label, 17, DIM)
    for i, r in enumerate(rows):
        for (label, x), v in zip(heads, r):
            sc.text(x, 192 + i * 34, v)
    return sc.array()
