"""Détection de la fenêtre de FM et capture d'écran (lecture seule).

Rien n'est injecté dans le jeu : on photographie simplement la zone de
l'écran occupée par sa fenêtre, comme le ferait un logiciel de capture.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np

SUPPORTED = sys.platform == "win32"
OWN_TITLES = ("FM Assistant",)


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int
    foreground: bool
    minimized: bool


def set_dpi_aware() -> None:
    """Coordonnées en pixels réels même avec la mise à l'échelle de Windows (125 %, 150 %…)."""
    if not SUPPORTED:
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _is_ours(hwnd: int, title: str) -> bool:
    return any(t.lower() in title.lower() for t in OWN_TITLES)


def find_window(keywords: list[str]) -> WindowInfo | None:
    """Cherche une fenêtre visible dont le titre contient l'un des mots-clés."""
    if not SUPPORTED:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []
    keys = [k.lower() for k in keywords if k]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        if any(k in title.lower() for k in keys) and not _is_ours(hwnd, title):
            found.append((hwnd, title))
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return None
    fg = user32.GetForegroundWindow()
    hwnd, title = next(((h, t) for h, t in found if h == fg), found[0])
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    fg_title = ""
    if fg:
        n = user32.GetWindowTextLengthW(fg)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(fg, buf, n + 1)
        fg_title = buf.value
    # L'overlay de l'assistant posé sur le jeu ne doit pas mettre la lecture en pause
    foreground = fg == hwnd or "overlay" in fg_title.lower() and _is_ours(fg, fg_title)
    return WindowInfo(hwnd, title, pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top,
                      bool(foreground), bool(user32.IsIconic(hwnd)))


def find_own_window_rect(title_part: str) -> tuple[int, int, int, int] | None:
    """Rectangle écran (gauche, haut, droite, bas) d'une de nos fenêtres (overlay)."""
    if not SUPPORTED:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title_part)
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return None
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def set_window_alpha(title: str, alpha: int = 225) -> bool:
    """Rend une de nos fenêtres translucide (overlay)."""
    if not SUPPORTED:
        return False
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x80000, 0x2
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
    return bool(user32.SetLayeredWindowAttributes(hwnd, 0, max(60, min(255, alpha)), LWA_ALPHA))


class Grabber:
    """Capture mss. À créer dans le fil qui l'utilise."""

    def __init__(self):
        import mss  # type: ignore

        self._sct = mss.mss()

    def grab(self, win: WindowInfo) -> np.ndarray | None:
        if win.width < 200 or win.height < 200:
            return None
        shot = self._sct.grab({"left": win.left, "top": win.top, "width": win.width, "height": win.height})
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3])  # BGRA → BGR

    def close(self) -> None:
        try:
            self._sct.close()
        except Exception:
            pass


def signature(img: np.ndarray) -> np.ndarray:
    """Empreinte compacte de l'image (niveaux de gris 192×108) pour détecter les changements."""
    import cv2

    small = cv2.resize(img, (192, 108), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)


def changed_fraction(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Part des pixels de l'empreinte qui ont nettement changé (0 → identique)."""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    return float((np.abs(a - b) > 22).mean())
