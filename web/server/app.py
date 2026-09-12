#!/usr/bin/env python3
"""
Petit serveur autonome pour l'appli QCM (qcm_app.html), à faire tourner sur
le Raspberry Pi quand le site n'est PAS ouvert dans Claude.ai (donc sans accès
à window.storage). Même API "shape" que window.storage pour que le JS de
qcm_app_template.html n'ait quasiment rien à changer (voir storage_backend.js).

Stockage : SQLite (un seul fichier, zéro configuration, très bien adapté à un
Raspberry Pi -- pas besoin d'un vrai serveur de base de données).

Lancement :
    pip install flask --break-system-packages
    python3 web/server/app.py            # écoute sur 0.0.0.0:5000
    # puis, en prod sur le Pi, dans un tmux/systemd :
    #   FLASK_ENV=production python3 web/server/app.py

Endpoints (tous en JSON) :
    GET  /api/kv/<key>?shared=0|1              -> {value: ...} ou 404
    POST /api/kv/<key>            {value, shared}
    DELETE /api/kv/<key>?shared=0|1
    GET  /api/kv-list?prefix=...&shared=0|1     -> {keys: [...]}

    L'identité "personnelle" (shared=0) est dérivée d'un cookie de session
    anonyme posé au premier appel (PAS l'adresse IP -- voir web/README.md
    pour la raison : NAT de classe + RGPD).
"""
import json
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, g

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "web" / "server" / "qcm_data.sqlite3"
COOKIE_NAME = "qcm_anon_id"

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS kv (
                scope TEXT NOT NULL,      -- 'shared' ou l'id anonyme (personnel)
                key   TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (scope, key)
            )
        """)
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def scope_for(shared: bool):
    if shared:
        return "shared"
    anon_id = request.cookies.get(COOKIE_NAME)
    return anon_id or None  # None -> pas encore de cookie, traité par le caller


def _parse_shared():
    if request.method == "GET" or request.method == "DELETE":
        return request.args.get("shared", "0") in ("1", "true", "True")
    body = request.get_json(silent=True) or {}
    return bool(body.get("shared", False))


@app.route("/api/kv/<path:key>", methods=["GET"])
def kv_get(key):
    shared = _parse_shared()
    resp = jsonify(None)
    scope = "shared" if shared else request.cookies.get(COOKIE_NAME)
    if not scope:
        return jsonify({"error": "no anon id"}), 404
    row = get_db().execute(
        "SELECT value FROM kv WHERE scope=? AND key=?", (scope, key)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    resp = jsonify({"key": key, "value": row[0], "shared": shared})
    return _ensure_cookie(resp)


@app.route("/api/kv/<path:key>", methods=["POST"])
def kv_set(key):
    shared = _parse_shared()
    body = request.get_json(force=True)
    value = body["value"]
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)

    scope = "shared" if shared else request.cookies.get(COOKIE_NAME)
    resp_needs_cookie = False
    if not shared and not scope:
        scope = secrets.token_hex(16)
        resp_needs_cookie = True

    get_db().execute(
        "INSERT INTO kv (scope, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(scope, key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
        (scope, key, value),
    )
    get_db().commit()

    resp = jsonify({"key": key, "value": value, "shared": shared})
    if resp_needs_cookie:
        resp.set_cookie(COOKIE_NAME, scope, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@app.route("/api/kv/<path:key>", methods=["DELETE"])
def kv_delete(key):
    shared = _parse_shared()
    scope = "shared" if shared else request.cookies.get(COOKIE_NAME)
    if not scope:
        return jsonify({"error": "no anon id"}), 404
    get_db().execute("DELETE FROM kv WHERE scope=? AND key=?", (scope, key))
    get_db().commit()
    return jsonify({"key": key, "deleted": True, "shared": shared})


@app.route("/api/kv-list", methods=["GET"])
def kv_list():
    shared = _parse_shared()
    prefix = request.args.get("prefix", "")
    scope = "shared" if shared else request.cookies.get(COOKIE_NAME)
    if not scope:
        return jsonify({"keys": []})
    rows = get_db().execute(
        "SELECT key FROM kv WHERE scope=? AND key LIKE ?", (scope, prefix + "%")
    ).fetchall()
    return jsonify({"keys": [r[0] for r in rows], "prefix": prefix, "shared": shared})


def _ensure_cookie(resp):
    if not request.cookies.get(COOKIE_NAME):
        resp.set_cookie(COOKIE_NAME, secrets.token_hex(16), max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


# Sert aussi l'appli statique elle-même (pratique pour un seul processus sur le Pi)
@app.route("/")
def serve_app():
    html_path = ROOT / "build" / "output" / "qcm_app.html"
    if not html_path.exists():
        return "qcm_app.html introuvable -- lance d'abord web/build_qcm_artifact.py", 404
    return html_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
