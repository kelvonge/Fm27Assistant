"""Lancement de FM Assistant 27 : serveur local + fenêtre desktop + compagnon de lecture."""
from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import webbrowser

from . import APP_NAME
from .capture import window

OVERLAY_TITLE = f"{APP_NAME} – Overlay"


def _free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


def _wait_ready(port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(prog="fm_assistant", description=APP_NAME)
    parser.add_argument("--demo", action="store_true", help="charge les données de démonstration au démarrage")
    parser.add_argument("--navigateur", action="store_true", help="ouvre l'interface dans le navigateur au lieu d'une fenêtre")
    parser.add_argument("--port", type=int, default=8727)
    parser.add_argument("--sans-capture", action="store_true", help="ne démarre pas la lecture en direct")
    parser.add_argument("--sans-fenetre", action="store_true", help="serveur seul (tests)")
    args = parser.parse_args()
    if sys.stdout is None or sys.stderr is None:
        # .exe sans console : la sortie standard n'existe pas, on écrit dans un journal
        from .config import data_dir

        sys.stdout = sys.stderr = open(data_dir() / "journal.log", "a", encoding="utf-8", buffering=1)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    window.set_dpi_aware()  # avant toute fenêtre, pour des coordonnées en pixels réels

    import uvicorn

    from .api import State, create_app
    from .demo import load_demo

    state = State()
    if args.demo:
        load_demo(state.db, state.kb)
    app = create_app(state)
    port = _free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None))
    thread = threading.Thread(target=server.run, name="fma-server", daemon=True)
    thread.start()
    if not _wait_ready(port):
        raise SystemExit("Le serveur local n'a pas démarré.")
    if not args.sans_capture:
        state.watcher.start()
    logging.getLogger("fma").info("%s prêt : %s", APP_NAME, url)

    def serve_forever():
        try:
            while thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    if args.sans_fenetre:
        serve_forever()
        return
    webview = None
    if not args.navigateur:
        try:
            import webview  # type: ignore
        except Exception as exc:
            logging.getLogger("fma").warning("pywebview indisponible (%s) : ouverture dans le navigateur.", exc)
    if webview is None:
        webbrowser.open(url)
        print(f"{APP_NAME} est ouvert dans votre navigateur : {url}\nFermez cette fenêtre (ou Ctrl+C) pour quitter.")
        serve_forever()
        return

    holder = {"overlay": None}

    def toggle_overlay() -> bool:
        if holder["overlay"] is not None:
            try:
                holder["overlay"].destroy()
            except Exception:
                pass
            holder["overlay"] = None
            return False
        ov = webview.create_window(OVERLAY_TITLE, f"{url}/overlay.html", width=400, height=250, x=30, y=90,
                                   frameless=True, on_top=True, easy_drag=True, resizable=True, min_size=(260, 140))
        ov.events.closed += lambda: holder.update(overlay=None)
        holder["overlay"] = ov
        threading.Timer(1.2, lambda: window.set_window_alpha(OVERLAY_TITLE, 228)).start()
        return True

    state.overlay_toggle = toggle_overlay
    state.overlay_open = lambda: holder["overlay"] is not None
    state.watcher.overlay_rect_provider = lambda: window.find_own_window_rect(OVERLAY_TITLE) if holder["overlay"] else None
    webview.create_window(APP_NAME, url, width=1440, height=900, min_size=(1100, 700), background_color="#0b0f14")
    webview.start()
    state.watcher.stop()
    server.should_exit = True


if __name__ == "__main__":
    main()
