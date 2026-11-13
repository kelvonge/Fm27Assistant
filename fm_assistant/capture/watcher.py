"""Compagnon d'arrière-plan : surveille la fenêtre de FM et lit chaque nouvel écran."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import numpy as np

from ..db import Database
from . import window
from .calibration import Calibration
from .ingest import ingest
from .ocr import Ocr
from .parsers import Knowledge4Parse, parse_frame

log = logging.getLogger("fma.watcher")


class Watcher:
    def __init__(self, db: Database, kb_provider, calib: Calibration):
        self.db = db
        self.kb_provider = kb_provider  # () -> (connaissances, écrans)
        self.calib = calib
        self.ocr: Ocr | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._force = threading.Event()
        self._lock = threading.Lock()
        self.overlay_rect_provider = None  # () -> (l, t, r, b) | None
        self.last_frame: np.ndarray | None = None
        self.last_tokens: list = []
        self.last_parsed: dict | None = None
        self.guide_start_scan = 0
        self.suspended = False  # vrai pendant un scan automatique (il fait ses propres captures)
        self.status = {
            "plateforme_ok": window.SUPPORTED, "etat": "arret", "fm_detecte": False, "fenetre": None,
            "resolution": None, "ocr": None, "ocr_erreurs": [], "dernier_ecran": None, "dernier_resume": None,
            "derniere_lecture": None, "avertissements": [], "erreur": None, "lectures": 0,
        }

    # ------------------------------------------------------------ cycle de vie
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="fma-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def scan_now(self) -> None:
        self._force.set()

    def ensure_ocr(self) -> Ocr:
        if self.ocr is None:
            self.ocr = Ocr(self.db.settings().get("ocr", "auto"))
            self.status["ocr"] = self.ocr.name
            self.status["ocr_erreurs"] = self.ocr.errors if not self.ocr.available else []
        return self.ocr

    # ------------------------------------------------------------ traitement d'une image
    def process_image(self, img: np.ndarray, source: str = "capture", force_screen: str | None = None,
                      save: bool = True) -> dict:
        """OCR + reconnaissance + enregistrement. Utilisé par la capture et par l'import d'image."""
        ocr = self.ensure_ocr()
        if not ocr.available:
            raise RuntimeError("Aucun moteur OCR disponible : " + " ; ".join(ocr.errors))
        h, w = img.shape[:2]
        x0, y0, x1, y1 = self.calib.crop_box(w, h)
        work = img[y0:y1, x0:x1]
        tokens = ocr.read(work, float(self.calib.data.get("echelle_ocr") or 0))
        kb, cfg = self.kb_provider()
        parsed = parse_frame(tokens, work, work.shape[1], work.shape[0], Knowledge4Parse(kb, cfg), self.calib,
                             self.db.settings(), self.db.game_date(), force_screen)
        result = ingest(self.db, parsed, source) if save else {"scan_id": None, "resume": "Aperçu (non enregistré)"}
        with self._lock:
            self.last_frame, self.last_tokens, self.last_parsed = work, tokens, {**parsed, **result}
        st = self.status
        st["lectures"] += 1
        st["dernier_ecran"] = parsed["screen_name"] if parsed["screen"] else None
        st["dernier_resume"] = result["resume"]
        st["derniere_lecture"] = datetime.now().isoformat(timespec="seconds")
        st["avertissements"] = parsed["warnings"]
        st["resolution"] = [w, h]
        return {**parsed, **result}

    def snapshot(self):
        with self._lock:
            return self.last_frame, list(self.last_tokens), self.last_parsed

    # ------------------------------------------------------------ boucle
    def _mask_overlay(self, img: np.ndarray, win) -> np.ndarray:
        if not self.overlay_rect_provider:
            return img
        rect = self.overlay_rect_provider()
        if not rect:
            return img
        l, t, r, b = rect
        x0, y0 = max(0, l - win.left), max(0, t - win.top)
        x1, y1 = min(win.width, r - win.left), min(win.height, b - win.top)
        if x1 > x0 and y1 > y0:
            img = img.copy()
            img[y0:y1, x0:x1] = 0  # l'overlay ne doit pas être lu comme faisant partie du jeu
        return img

    def _run(self) -> None:
        st = self.status
        if not window.SUPPORTED:
            st["etat"] = "indisponible"
            st["erreur"] = "La lecture en direct nécessite Windows. Le mode démonstration et l'import de captures restent utilisables."
            return
        try:
            grabber = window.Grabber()
        except Exception as exc:
            st["etat"] = "indisponible"
            st["erreur"] = f"Capture d'écran impossible (module mss) : {exc}"
            return
        last_sig = processed_sig = None
        stable = 0
        while not self._stop.is_set():
            settings = self.db.settings()
            interval = max(0.3, float(settings.get("intervalle") or 1.0))
            try:
                if self.suspended:
                    time.sleep(0.5)
                    continue
                if not settings.get("capture_active", True) and not self._force.is_set():
                    st["etat"] = "pause"
                    time.sleep(0.8)
                    continue
                win = window.find_window(settings.get("fenetre") or ["Football Manager"])
                if win is None:
                    st.update(etat="absent", fm_detecte=False, fenetre=None)
                    last_sig = processed_sig = None
                    time.sleep(2.0)
                    continue
                st.update(fm_detecte=True, fenetre=win.title)
                if win.minimized or not win.foreground:
                    st["etat"] = "arriere_plan"
                    time.sleep(1.0)
                    continue
                frame = grabber.grab(win)
                if frame is None:
                    time.sleep(1.0)
                    continue
                frame = self._mask_overlay(frame, win)
                sig = window.signature(frame)
                moving = window.changed_fraction(sig, last_sig) > 0.002
                last_sig = sig
                stable = 0 if moving else stable + 1
                forced = self._force.is_set()
                is_new = window.changed_fraction(sig, processed_sig) > 0.004
                st["etat"] = "actif"
                if forced or (is_new and stable >= 1):
                    self._force.clear()
                    processed_sig = sig
                    st["erreur"] = None
                    self.process_image(frame, "capture")
            except Exception as exc:  # une lecture ratée ne doit jamais arrêter le compagnon
                log.exception("Lecture échouée")
                st["erreur"] = f"Lecture échouée : {exc}"
                time.sleep(1.5)
            time.sleep(interval)
        grabber.close()
        st["etat"] = "arret"

    # ------------------------------------------------------------ statut lisible
    def status_view(self) -> dict:
        st = dict(self.status)
        counts = self.db.counts()
        etat = st["etat"]
        if etat == "indisponible":
            msg = st["erreur"] or "Lecture en direct indisponible"
            if st["dernier_resume"]:
                msg = f"Dernière capture importée : {st['dernier_resume']} – (lecture en direct indisponible sur ce système)"
        elif etat == "absent":
            msg = "FM 27 non détecté – lancez le jeu, la lecture démarrera toute seule"
        elif etat == "pause":
            msg = "Lecture en pause"
        elif etat == "arret":
            msg = "Compagnon arrêté"
        else:
            msg = "FM 27 détecté ✓"
            if etat == "arriere_plan":
                msg += " – jeu en arrière-plan, lecture suspendue"
            if st["dernier_resume"]:
                msg += f" – dernier écran lu : {st['dernier_resume']}"
            elif etat == "actif":
                msg += " – en attente d'un écran lisible"
        st["message"] = msg
        st["compteurs"] = counts
        st["date_jeu"] = self.db.game_date()
        return st
