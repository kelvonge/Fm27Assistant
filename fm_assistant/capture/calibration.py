"""Calibrage : réglages propres à votre installation et corrections apprises.

Tout est stocké dans calibrage.json (dossier de données). Chaque correction
faite dans l'interface améliore les lectures suivantes :
- « titres »        : mots qui identifient un écran chez vous (skin, langue) ;
- « colonnes »      : en-tête de tableau → champ ;
- « remplacements » : texte mal lu → texte correct.
"""
from __future__ import annotations

import json
import threading

from .. import config
from ..textutil import norm

DEFAULT = {
    "echelle_ocr": 0,  # 0 = automatique
    "marges": {"haut": 0.0, "bas": 0.0, "gauche": 0.0, "droite": 0.0},  # part de l'image ignorée
    "titres": {},
    "colonnes": {},
    "remplacements": {},
    "resolution": None,
    "valide": False,
}


class Calibration:
    def __init__(self):
        self._lock = threading.Lock()
        self.path = config.data_dir() / "calibrage.json"
        self.data = json.loads(json.dumps(DEFAULT))
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass  # fichier abîmé : on repart des valeurs par défaut

    def save(self) -> None:
        with self._lock:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def update(self, patch: dict) -> dict:
        for k in ("echelle_ocr", "resolution", "valide"):
            if k in patch:
                self.data[k] = patch[k]
        if isinstance(patch.get("marges"), dict):
            for k in ("haut", "bas", "gauche", "droite"):
                if k in patch["marges"]:
                    self.data["marges"][k] = max(0.0, min(0.4, float(patch["marges"][k] or 0)))
        self.save()
        return self.data

    # ---- corrections
    def add_title(self, screen: str, phrase: str) -> None:
        p = norm(phrase)
        if not p:
            return
        for lst in self.data["titres"].values():  # un repère n'identifie qu'un seul écran
            if p in lst:
                lst.remove(p)
        self.data["titres"].setdefault(screen, []).append(p)
        self.save()

    def remove_title(self, screen: str, phrase: str) -> None:
        lst = self.data["titres"].get(screen, [])
        if norm(phrase) in lst:
            lst.remove(norm(phrase))
            self.save()

    def set_column(self, header: str, field: str | None) -> None:
        h = norm(header)
        if not h:
            return
        if field:
            self.data["colonnes"][h] = field
        else:
            self.data["colonnes"].pop(h, None)
        self.save()

    def add_replacement(self, wrong: str, right: str) -> None:
        w = norm(wrong)
        if not w or wrong == right:
            return
        if right:
            self.data["remplacements"][w] = right
        else:
            self.data["remplacements"].pop(w, None)
        self.save()

    def fix(self, text: str) -> str:
        """Applique les corrections de texte apprises."""
        rep = self.data["remplacements"]
        if not rep:
            return text
        return rep.get(norm(text), text)

    def crop_box(self, w: int, h: int) -> tuple[int, int, int, int]:
        m = self.data["marges"]
        return (int(w * m["gauche"]), int(h * m["haut"]), int(w * (1 - m["droite"])), int(h * (1 - m["bas"])))
