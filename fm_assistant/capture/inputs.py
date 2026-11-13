"""Envoi de touches et de clics à la fenêtre de FM (scan automatique uniquement).

Rien n'est envoyé si FM n'est pas au premier plan, et les clics sont limités
à l'intérieur de sa fenêtre. Windows uniquement.
"""
from __future__ import annotations

import sys
import time

SUPPORTED = sys.platform == "win32"

VK = {
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "maj": 0x10, "entree": 0x0D, "enter": 0x0D, "echap": 0x1B, "esc": 0x1B,
    "espace": 0x20, "space": 0x20, "tab": 0x09, "retour_arriere": 0x08, "backspace": 0x08,
    "gauche": 0x25, "left": 0x25, "haut": 0x26, "up": 0x26, "droite": 0x27, "right": 0x27, "bas": 0x28, "down": 0x28,
    "pageprec": 0x21, "pageup": 0x21, "pagesuiv": 0x22, "pagedown": 0x22, "fin": 0x23, "end": 0x23, "debut": 0x24, "home": 0x24,
    ",": 0xBC, ".": 0xBE, "-": 0xBD, "+": 0xBB, ";": 0xBA, "/": 0xBF,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 13)})
MOUSE_KEYS = {"souris_precedent": 1, "souris_suivant": 2}  # boutons latéraux de la souris
_EXTENDED = {0x25, 0x26, 0x27, 0x28, 0x21, 0x22, 0x23, 0x24}


def parse_combo(combo: str) -> list[str]:
    """« ctrl+maj+p » → ['ctrl', 'maj', 'p']. Lève ValueError si une touche est inconnue."""
    raw = (combo or "").strip().lower().replace(" ", "")
    if not raw:
        raise ValueError("raccourci vide")
    parts = ["+"] if raw == "+" else [p for p in raw.replace("++", "+plus").split("+") if p]
    parts = ["+" if p == "plus" else p for p in parts]
    for p in parts:
        if p not in VK and p not in MOUSE_KEYS and not (len(p) == 1 and p.isalnum()):
            raise ValueError(f"touche inconnue : « {p} »")
    return parts


def _vk(key: str) -> int:
    return VK[key] if key in VK else ord(key.upper())


def press(combo: str) -> None:
    """Appuie sur un raccourci clavier (ou un bouton latéral de la souris)."""
    import ctypes

    user32 = ctypes.windll.user32
    keys = parse_combo(combo)
    if len(keys) == 1 and keys[0] in MOUSE_KEYS:
        user32.mouse_event(0x0080, 0, 0, MOUSE_KEYS[keys[0]], 0)  # XDOWN
        time.sleep(0.03)
        user32.mouse_event(0x0100, 0, 0, MOUSE_KEYS[keys[0]], 0)  # XUP
        return
    codes = [_vk(k) for k in keys]
    for vk in codes:
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), 0x0001 if vk in _EXTENDED else 0, 0)
        time.sleep(0.02)
    time.sleep(0.04)
    for vk in reversed(codes):
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), (0x0001 if vk in _EXTENDED else 0) | 0x0002, 0)
        time.sleep(0.02)


def click(x: int, y: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.06)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def scroll(x: int, y: int, notches: int) -> None:
    """Molette au point donné. notches < 0 : vers le bas."""
    import ctypes

    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    step = 1 if notches > 0 else -1
    for _ in range(abs(notches)):
        user32.mouse_event(0x0800, 0, 0, ctypes.c_ulong(120 * step & 0xFFFFFFFF).value, 0)
        time.sleep(0.03)


def focus(hwnd: int) -> None:
    """Met la fenêtre au premier plan."""
    import ctypes

    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
