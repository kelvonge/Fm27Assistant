"""API locale (FastAPI) : sert l'interface et expose données + analyses."""
from __future__ import annotations

import mimetypes
import random
import subprocess
import sys

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import APP_NAME, __version__, chat as chat_mod, config, demo
from .analysis import contracts as contracts_mod
from .analysis import dashboard as dashboard_mod
from .analysis import development, ratings, recruitment, squad, tactics
from .analysis.knowledge import KB, load_kb
from .capture.calibration import Calibration
from .capture.watcher import Watcher
from .db import Database
from .textutil import name_key, norm

# Windows associe parfois .js à text/plain dans le registre : les modules ES seraient refusés
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


class State:
    """État partagé de l'application."""

    def __init__(self, db: Database | None = None):
        config.ensure_user_files()
        self.db = db or Database()
        self.calib = Calibration()
        self.reload_knowledge()
        self.watcher = Watcher(self.db, lambda: (self.kb.raw, self.screens), self.calib)
        self.overlay_toggle = None  # défini par main.py quand la fenêtre desktop existe
        self.overlay_open = lambda: False

    def reload_knowledge(self) -> None:
        self.kb: KB = load_kb()
        self.screens, self.screens_warning = config.load_json("ecrans.json")
        self.ideas, self.ideas_warning = config.load_json("defis.json")

    # ---- contexte d'analyse recalculé à chaque requête (quelques millisecondes)
    def squad(self):
        return squad.enrich_all(self.db.players("effectif"), self.kb)

    def doc(self, kind: str):
        d = self.db.document(kind)
        return d["data"] if d else None


def create_app(state: State | None = None) -> FastAPI:
    st = state or State()
    app = FastAPI(title=APP_NAME, version=__version__, docs_url=None, redoc_url=None)
    app.state.fma = st

    # ------------------------------------------------------------ général
    @app.get("/api/status")
    def status():
        s = st.watcher.status_view()
        s["version"] = __version__
        s["demo"] = bool(st.db.get_meta("demo", False))
        s["overlay"] = {"disponible": st.overlay_toggle is not None, "ouvert": bool(st.overlay_open())}
        s["avertissements_fichiers"] = [w for w in (st.kb.warning, st.screens_warning, st.ideas_warning) if w]
        return s

    @app.get("/api/settings")
    def get_settings():
        return st.db.settings()

    @app.put("/api/settings")
    def put_settings(patch: dict = Body(...)):
        before = st.db.settings()
        s = st.db.update_settings(patch)
        if s.get("ocr") != before.get("ocr"):
            st.watcher.ocr = None
        return s

    @app.get("/api/knowledge")
    def knowledge():
        kb = st.kb
        return {
            "attributs": [{"id": a["id"], "nom": a["nom"], "categorie": a["categorie"]} for a in kb.attrs.values()],
            "roles": [{"id": r["id"], "nom": r["nom"], "postes": r["postes"], "description": r.get("description"),
                       "cles": [kb.attr_name(a) for a in r["cles"]], "secondaires": [kb.attr_name(a) for a in r["secondaires"]]}
                      for r in kb.roles.values()],
            "postes": [{"id": p, "label": l, "nom": kb.pos_names.get(p, p)} for p, l in kb.pos_labels.items()],
            "formations": [{"id": f["id"], "nom": f["nom"]} for f in kb.formations.values()],
            "tactiques": [{"id": t["id"], "nom": t["nom"], "style": t.get("style")} for t in kb.tactics],
            "dossier": str(config.data_dir()), "avertissement": kb.warning,
        }

    @app.post("/api/knowledge/reload")
    def knowledge_reload():
        st.reload_knowledge()
        return {"ok": True, "avertissements": [w for w in (st.kb.warning, st.screens_warning, st.ideas_warning) if w]}

    @app.post("/api/open-data-folder")
    def open_folder():
        path = str(config.data_dir())
        try:
            if sys.platform == "win32":
                import os
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass
        return {"dossier": path}

    @app.post("/api/demo/load")
    def demo_load():
        return demo.load_demo(st.db, st.kb)

    @app.post("/api/data/reset")
    def data_reset():
        st.db.reset()
        st.db.update_settings({"premier_lancement": False})
        return {"ok": True}

    # ------------------------------------------------------------ tableau de bord
    @app.get("/api/dashboard")
    def get_dashboard():
        enriched, ref = st.squad()
        check = tactics.check_tactic(st.doc("tactique"), enriched, st.kb)
        d = dashboard_mod.dashboard(enriched, ref, st.kb, st.db.settings(), st.db.game_date(), st.doc("finances"),
                                    st.doc("classement"), check, st.db.counts())
        d["historique_finances"] = [{"date": h["game_date"], **h["data"]} for h in st.db.document_history("finances")]
        d["prochain_match"] = tactics.prematch(st.doc("calendrier"), st.doc("classement"), [], enriched, st.kb,
                                               st.db.settings().get("club", ""), st.db.game_date()).get("match")
        return d

    # ------------------------------------------------------------ joueurs
    @app.get("/api/players")
    def players(scope: str = "effectif"):
        _, ref = st.squad()
        lst = [ratings.enrich(p, st.kb, ref) for p in st.db.players(scope)]
        for p in lst:
            p["n_attributs"] = len(p.get("attributes") or {})
            p.pop("attributes", None)
            p.pop("attr_source", None)
        return {"joueurs": lst, "reference": ref}

    @app.get("/api/players/{pid}")
    def player(pid: int):
        p = st.db.player(pid)
        if not p:
            raise HTTPException(404, "Joueur introuvable")
        _, ref = st.squad()
        out = ratings.enrich(p, st.kb, ref, full=True)
        out["historique"] = []
        for h in st.db.history(pid):
            sc = ratings.roles_for_player({**p, "attributes": h.get("attributes")}, st.kb)
            out["historique"].append({"date": h["game_date"], "note": sc[0]["note"] if sc and sc[0]["fiable"] else None,
                                      "value": h.get("value"), "form": h.get("form"), "attributes": h.get("attributes")})
        out["attributs_detail"] = [
            {"id": a["id"], "nom": a["nom"], "categorie": a["categorie"], "val": (p.get("attributes") or {}).get(a["id"]),
             "source": (p.get("attr_source") or {}).get(a["id"])} for a in st.kb.attrs.values()]
        out["reference"] = ref
        return out

    @app.patch("/api/players/{pid}")
    def patch_player(pid: int, patch: dict = Body(...)):
        p = st.db.patch_player(pid, patch)
        if not p:
            raise HTTPException(404, "Joueur introuvable")
        return p

    @app.delete("/api/players/{pid}")
    def delete_player(pid: int):
        st.db.delete_player(pid)
        return {"ok": True}

    @app.get("/api/compare")
    def compare(ids: str):
        _, ref = st.squad()
        out = []
        for raw in ids.split(",")[:4]:
            p = st.db.player(int(raw)) if raw.strip().isdigit() else None
            if p:
                e = ratings.enrich(p, st.kb, ref, full=True)
                out.append(e)
        return {"joueurs": out, "attributs": [{"id": a["id"], "nom": a["nom"], "categorie": a["categorie"]} for a in st.kb.attrs.values()]}

    @app.get("/api/squad/analysis")
    def squad_analysis():
        enriched, ref = st.squad()
        return {"reference": ref, "profondeur": squad.depth(enriched, st.kb, ref), "forces": squad.strengths(enriched, st.kb),
                "joueurs": len(enriched), "avec_attributs": sum(1 for p in enriched if p.get("attributes"))}

    # ------------------------------------------------------------ tactique
    @app.get("/api/tactics")
    def get_tactics(formation: str | None = None):
        enriched, ref = st.squad()
        settings = st.db.settings()
        tactic = st.doc("tactique")
        fid = formation or (tactic or {}).get("formation")
        if fid not in st.kb.formations:
            fid = "4-2-3-1" if "4-2-3-1" in st.kb.formations else next(iter(st.kb.formations))
        return {
            "formation": fid, "formations": list(st.kb.formations), "reference": ref,
            "xi": tactics.best_xi(enriched, st.kb.formations[fid], st.kb),
            "suggestions": tactics.suggest_tactics(enriched, st.kb, settings.get("style", "")),
            "coherence": tactics.check_tactic(tactic, enriched, st.kb),
            "avant_match": tactics.prematch(st.doc("calendrier"), st.doc("classement"), st.db.players("autre") + st.db.players("cible"),
                                            enriched, st.kb, settings.get("club", ""), st.db.game_date()),
        }

    # ------------------------------------------------------------ recrutement
    @app.get("/api/recruitment/needs")
    def recruitment_needs():
        enriched, ref = st.squad()
        pool = st.db.players("hors_effectif")
        return {"besoins": recruitment.needs(enriched, st.kb, ref, st.db.game_date()), "pepites": recruitment.gems(pool, st.kb, ref),
                "reference": ref, "joueurs_lus": len(pool)}

    @app.post("/api/recruitment/search")
    def recruitment_search(crit: dict = Body(default={})):
        _, ref = st.squad()
        return recruitment.search(st.db.players("hors_effectif"), crit, st.kb, ref)

    # ------------------------------------------------------------ jeunes, contrats
    @app.get("/api/youth")
    def youth():
        enriched, ref = st.squad()
        return development.youth_plan(enriched, st.kb, ref)

    @app.get("/api/contracts")
    def get_contracts():
        enriched, ref = st.squad()
        out = contracts_mod.contracts(enriched, st.kb, ref, st.db.game_date(), st.doc("finances"))
        out["date_jeu"] = st.db.game_date()
        out["staff"] = st.doc("staff")
        out["historique_finances"] = [{"date": h["game_date"], **h["data"]} for h in st.db.document_history("finances")]
        return out

    # ------------------------------------------------------------ idées de carrière
    @app.get("/api/ideas")
    def ideas(surprise: bool = False):
        lst = st.ideas.get("defis", [])
        if surprise and lst:
            return {"defi": random.choice(lst)}
        return {"defis": lst, "avertissement": st.ideas_warning}

    # ------------------------------------------------------------ recherche globale
    @app.get("/api/search")
    def search(q: str = ""):
        n = norm(q)
        if len(n) < 2:
            return {"resultats": []}
        out = []
        for p in st.db.players():
            if n in norm(p["name"]):
                out.append({"type": "joueur", "id": p["id"], "titre": p["name"],
                            "sous_titre": f"{p.get('positions') or 'poste inconnu'} · {p.get('club') or p['scope']}"})
        for r in st.kb.roles.values():
            if n in norm(r["nom"]) or n in norm(r.get("en", "")):
                out.append({"type": "role", "id": r["id"], "titre": r["nom"], "sous_titre": r.get("description", "")})
        for d in st.ideas.get("defis", []):
            if n in norm(d["titre"]) or n in norm(d.get("pitch", "")):
                out.append({"type": "defi", "id": d["id"], "titre": d["titre"], "sous_titre": d.get("pitch", "")})
        return {"resultats": out[:25]}

    # ------------------------------------------------------------ capture & calibrage
    def _last_view():
        frame, tokens, parsed = st.watcher.snapshot()
        return {
            "disponible": parsed is not None,
            "image": None if frame is None else {"w": int(frame.shape[1]), "h": int(frame.shape[0])},
            "tokens": [t.as_dict() for t in tokens], "lecture": parsed,
            "ecrans": [{"id": s["id"], "nom": s["nom"]} for s in st.screens.get("ecrans", [])],
            "champs": sorted(st.screens.get("colonnes", {}).keys()),
            "calibrage": st.calib.data,
        }

    @app.get("/api/capture/last")
    def capture_last():
        return _last_view()

    @app.get("/api/capture/last.png")
    def capture_png():
        frame, _, _ = st.watcher.snapshot()
        if frame is None:
            raise HTTPException(404, "Aucune capture")
        import cv2

        ok, buf = cv2.imencode(".png", frame)
        if not ok:
            raise HTTPException(500, "Encodage impossible")
        return Response(buf.tobytes(), media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.post("/api/capture/scan-now")
    def scan_now():
        st.watcher.scan_now()
        return {"ok": True}

    @app.post("/api/capture/upload")
    async def capture_upload(request: Request, ecran: str | None = None, enregistrer: bool = True):
        """Lit une capture d'écran fournie en fichier (PNG/JPG) : test sans le jeu, ou calibrage."""
        import cv2
        import numpy as np

        raw = await request.body()
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None
        if img is None:
            raise HTTPException(400, "Image illisible (formats acceptés : PNG, JPG)")
        try:
            st.watcher.process_image(img, "import", ecran or None, save=enregistrer)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))
        return _last_view()

    @app.post("/api/capture/reparse")
    def reparse(body: dict = Body(default={})):
        """Relit la dernière capture après une correction de calibrage."""
        frame, _, _ = st.watcher.snapshot()
        if frame is None:
            raise HTTPException(404, "Aucune capture à relire")
        st.watcher.process_image(frame, "calibrage", body.get("ecran") or None, save=bool(body.get("enregistrer", True)))
        return _last_view()

    @app.put("/api/calibration")
    def put_calibration(patch: dict = Body(...)):
        return st.calib.update(patch)

    @app.post("/api/calibration/correction")
    def correction(body: dict = Body(...)):
        kind = body.get("type")
        if kind == "titre":
            st.calib.add_title(body["ecran"], body["texte"])
        elif kind == "titre_suppr":
            st.calib.remove_title(body["ecran"], body["texte"])
        elif kind == "colonne":
            st.calib.set_column(body["texte"], body.get("champ") or None)
        elif kind == "texte":
            st.calib.add_replacement(body["lu"], body.get("correct", ""))
            # La fiche créée sous le nom mal lu est renommée (ou supprimée si la bonne existe déjà)
            wrong, right = body["lu"], body.get("correct", "")
            if right and name_key(wrong) != name_key(right):
                bad = next((p for p in st.db.players() if name_key(p["name"]) == name_key(wrong)), None)
                good = next((p for p in st.db.players() if name_key(p["name"]) == name_key(right)), None)
                if bad and good:
                    st.db.delete_player(bad["id"])
                elif bad:
                    st.db.patch_player(bad["id"], {"name": right})
        else:
            raise HTTPException(400, "Type de correction inconnu")
        return st.calib.data

    @app.post("/api/scans/{scan_id}/reassign")
    def reassign(scan_id: int, body: dict = Body(...)):
        scope = body.get("scope")
        if scope not in ("effectif", "cible", "autre"):
            raise HTTPException(400, "Groupe inconnu")
        return {"modifies": st.db.reassign_scan(scan_id, scope)}

    @app.get("/api/scans")
    def scans():
        return {"lectures": st.db.scans(40)}

    @app.get("/api/scan-guide")
    def scan_guide():
        seen: dict[str, int] = {}
        for s in st.db.scans(400, st.watcher.guide_start_scan):
            if s["source"] != "demo" and "rien de lisible" not in (s["summary"] or ""):
                seen[s["screen"]] = seen.get(s["screen"], 0) + 1
        seen["recherche"] = seen.get("recherche", 0) + seen.get("shortlist", 0)
        steps = []
        for g in st.screens.get("guide_scan", []):
            n, need = seen.get(g["ecran"], 0), g.get("minimum", 1)
            steps.append({**g, "lus": n, "fait": n >= need})
        req = [s for s in steps if not s.get("facultatif")]
        return {"etapes": steps, "termine": all(s["fait"] for s in req), "progression": sum(s["fait"] for s in req) / max(1, len(req))}

    @app.post("/api/scan-guide/start")
    def scan_guide_start():
        st.watcher.guide_start_scan = st.db.last_scan_id()
        st.db.update_settings({"premier_lancement": False})
        return {"ok": True}

    # ------------------------------------------------------------ overlay
    @app.get("/api/overlay")
    def overlay():
        s = st.watcher.status_view()
        enriched, ref = st.squad()
        tips = []
        last = st.watcher.snapshot()[2] or {}
        screen = last.get("screen")
        if screen == "profil" and last.get("players"):
            p = st.db.find_player(last["players"][0].get("name", ""))
            if p:
                e = ratings.enrich(p, st.kb, ref, full=True)
                if e["analyse"].get("explication"):
                    tips.append(e["analyse"]["explication"])
                for r in (e["analyse"].get("roles") or [])[1:3]:
                    tips.append(f"Alternative : {r['nom']} ({r['note']:.1f}/20)")
        elif screen == "tactique":
            check = tactics.check_tactic(st.doc("tactique"), enriched, st.kb)
            tips += [f"⚠ {a['message']} {a['conseil'] or ''}" for a in check["alertes"]]
            tips += [r["message"] for r in check["roles"] if r.get("statut") == "mieux"][:3]
            if not tips:
                tips.append("Tactique cohérente avec votre effectif : rien à signaler.")
        elif screen in ("recherche", "shortlist"):
            res = recruitment.search(st.db.players("hors_effectif"), {}, st.kb, ref)["resultats"]
            good = [r for r in res if r["note"] is not None and ref is not None and r["note"] >= ref - 0.5][:3]
            tips += [f"{r['name']} ({r['age'] or '?'} ans) : {r['role_nom'] or 'niveau estimé'} {r['note']:.1f}/20" for r in good]
            if not tips:
                tips.append("Aucun joueur lu au niveau de votre onze type pour l'instant. Ouvrez les profils pour affiner.")
        if not tips:
            check = tactics.check_tactic(st.doc("tactique"), enriched, st.kb)
            d = dashboard_mod.dashboard(enriched, ref, st.kb, st.db.settings(), st.db.game_date(), st.doc("finances"),
                                        st.doc("classement"), check, s["compteurs"])
            tips = [a["texte"] for a in d["alertes"][:4]] or ["Aucune alerte. Continuez à jouer, je lis les écrans au passage."]
        return {"statut": s["message"], "etat": s["etat"], "ecran": last.get("screen_name"), "conseils": tips[:5],
                "accent": st.db.settings().get("accent")}

    @app.post("/api/overlay/toggle")
    def overlay_toggle():
        if st.overlay_toggle is None:
            raise HTTPException(409, "L'overlay n'est disponible que dans la fenêtre desktop (pas dans le navigateur).")
        return {"ouvert": bool(st.overlay_toggle())}

    # ------------------------------------------------------------ chat (Ollama)
    @app.get("/api/chat/status")
    def chat_status():
        return chat_mod.status()

    @app.post("/api/chat")
    def chat(body: dict = Body(...)):
        info = chat_mod.status()
        if not info["disponible"]:
            raise HTTPException(503, "Ollama n'est pas disponible sur ce PC.")
        settings = st.db.settings()
        model = body.get("modele") or settings.get("modele_chat") or info["modeles"][0]
        if model not in info["modeles"]:
            model = info["modeles"][0]
        enriched, ref = st.squad()
        check = tactics.check_tactic(st.doc("tactique"), enriched, st.kb)
        d = dashboard_mod.dashboard(enriched, ref, st.kb, settings, st.db.game_date(), st.doc("finances"),
                                    st.doc("classement"), check, st.db.counts())
        ctx = chat_mod.build_context(enriched, settings, st.db.game_date(), st.doc("finances"), st.doc("tactique"),
                                     d["classement"], d["alertes"])
        try:
            answer = chat_mod.chat(model, ctx, body.get("messages") or [])
        except Exception as exc:
            raise HTTPException(502, f"Le modèle local n'a pas répondu : {exc}")
        return {"reponse": answer or "Le modèle n'a rien répondu.", "modele": model}

    # ------------------------------------------------------------ interface
    web = config.web_dir()

    @app.get("/")
    def index():
        return FileResponse(web / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=str(web), html=True), name="web")
    return app
