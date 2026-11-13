"""Scan automatique testé contre un jeu simulé (aucune touche réelle n'est envoyée)."""
import pytest

from fm_assistant.capture.autopilot import AutoScan, LostFocus
from fm_assistant.capture.inputs import parse_combo

SQUAD = [f"Joueur {chr(65 + i)}" for i in range(14)]
VISIBLE = 5


class FakeGame:
    """Simule FM : une liste qui défile, des profils, des écrans atteints par raccourci."""

    def __init__(self, keys_work=True, focus_until=None):
        self.screen, self.offset, self.profile = "effectif", 0, 0
        self.keys_work, self.focus_until, self.actions, self.reads = keys_work, focus_until, [], 0

    # lecteur
    def read(self):
        self.reads += 1
        if self.focus_until is not None and self.reads > self.focus_until:
            raise LostFocus()
        if self.screen == "effectif":
            rows = SQUAD[self.offset:self.offset + VISIBLE]
            return {"screen": "effectif", "players": [{"name": n, "_box": [100, 200 + 30 * i]} for i, n in enumerate(rows)]}
        if self.screen == "profil":
            return {"screen": "profil", "players": [{"name": SQUAD[self.profile], "attributes": {"pace": 10}}]}
        return {"screen": self.screen, "players": [], "resume": f"{self.screen} lu"}

    # pilote
    def prepare(self):
        self.actions.append("prepare")

    def scroll(self, point, notches):
        self.actions.append(("scroll", notches))
        if self.screen == "effectif":
            self.offset = max(0, min(len(SQUAD) - VISIBLE, self.offset - notches))

    def click(self, box):
        self.actions.append(("click", tuple(box)))
        if self.screen == "effectif":
            self.profile = self.offset + (box[1] - 200) // 30
            self.screen = "profil"

    def press(self, combo):
        self.actions.append(("press", combo))
        if not self.keys_work:
            return
        if combo == "n" and self.screen == "profil":
            self.profile = (self.profile + 1) % len(SQUAD)
        elif combo == "alt+gauche" and self.screen == "profil":
            self.screen = "effectif"
        elif combo.startswith("f"):
            self.screen = {"f1": "effectif", "f2": "tactique", "f3": "finances", "f4": "classement", "f5": "calendrier"}.get(combo, self.screen)


def run(game, keys, **opts):
    scan = AutoScan(game, game, lambda: {"raccourcis": keys, "delai_auto": 0.2}, sleep=lambda s: None)
    scan.run({"read_cost": 3.0, **opts})
    return scan.status


ALL = {"suivant": "n", "retour": "alt+gauche", "effectif": "f1", "tactique": "f2", "finances": "f3", "classement": "f4", "calendrier": "f5"}


def test_full_scan_with_next_key():
    game = FakeGame()
    st = run(game, ALL)
    assert st["termine"] and not st["erreur"]
    assert st["joueurs"] == 14 and st["profils"] == 14
    assert st["ecrans"] == ["tactique", "finances", "classement", "calendrier"]
    assert game.offset == 0 or game.screen != "effectif"   # la liste a été remontée avant les profils
    assert sum(1 for a in game.actions if a == ("press", "n")) == 14  # s'arrête dès le retour au premier joueur


def test_profiles_by_clicking_each_name_when_only_back_is_known():
    game = FakeGame()
    st = run(game, {"retour": "alt+gauche"}, ecrans=[])
    assert st["termine"] and st["profils"] == 14
    assert sum(1 for a in game.actions if a[0] == "click") == 14


def test_without_profile_shortcuts_only_the_list_is_read():
    game = FakeGame()
    st = run(game, {}, ecrans=[])
    assert st["termine"] and st["joueurs"] == 14 and st["profils"] == 0
    assert not any(a[0] in ("click", "press") for a in game.actions if a != "prepare")
    assert any("aucun raccourci" in line for line in st["journal"])


def test_useless_next_key_is_detected_and_does_not_loop():
    game = FakeGame(keys_work=False)
    st = run(game, {"suivant": "n"}, ecrans=[])
    assert st["profils"] == 1
    assert sum(1 for a in game.actions if a == ("press", "n")) == 1
    assert any("ne semble pas avoir d'effet" in line for line in st["journal"])


def test_unreachable_screen_is_skipped_not_fatal():
    game = FakeGame()
    st = run(game, {**ALL, "finances": "f9"}, profils=False)
    assert st["termine"] and st["ecrans"] == ["tactique", "classement", "calendrier"]
    assert any("Finances : écran non atteint" in line for line in st["journal"])


def test_stops_as_soon_as_game_loses_focus():
    game = FakeGame(focus_until=3)
    st = run(game, ALL)
    n_actions = len(game.actions)
    assert st["erreur"] and "premier plan" in st["erreur"] and not st["termine"] and not st["actif"]
    assert len(game.actions) == n_actions and game.reads == 4


def test_shortcut_parsing():
    assert parse_combo("Ctrl + Maj + P") == ["ctrl", "maj", "p"]
    assert parse_combo("alt+gauche") == ["alt", "gauche"]
    assert parse_combo("souris_precedent") == ["souris_precedent"]
    assert parse_combo("f6") == ["f6"]
    for bad in ("", "ctrl+bidule", "windows+r"):
        with pytest.raises(ValueError):
            parse_combo(bad)
