"""Chemins, fichiers éditables et réglages par défaut."""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path

log = logging.getLogger("fma.config")

DEFAULT_SETTINGS = {
    "club": "",
    "division": "",
    "saison": "",
    "style": "",
    "objectif": "",
    "accent": "#2fd08c",
    "periode_salaire": "semaine",  # période supposée quand le jeu n'affiche pas p/s, p/m ou p/a
    "fenetre": ["Football Manager"],  # morceaux de titre de fenêtre à chercher
    "intervalle": 1.0,  # secondes entre deux captures
    "ocr": "auto",  # auto | rapidocr | windows
    "capture_active": True,
    "premier_lancement": True,
    "modele_chat": "",
}


def resource_dir() -> Path:
    """Dossier des ressources embarquées (compatible PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "fm_assistant"
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Dossier utilisateur : base SQLite, calibrage, fichiers éditables."""
    override = os.environ.get("FMA_DATA_DIR")
    if override:
        d = Path(override)
    elif sys.platform == "win32":
        d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FMAssistant27"
    else:
        d = Path.home() / ".fm_assistant27"
    d.mkdir(parents=True, exist_ok=True)
    return d


def web_dir() -> Path:
    return resource_dir() / "web"


EDITABLE = ("connaissances.json", "ecrans.json", "defis.json")


def ensure_user_files() -> None:
    """Copie les JSON éditables dans le dossier utilisateur au premier lancement."""
    for name in EDITABLE:
        dst = data_dir() / name
        if not dst.exists():
            try:
                shutil.copyfile(resource_dir() / "data" / name, dst)
            except OSError as exc:  # pas bloquant : on lira la version embarquée
                log.warning("Copie de %s impossible : %s", name, exc)


def load_json(name: str) -> tuple[dict, str | None]:
    """Charge un JSON éditable. Retourne (données, avertissement éventuel).

    Si la copie utilisateur est illisible (faute de frappe…), on retombe sur la
    version embarquée et on le signale au lieu de planter.
    """
    user = data_dir() / name
    bundled = resource_dir() / "data" / name
    warning = None
    if user.exists():
        try:
            return json.loads(user.read_text(encoding="utf-8")), None
        except (OSError, ValueError) as exc:
            warning = f"{name} est illisible ({exc}). La version d'origine est utilisée."
            log.warning(warning)
    return json.loads(bundled.read_text(encoding="utf-8")), warning
