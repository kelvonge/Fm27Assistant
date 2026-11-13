"""Base locale SQLite : joueurs fusionnés sans doublons + historique par date de jeu."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import config
from .textutil import name_key, names_compatible, norm

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, name_key TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'cible',      -- effectif | cible | autre
    shortlist INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}',
    game_date TEXT, created_scan INTEGER, updated_scan INTEGER, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_players_key ON players(name_key);
CREATE TABLE IF NOT EXISTS player_history (
    player_id INTEGER NOT NULL, game_date TEXT NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (player_id, game_date)
);
CREATE TABLE IF NOT EXISTS documents (
    kind TEXT NOT NULL, game_date TEXT NOT NULL DEFAULT '', data TEXT NOT NULL, updated_at TEXT,
    PRIMARY KEY (kind, game_date)
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, screen TEXT, game_date TEXT, summary TEXT, source TEXT
);
"""

# Champs suivis dans l'historique (graphiques d'évolution)
HISTORY_FIELDS = ("attributes", "value", "wage", "form", "ability_stars", "potential_stars", "age", "morale", "condition")
SCOPES = ("effectif", "cible", "autre")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str | None = None):
        self.path = str(path or (config.data_dir() / "carriere.sqlite"))
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------ méta
    def get_meta(self, key: str, default=None):
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except ValueError:
            return default

    def set_meta(self, key: str, value) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            self._conn.commit()

    def settings(self) -> dict:
        s = dict(config.DEFAULT_SETTINGS)
        s.update(self.get_meta("settings", {}) or {})
        return s

    def update_settings(self, patch: dict) -> dict:
        s = self.settings()
        s.update({k: v for k, v in patch.items() if k in config.DEFAULT_SETTINGS})
        self.set_meta("settings", s)
        return s

    def game_date(self) -> str | None:
        return self.get_meta("game_date")

    # ------------------------------------------------------------ joueurs
    @staticmethod
    def _row_to_player(row) -> dict:
        p = json.loads(row["data"])
        p.update(
            id=row["id"], name=row["name"], scope=row["scope"], shortlist=bool(row["shortlist"]),
            game_date=row["game_date"], updated_at=row["updated_at"],
        )
        return p

    def players(self, scope: str | None = None) -> list[dict]:
        q = "SELECT * FROM players"
        args: tuple = ()
        if scope == "shortlist":
            q += " WHERE shortlist=1"
        elif scope == "hors_effectif":
            q += " WHERE scope!='effectif'"
        elif scope:
            q += " WHERE scope=?"
            args = (scope,)
        with self._lock:
            rows = self._conn.execute(q + " ORDER BY name", args).fetchall()
        return [self._row_to_player(r) for r in rows]

    def player(self, pid: int) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
        return self._row_to_player(row) if row else None

    def find_player(self, name: str, age: int | None = None, club: str | None = None) -> dict | None:
        """Retrouve un joueur déjà connu : nom exact, sinon initiale + nom de famille."""
        key = name_key(name)
        if not key:
            return None
        with self._lock:
            rows = self._conn.execute("SELECT * FROM players WHERE name_key=?", (key,)).fetchall()
            if not rows:
                last = key.split()[-1]
                rows = [
                    r for r in self._conn.execute("SELECT * FROM players WHERE name_key LIKE ?", (f"%{last}",)).fetchall()
                    if names_compatible(r["name_key"], key)
                ]
        best = None
        for r in rows:
            p = self._row_to_player(r)
            if age is not None and p.get("age") is not None and abs(p["age"] - age) > 1:
                continue  # homonyme d'un autre âge : joueur différent
            if club and p.get("club") and norm(club) == norm(p["club"]):
                return p
            best = best or p
        return best

    def upsert_player(self, rec: dict, scope: str | None, scan_id: int | None, game_date: str | None) -> tuple[int, bool]:
        """Fusionne une lecture dans la fiche du joueur. Retourne (id, créé ?).

        Règles : une valeur lue remplace l'ancienne, une valeur absente ne
        supprime rien, les attributs sont fusionnés un par un.
        """
        name = (rec.get("name") or "").strip()
        if not name_key(name):
            raise ValueError("nom illisible")
        existing = self.find_player(name, rec.get("age"), rec.get("club"))
        data = {} if existing is None else {
            k: v for k, v in existing.items() if k not in ("id", "name", "scope", "shortlist", "game_date", "updated_at")
        }
        for k, v in rec.items():
            if k in ("name", "scope", "shortlist") or v is None or v == "" or v == []:
                continue
            if k in ("attributes", "attr_source") and isinstance(v, dict):
                merged = dict(data.get(k) or {})
                merged.update(v)
                data[k] = merged
            else:
                data[k] = v
        shortlist = bool(rec.get("shortlist"))
        with self._lock:
            if existing is None:
                cur = self._conn.execute(
                    "INSERT INTO players(name,name_key,scope,shortlist,data,game_date,created_scan,updated_scan,updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?)",
                    (name, name_key(name), scope or "cible", int(shortlist), json.dumps(data, ensure_ascii=False),
                     game_date, scan_id, scan_id, _now()),
                )
                pid, created = cur.lastrowid, True
            else:
                pid, created = existing["id"], False
                # On garde le nom le plus complet (« Kylian Mbappé » plutôt que « K. Mbappé »)
                best_name = name if len(name_key(name)) > len(name_key(existing["name"])) else existing["name"]
                new_scope = existing["scope"]
                if scope == "effectif" or (scope and existing["scope"] != "effectif"):
                    new_scope = scope
                self._conn.execute(
                    "UPDATE players SET name=?,name_key=?,scope=?,shortlist=?,data=?,game_date=?,updated_scan=?,updated_at=? WHERE id=?",
                    (best_name, name_key(best_name), new_scope, int(shortlist or existing["shortlist"]),
                     json.dumps(data, ensure_ascii=False), game_date or existing.get("game_date"), scan_id, _now(), pid),
                )
            hist = {k: data[k] for k in HISTORY_FIELDS if data.get(k) not in (None, {}, "")}
            if hist:
                self._conn.execute(
                    "INSERT INTO player_history(player_id,game_date,data) VALUES(?,?,?)"
                    " ON CONFLICT(player_id,game_date) DO UPDATE SET data=excluded.data",
                    (pid, game_date or "", json.dumps(hist, ensure_ascii=False)),
                )
            self._conn.commit()
        return pid, created

    def patch_player(self, pid: int, patch: dict) -> dict | None:
        p = self.player(pid)
        if not p:
            return None
        cols, args = [], []
        if patch.get("scope") in SCOPES:
            cols.append("scope=?"); args.append(patch["scope"])
        if "shortlist" in patch:
            cols.append("shortlist=?"); args.append(int(bool(patch["shortlist"])))
        if patch.get("name"):
            cols += ["name=?", "name_key=?"]; args += [patch["name"], name_key(patch["name"])]
        data = {k: v for k, v in p.items() if k not in ("id", "name", "scope", "shortlist", "game_date", "updated_at")}
        for k, v in (patch.get("data") or {}).items():
            if k == "attributes" and isinstance(v, dict):
                attrs = dict(data.get("attributes") or {})
                for a, val in v.items():
                    if val is None:
                        attrs.pop(a, None)
                    else:
                        attrs[a] = val
                data["attributes"] = attrs
            elif v is None:
                data.pop(k, None)
            else:
                data[k] = v
        cols += ["data=?", "updated_at=?"]; args += [json.dumps(data, ensure_ascii=False), _now()]
        with self._lock:
            self._conn.execute(f"UPDATE players SET {','.join(cols)} WHERE id=?", (*args, pid))
            self._conn.commit()
        return self.player(pid)

    def delete_player(self, pid: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM players WHERE id=?", (pid,))
            self._conn.execute("DELETE FROM player_history WHERE player_id=?", (pid,))
            self._conn.commit()

    def history(self, pid: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT game_date,data FROM player_history WHERE player_id=? ORDER BY game_date", (pid,)
            ).fetchall()
        return [{"game_date": r["game_date"] or None, **json.loads(r["data"])} for r in rows]

    def reassign_scan(self, scan_id: int, scope: str) -> int:
        """Corrige une lecture attribuée au mauvais groupe (ex. effectif adverse)."""
        with self._lock:
            cur = self._conn.execute("UPDATE players SET scope=? WHERE created_scan=?", (scope, scan_id))
            self._conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------ documents
    def save_document(self, kind: str, data, game_date: str | None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents(kind,game_date,data,updated_at) VALUES(?,?,?,?)"
                " ON CONFLICT(kind,game_date) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (kind, game_date or "", json.dumps(data, ensure_ascii=False), _now()),
            )
            self._conn.commit()

    def document(self, kind: str, game_date: str | None = None):
        q = "SELECT data,game_date,updated_at FROM documents WHERE kind=?"
        args: list = [kind]
        if game_date is not None:
            q += " AND game_date=?"
            args.append(game_date)
        with self._lock:
            row = self._conn.execute(q + " ORDER BY updated_at DESC LIMIT 1", args).fetchone()
        if not row:
            return None
        return {"data": json.loads(row["data"]), "game_date": row["game_date"] or None, "updated_at": row["updated_at"]}

    def document_history(self, kind: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data,game_date FROM documents WHERE kind=? AND game_date!='' ORDER BY game_date", (kind,)
            ).fetchall()
        return [{"game_date": r["game_date"], "data": json.loads(r["data"])} for r in rows]

    # ------------------------------------------------------------ journal
    def add_scan(self, screen: str, game_date: str | None, summary: str, source: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO scans(at,screen,game_date,summary,source) VALUES(?,?,?,?,?)",
                (_now(), screen, game_date, summary, source),
            )
            self._conn.execute("DELETE FROM scans WHERE id < ?", (cur.lastrowid - 400,))
            self._conn.commit()
            return cur.lastrowid

    def update_scan(self, scan_id: int, summary: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE scans SET summary=? WHERE id=?", (summary, scan_id))
            self._conn.commit()

    def scans(self, limit: int = 30, since_id: int = 0) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM scans WHERE id>? ORDER BY id DESC LIMIT ?", (since_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def last_scan_id(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT MAX(id) AS m FROM scans").fetchone()
        return row["m"] or 0

    def counts(self) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT scope, COUNT(*) AS n FROM players GROUP BY scope").fetchall()
            sl = self._conn.execute("SELECT COUNT(*) AS n FROM players WHERE shortlist=1").fetchone()["n"]
        out = {s: 0 for s in SCOPES}
        out.update({r["scope"]: r["n"] for r in rows})
        out["shortlist"] = sl
        return out

    def reset(self, keep_settings: bool = True) -> None:
        settings = self.settings()
        with self._lock:
            for t in ("players", "player_history", "documents", "scans", "meta"):
                self._conn.execute(f"DELETE FROM {t}")
            self._conn.commit()
        if keep_settings:
            self.set_meta("settings", settings)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
