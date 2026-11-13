"""Scan automatique : l'assistant parcourt lui-même les écrans de FM.

Déroulé : fait défiler l'effectif, ouvre chaque profil (touche « joueur
suivant », ou clic sur chaque nom + « retour »), puis visite tactique,
finances, classement et calendrier. Quand un raccourci n'est pas configuré,
il demande d'ouvrir l'écran à la main et reprend dès qu'il le voit.

Sécurités : aucune action si FM n'est pas au premier plan (passer sur une
autre fenêtre arrête le scan), clics limités à la fenêtre du jeu, et seules
des touches de navigation sont envoyées. La sauvegarde n'est jamais touchée.

La logique ne dépend ni de Windows ni de l'OCR : elle reçoit un « lecteur »
et un « pilote », ce qui permet de la tester avec un jeu simulé.
"""
from __future__ import annotations

import threading
import time

from ..textutil import name_key

NAMES = {"effectif": "Effectif", "profil": "Profil joueur", "tactique": "Tactique", "finances": "Finances",
         "classement": "Classement", "calendrier": "Calendrier"}
OTHER_SCREENS = ("tactique", "finances", "classement", "calendrier")


class Stopped(Exception):
    """Arrêt demandé par l'utilisateur."""


class LostFocus(Exception):
    """FM n'est plus au premier plan."""


class AutoScan:
    def __init__(self, reader, driver, settings_provider, sleep=time.sleep):
        self.reader, self.driver, self.settings_provider, self.sleep = reader, driver, settings_provider, sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.on_state = None  # appelé avec True au démarrage, False à la fin
        self.status = self._fresh()

    @staticmethod
    def _fresh() -> dict:
        return {"actif": False, "phase": None, "message": "", "joueurs": 0, "profils": 0, "total": None,
                "journal": [], "erreur": None, "termine": False, "ecrans": []}

    # ------------------------------------------------------------ pilotage
    def start(self, options: dict | None = None) -> bool:
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self.status = self._fresh()
        self.status["actif"] = True
        self._thread = threading.Thread(target=self.run, args=(options or {},), name="fma-autoscan", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _log(self, text: str) -> None:
        self.status["message"] = text
        self.status["journal"] = (self.status["journal"] + [text])[-40:]

    def _pause(self, seconds: float) -> None:
        if self._stop.is_set():
            raise Stopped()
        self.sleep(seconds)
        if self._stop.is_set():
            raise Stopped()

    def _read(self) -> dict:
        if self._stop.is_set():
            raise Stopped()
        return self.reader.read() or {"screen": None, "players": []}

    def _wait_for(self, screens, timeout: float, prompt: str | None = None) -> dict | None:
        if prompt:
            self.status["message"] = prompt
        waited = 0.0
        while True:
            p = self._read()
            if p.get("screen") in screens:
                return p
            if waited >= timeout:
                return None
            self._pause(1.0)
            waited += 1.0 + self.read_cost

    def _goto(self, screen: str, manual_timeout: float = 45) -> dict | None:
        """Va sur un écran : raccourci s'il est configuré, sinon demande à l'utilisateur."""
        p = self._read()
        if p.get("screen") == screen:
            return p
        key = (self.keys.get(screen) or "").strip()
        if key:
            self.driver.press(key)
            self._pause(self.delay)
            p = self._wait_for([screen], 5)
            if p:
                return p
            self._log(f"Le raccourci « {key} » n'a pas ouvert l'écran {NAMES[screen]}.")
        return self._wait_for([screen], manual_timeout,
                              f"Ouvrez l'écran {NAMES[screen]} dans FM : le scan reprendra tout seul (attente {int(manual_timeout)} s).")

    # ------------------------------------------------------------ déroulé
    def run(self, options: dict) -> None:
        st = self.status
        settings = self.settings_provider()
        self.keys = dict(settings.get("raccourcis") or {})
        self.delay = max(0.2, float(settings.get("delai_auto") or 0.8))
        self.read_cost = float(options.get("read_cost", 1.5))  # durée approximative d'une lecture OCR
        if self.on_state:
            self.on_state(True)
        try:
            self.driver.prepare()
            st["phase"] = "liste"
            self._log("Lecture de l'effectif…")
            p = self._goto("effectif", 60)
            if not p:
                raise RuntimeError("Écran Effectif introuvable : ouvrez-le dans FM puis relancez le scan.")
            names = self._scan_list(p)
            st["total"] = len(names)
            self._log(f"Effectif : {len(names)} joueur(s) lu(s).")
            if options.get("profils", True):
                st["phase"] = "profils"
                self._scan_profiles(names)
            for screen in options.get("ecrans", OTHER_SCREENS):
                st["phase"] = screen
                self._log(f"Écran {NAMES[screen]}…")
                p = self._goto(screen)
                if p:
                    st["ecrans"].append(screen)
                    self._log(f"{NAMES[screen]} : {p.get('resume') or 'lu'}.")
                else:
                    self._log(f"{NAMES[screen]} : écran non atteint, étape passée.")
            st["termine"] = True
            self._log(f"Scan terminé : {st['joueurs']} joueur(s), {st['profils']} profil(s), {len(st['ecrans'])} autre(s) écran(s).")
        except Stopped:
            self._log("Scan arrêté à votre demande.")
        except LostFocus:
            st["erreur"] = "Scan interrompu : FM n'est plus au premier plan. Rien d'autre n'a été envoyé au jeu."
            self._log(st["erreur"])
        except Exception as exc:
            st["erreur"] = str(exc)
            self._log(f"Scan interrompu : {exc}")
        finally:
            st["actif"] = False
            st["phase"] = None
            if self.on_state:
                self.on_state(False)

    def _list_point(self, p: dict):
        boxes = [pl["_box"] for pl in p.get("players", []) if pl.get("_box")]
        if not boxes:
            return None
        return (sum(b[0] for b in boxes) / len(boxes), sum(b[1] for b in boxes) / len(boxes))

    def _scan_list(self, p: dict) -> list[str]:
        """Fait défiler la liste jusqu'à ce qu'aucun nouveau nom n'apparaisse, puis remonte."""
        seen: list[str] = []
        point = self._list_point(p)
        scrolled = stale = 0
        for _ in range(80):
            new = [pl["name"] for pl in p.get("players", []) if pl["name"] not in seen]
            seen += new
            self.status["joueurs"] = len(seen)
            stale = 0 if new else stale + 1
            if stale >= 2 or point is None:
                break
            self.driver.scroll(point, -3)
            scrolled += 3
            self._pause(self.delay)
            p = self._read()
            if p.get("screen") != "effectif":
                break
        if scrolled and point:
            self.driver.scroll(point, scrolled + 3)
            self._pause(self.delay)
        return seen

    def _scan_profiles(self, names: list[str]) -> None:
        nxt, back = (self.keys.get("suivant") or "").strip(), (self.keys.get("retour") or "").strip()
        if not nxt and not back:
            self._log("Profils : aucun raccourci « joueur suivant » ni « retour » configuré. Renseignez-en un pour lire les attributs automatiquement.")
            return
        p = self._goto("effectif", 20)
        if not p or not self._list_point(p):
            self._log("Profils : liste de l'effectif introuvable, étape passée.")
            return
        if nxt:
            self._profiles_by_next(p, names, nxt, back)
        else:
            self._profiles_by_click(p, back)

    def _profiles_by_next(self, p: dict, names: list[str], nxt: str, back: str) -> None:
        first = next(pl for pl in p["players"] if pl.get("_box"))
        self.driver.click(first["_box"])
        self._pause(self.delay)
        q = self._wait_for(["profil"], 6)
        if not q:
            self._log("Profils : le clic sur un nom n'a pas ouvert de profil, étape passée.")
            return
        done: list[str] = []
        for _ in range(len(names) + 6):
            name = name_key((q.get("players") or [{}])[0].get("name"))
            if not name or name in done:
                break  # retour au premier joueur (ou touche sans effet) : tour complet
            done.append(name)
            self.status["profils"] = len(done)
            self.status["message"] = f"Profils : {len(done)} lu(s) sur {len(names)}…"
            self.driver.press(nxt)
            self._pause(self.delay)
            q = self._read()
            if q.get("screen") != "profil":
                break
        self._log(f"Profils : {len(done)} lu(s) avec la touche « joueur suivant ».")
        if len(done) <= 1 and len(names) > 1:
            self._log("La touche « joueur suivant » ne semble pas avoir d'effet : vérifiez le raccourci.")
        if back:
            self.driver.press(back)
            self._pause(self.delay)

    def _profiles_by_click(self, p: dict, back: str) -> None:
        done: set[str] = set()
        failed: set[str] = set()
        stale = 0
        for _ in range(400):
            target = next((pl for pl in p.get("players", []) if pl.get("_box") and pl["name"] not in done and pl["name"] not in failed), None)
            if target is None:
                point = self._list_point(p)
                if point is None or stale >= 2:
                    break
                before = {pl["name"] for pl in p.get("players", [])}
                self.driver.scroll(point, -3)
                self._pause(self.delay)
                p = self._read()
                if p.get("screen") != "effectif":
                    break
                stale = stale + 1 if {pl["name"] for pl in p.get("players", [])} <= before else 0
                continue
            stale = 0
            self.driver.click(target["_box"])
            self._pause(self.delay)
            q = self._wait_for(["profil"], 6)
            if not q:
                failed.add(target["name"])
                p = self._read()
                if p.get("screen") != "effectif":
                    self._log("Profils : écran inattendu après un clic, étape arrêtée.")
                    break
                continue
            done.add(target["name"])
            self.status["profils"] = len(done)
            self.status["message"] = f"Profils : {len(done)} lu(s)…"
            self.driver.press(back)
            self._pause(self.delay)
            p = self._wait_for(["effectif"], 6)
            if not p:
                self._log(f"Profils : le raccourci « retour » ({back}) ne ramène pas à l'effectif. Vérifiez-le.")
                break
        self._log(f"Profils : {len(done)} lu(s) en cliquant sur chaque nom." + (f" {len(failed)} non ouvert(s)." if failed else ""))


# ---------------------------------------------------------------- branchement sur le vrai jeu
class LiveReader:
    """Capture + lecture de la fenêtre de FM pour le scan automatique."""

    def __init__(self, watcher, db):
        self.watcher, self.db = watcher, db
        self._grabber = None
        self.origin = (0, 0)
        self.win = None

    def window(self):
        from . import window

        return window.find_window(self.db.settings().get("fenetre") or ["Football Manager"])

    def read(self) -> dict | None:
        from . import window

        win = self.window()
        if win is None or win.minimized or not win.foreground:
            raise LostFocus()
        if self._grabber is None:
            self._grabber = window.Grabber()
        frame = self._grabber.grab(win)
        if frame is None:
            return None
        x0, y0, _, _ = self.watcher.calib.crop_box(win.width, win.height)
        self.win, self.origin = win, (win.left + x0, win.top + y0)
        return self.watcher.process_image(frame, "auto")


class LiveDriver:
    def __init__(self, reader: LiveReader):
        self.reader = reader

    def _check(self):
        win = self.reader.window()
        if win is None or not win.foreground:
            raise LostFocus()
        return win

    def _screen_point(self, point):
        win = self._check()
        x, y = self.reader.origin[0] + point[0], self.reader.origin[1] + point[1]
        if not (win.left <= x < win.left + win.width and win.top <= y < win.top + win.height):
            raise RuntimeError("Clic hors de la fenêtre du jeu annulé.")
        return int(x), int(y)

    def prepare(self) -> None:
        """Met FM au premier plan (ou attend que l'utilisateur clique dessus)."""
        from . import inputs

        if not inputs.SUPPORTED:
            raise RuntimeError("Le scan automatique nécessite Windows.")
        win = self.reader.window()
        if win is None:
            raise RuntimeError("FM 27 non détecté : lancez le jeu et chargez votre partie.")
        inputs.focus(win.hwnd)
        for _ in range(16):
            time.sleep(0.5)
            w = self.reader.window()
            if w and w.foreground:
                time.sleep(0.6)
                return
        raise RuntimeError("Impossible de mettre FM au premier plan : cliquez dans la fenêtre du jeu juste après avoir lancé le scan.")

    def press(self, combo: str) -> None:
        from . import inputs

        self._check()
        inputs.press(combo)

    def click(self, point) -> None:
        from . import inputs

        inputs.click(*self._screen_point(point))

    def scroll(self, point, notches: int) -> None:
        from . import inputs

        inputs.scroll(*self._screen_point(point), notches)
