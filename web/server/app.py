#!/usr/bin/env python3
"""
Serveur QCM -- Flask + SQLite, pour le Raspberry Pi (gunicorn : `web.server.app:app`).

Remplace l'ancien stockage clé/valeur ouvert (/api/kv/…) par des routes MÉTIER :
  * le navigateur ne peut plus lire/écrire/supprimer des clés arbitraires ;
  * la CORRECTION est faite ici : les bonnes réponses ne sont jamais envoyées
    aux téléphones avant que l'élève ait répondu ;
  * le pilotage (créer / lancer / arrêter / réinitialiser) exige le jeton enseignant ;
  * identité = UUID pseudonyme généré par le navigateur (aucun nom, aucune IP).

Les questions sont lues directement dans data/matieres/<m>/qcm/*.yaml (via qcm_data.py),
avec rechargement automatique quand un fichier change : ajouter des questions = éditer
le YAML, rien à relancer.

Deux types de séances :
  mode "direct" : l'enseignant lance UNE question à la fois (QR code au tableau) ;
  mode "serie"  : tout un chapitre (ou une sélection) est ouvert ; chacun avance à son rythme.

Variables d'environnement :
  QCM_TEACHER_TOKEN   jeton enseignant (OBLIGATOIRE pour piloter ; ex: python3 -c "import secrets;print(secrets.token_urlsafe(24))")
  QCM_DB_PATH         fichier SQLite (défaut : web/server/qcm_data.sqlite3)
  QCM_LEGACY_KV=1     réactive l'ancienne API /api/kv (migration seulement ; NON sécurisée)

Lancement de test :   python3 web/server/app.py          (écoute 0.0.0.0:5000)
Production (Pi)    :   gunicorn --workers 2 web.server.app:app   (voir web/README_QCM.md)
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, redirect, request, send_from_directory

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import qcm_data  # noqa: E402

DB_PATH = Path(os.environ.get("QCM_DB_PATH", ROOT / "web" / "server" / "qcm_data.sqlite3"))
QCM_PUBLIC = ROOT / "build" / "public" / "qcm"
COOKIE_NAME = "qcm_anon_id"          # ancienne API kv uniquement
SLUG_RE = re.compile(r"[A-Za-z0-9_-]+")
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # sans 0/O/1/I

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.json.ensure_ascii = False


def teacher_token() -> str:
    return os.environ.get("QCM_TEACHER_TOKEN", "")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------
# Base de données
# ----------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS qcm_sessions (
    id TEXT PRIMARY KEY,
    matiere TEXT NOT NULL,
    title TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('direct','serie','libre')),
    chapitre TEXT,
    qcm_ids TEXT NOT NULL DEFAULT '[]',      -- JSON : questions de la séance (serie) / lancées (direct) ; libre : calculé à la volée
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
    active_qcm_id TEXT,                      -- direct : question en cours (NULL = aucune)
    created_at TEXT NOT NULL,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS qcm_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES qcm_sessions(id) ON DELETE CASCADE,
    matiere TEXT NOT NULL,
    chapitre TEXT,
    qcm_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    choice_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('correct','incorrect','neutre')),
    submitted_at TEXT NOT NULL,
    UNIQUE(session_id, qcm_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_qr_session ON qcm_responses(session_id, qcm_id);
CREATE INDEX IF NOT EXISTS idx_qr_student ON qcm_responses(student_id, matiere, chapitre);
CREATE TABLE IF NOT EXISTS kv (
    scope TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (scope, key)
);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(DB_PATH, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        g.db = con
    return g.db


@app.teardown_appcontext
def close_db(exc):
    con = g.pop("db", None)
    if con is not None:
        con.close()


# ----------------------------------------------------------------------
# Banque de questions (cache invalidé quand un YAML change)
# ----------------------------------------------------------------------

_BANK: dict = {}   # matiere -> (signature, {id: question}, [ordre ids])


def bank(matiere: str):
    """(index {id: question}, ordre [ids]) -- ou (None, None) si la matière n'a pas de QCM."""
    if not SLUG_RE.fullmatch(matiere or ""):
        return None, None
    sig = qcm_data.signature(matiere)
    if not sig:
        _BANK.pop(matiere, None)
        return None, None
    cached = _BANK.get(matiere)
    if cached and cached[0] == sig:
        return cached[1], cached[2]
    items, seen = [], set()
    for q in qcm_data.load_all_qcm(matiere):
        errs = qcm_data.question_errors(q)
        if errs:                                  # question cassée : ignorée (voir `python3 tools/qcm.py check`)
            print(f"[qcm] question ignorée {q['id']} : {'; '.join(errs)}", file=sys.stderr)
            continue
        if q["id"] not in seen:
            seen.add(q["id"])
            items.append(q)
    index = {q["id"]: q for q in items}
    order = [q["id"] for q in items]
    _BANK[matiere] = (sig, index, order)
    return index, order


def public_question(q: dict) -> dict:
    """Ce que voit un téléphone AVANT de répondre : jamais `correct`, ni le feedback."""
    return {
        "id": q["id"], "chapitre": q["chapitre"], "moment": q["moment"],
        "difficulte": q.get("difficulte"), "question": q["question"],
        "choix": [{"id": c["id"], "texte": c["texte"], "neutre": bool(c.get("neutre"))} for c in q["choix"]],
        **qcm_data.media_for_web(q),            # {"figures": [...], "animation": {...}|None} (chemins web)
    }


def result_for(q: dict, choice_id: str, status: str) -> dict:
    """Ce que voit l'élève APRÈS avoir répondu."""
    right = next((c["id"] for c in q["choix"] if c.get("correct")), None)
    return {"status": status, "choice_id": choice_id, "correct_choice_id": right,
            "feedback": q["feedback"].get(status, ""), "explication": q.get("explication")}


# ----------------------------------------------------------------------
# Authentification enseignant / identité élève
# ----------------------------------------------------------------------

def is_teacher() -> bool:
    tok = teacher_token()
    supplied = request.headers.get("Authorization", "")
    return bool(tok) and hmac.compare_digest(supplied.encode(), f"Bearer {tok}".encode())


def teacher_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not teacher_token():
            return jsonify(error="QCM_TEACHER_TOKEN n'est pas configuré sur le serveur."), 503
        if not is_teacher():
            time.sleep(0.4)                      # freine les essais en rafale
            return jsonify(error="Jeton enseignant requis."), 401
        return fn(*a, **kw)
    return wrapper


def valid_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def student_id_from_request(data: dict | None = None):
    raw = request.headers.get("X-Student-ID") or (data or {}).get("student_id")
    return valid_uuid(raw)


def new_session_code(con) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not con.execute("SELECT 1 FROM qcm_sessions WHERE id=?", (code,)).fetchone():
            return code
    raise RuntimeError("code de séance introuvable")


def session_row(con, session_id):
    return con.execute("SELECT * FROM qcm_sessions WHERE id=?", ((session_id or "").upper(),)).fetchone()


def session_qcm_ids(s) -> list[str]:
    if s["mode"] == "libre":                  # entraînement libre : toujours les questions ACTUELLES du chapitre
        index, order = bank(s["matiere"])
        return [i for i in (order or [])
                if (not s["chapitre"] or index[i]["chapitre"] == s["chapitre"])
                and qcm_data.is_libre(s["matiere"], index[i]["chapitre"])]
    return json.loads(s["qcm_ids"] or "[]")


def free_session_code(matiere: str, chapitre: str | None) -> str:
    """Code STABLE de la séance d'entraînement libre d'un chapitre (même code pour tout le monde)."""
    import hashlib
    return "L" + hashlib.sha1(f"{matiere}|{chapitre or ''}".encode()).hexdigest()[:5].upper()


@app.post("/api/libre")
def api_free_session():
    """Entraînement libre (hors cours, sans enseignant) : ouvre / retrouve la séance permanente
    d'un chapitre (ou de toute la matière si `chapitre` est vide)."""
    data = request.get_json(silent=True) or {}
    matiere, chapitre = data.get("matiere", ""), data.get("chapitre") or None
    index, order = bank(matiere)
    if index is None:
        return jsonify(error="Matière sans QCM."), 404
    if chapitre and not any(q["chapitre"] == chapitre for q in index.values()):
        return jsonify(error="Chapitre inconnu."), 404
    if chapitre and not qcm_data.is_libre(matiere, chapitre):
        return jsonify(error="Ce chapitre n'est pas ouvert à l'entraînement libre (réservé aux séances en classe)."), 403
    if not chapitre and not qcm_data.chapitres_libres(matiere):
        return jsonify(error="Aucun chapitre en accès libre pour cette matière."), 403
    code = free_session_code(matiere, chapitre)
    con = get_db()
    if not session_row(con, code):
        title = "Entraînement libre — " + (chapitre or "toute la matière")
        with con:
            con.execute("INSERT OR IGNORE INTO qcm_sessions(id,matiere,title,mode,chapitre,qcm_ids,created_at) VALUES(?,?,?,?,?,?,?)",
                        (code, matiere, title, "libre", chapitre, "[]", now_iso()))
    return jsonify(session_id=code)


# ----------------------------------------------------------------------
# API publique
# ----------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify(status="ok", matieres=qcm_data.list_matieres_qcm(), teacher_configured=bool(teacher_token()))


@app.get("/api/qcm/<matiere>/chapitres")
def api_chapitres(matiere):
    index, _ = bank(matiere)
    if index is None:
        return jsonify(error="Matière sans QCM."), 404
    meta = qcm_data.matiere_meta(matiere)
    return jsonify(matiere=matiere, nom=meta.get("nom"), total=len(index), chapitres=qcm_data.chapitres(matiere))



def brief_session(s, con) -> dict:
    ids = session_qcm_ids(s)
    n_part = con.execute("SELECT COUNT(DISTINCT student_id) FROM qcm_responses WHERE session_id=?", (s["id"],)).fetchone()[0]
    return {"id": s["id"], "matiere": s["matiere"], "title": s["title"], "mode": s["mode"],
            "chapitre": s["chapitre"], "status": s["status"], "n_questions": len(ids),
            "participants": n_part, "created_at": s["created_at"]}


@app.get("/api/sessions")
def api_sessions_open():
    """Séances ouvertes d'une matière (pour rejoindre sans QR)."""
    matiere = request.args.get("matiere", "")
    con = get_db()
    rows = con.execute("SELECT * FROM qcm_sessions WHERE matiere=? AND status='open' AND mode!='libre' ORDER BY created_at DESC LIMIT 20",
                       (matiere,)).fetchall()
    return jsonify([{k: v for k, v in brief_session(r, con).items() if k != "participants"} for r in rows])


@app.get("/api/sessions/<session_id>")
def api_session(session_id):
    con = get_db()
    s = session_row(con, session_id)
    if not s:
        return jsonify(error="Séance introuvable."), 404
    index, _ = bank(s["matiere"])
    index = index or {}
    sid = student_id_from_request()
    ids = session_qcm_ids(s)
    mine = {}
    if sid:
        for r in con.execute("SELECT qcm_id,choice_id,status FROM qcm_responses WHERE session_id=? AND student_id=?",
                             (s["id"], sid)):
            q = index.get(r["qcm_id"])
            if q:
                mine[r["qcm_id"]] = result_for(q, r["choice_id"], r["status"])
    out = brief_session(s, con)
    out["mine"] = mine
    out["n_answered"] = len(mine)
    if s["mode"] == "direct":
        q = index.get(s["active_qcm_id"]) if s["active_qcm_id"] else None
        out["active"] = public_question(q) if q and s["status"] == "open" else None
        out["n_launched"] = len(ids)
    else:
        out["questions"] = [public_question(index[i]) for i in ids if i in index]
    return jsonify(out)


@app.post("/api/responses")
def api_submit_response():
    data = request.get_json(silent=True) or {}
    sid = student_id_from_request(data)
    session_id = (data.get("session_id") or "").upper()
    qcm_id, choice_id = data.get("qcm_id"), data.get("choice_id")
    if not (sid and session_id and qcm_id and choice_id):
        return jsonify(error="Données incomplètes."), 400
    con = get_db()
    s = session_row(con, session_id)
    if not s or (s["status"] != "open" and s["mode"] != "libre"):
        return jsonify(error="Cette séance n'est plus ouverte."), 409
    ids = session_qcm_ids(s)
    if s["mode"] == "direct":
        if s["active_qcm_id"] != qcm_id:
            return jsonify(error="Cette question n'est plus ouverte."), 409
    elif qcm_id not in ids:
        return jsonify(error="Question hors séance."), 400
    index, _ = bank(s["matiere"])
    q = (index or {}).get(qcm_id)
    if not q:
        return jsonify(error="Question inconnue."), 404
    choice = next((c for c in q["choix"] if c["id"] == choice_id), None)
    if not choice:
        return jsonify(error="Proposition inconnue."), 400
    status = "correct" if choice.get("correct") else ("neutre" if choice.get("neutre") else "incorrect")
    upsert = (" ON CONFLICT(session_id,qcm_id,student_id) DO UPDATE SET choice_id=excluded.choice_id,"
              " status=excluded.status, submitted_at=excluded.submitted_at") if s["mode"] == "libre" else ""
    try:                                      # libre : on peut REFAIRE une question (dernière réponse retenue)
        with con:
            con.execute("INSERT INTO qcm_responses(session_id,matiere,chapitre,qcm_id,student_id,choice_id,status,submitted_at)"
                        " VALUES(?,?,?,?,?,?,?,?)" + upsert,
                        (s["id"], s["matiere"], q["chapitre"], qcm_id, sid, choice_id, status, now_iso()))
    except sqlite3.IntegrityError:        # requête rejouée après une coupure réseau : idempotent
        old = con.execute("SELECT choice_id,status FROM qcm_responses WHERE session_id=? AND qcm_id=? AND student_id=?",
                          (s["id"], qcm_id, sid)).fetchone()
        res = result_for(q, old["choice_id"], old["status"])
        res.update(already=True)
        return jsonify(res), 200
    return jsonify(result_for(q, choice_id, status)), 201


def question_stats(con, s, q, include_correct: bool) -> dict:
    rows = con.execute("SELECT choice_id,status,COUNT(*) n FROM qcm_responses WHERE session_id=? AND qcm_id=? GROUP BY choice_id,status",
                       (s["id"], q["id"])).fetchall()
    by_choice = {c["id"]: 0 for c in q["choix"]}
    counts = {"correct": 0, "incorrect": 0, "neutre": 0}
    for r in rows:
        by_choice[r["choice_id"]] = by_choice.get(r["choice_id"], 0) + r["n"]
        counts[r["status"]] += r["n"]
    total = sum(counts.values())
    evaluated = counts["correct"] + counts["incorrect"]
    out = {"qcm_id": q["id"], "chapitre": q["chapitre"], "question": q["question"], "total": total,
           "counts": counts, "by_choice": by_choice,
           "success_rate": round(100 * counts["correct"] / total, 1) if total else None,
           "success_rate_evaluated": round(100 * counts["correct"] / evaluated, 1) if evaluated else None,
           "choices": [{"id": c["id"], "texte": c["texte"], "neutre": bool(c.get("neutre")),
                        **({"correct": bool(c.get("correct"))} if include_correct else {})} for c in q["choix"]]}
    return out


@app.get("/api/statistics/sessions/<session_id>")
def api_session_stats(session_id):
    """Statistiques collectives AGRÉGÉES (jamais d'identifiants). Pour un élève, une question n'est
    visible qu'après y avoir répondu (ou quand la séance est close) : on ne spoile pas la classe."""
    con = get_db()
    s = session_row(con, session_id)
    if not s:
        return jsonify(error="Séance introuvable."), 404
    index, _ = bank(s["matiere"])
    index = index or {}
    teacher = is_teacher()
    sid = student_id_from_request()
    answered = set()
    if sid:
        answered = {r[0] for r in con.execute("SELECT qcm_id FROM qcm_responses WHERE session_id=? AND student_id=?", (s["id"], sid))}
    wanted = [request.args["qcm_id"]] if request.args.get("qcm_id") else session_qcm_ids(s)
    stats = []
    for qid in wanted:
        q = index.get(qid)
        if not q:
            continue
        if teacher or s["status"] == "closed" or qid in answered:
            stats.append(question_stats(con, s, q, include_correct=teacher or qid in answered or s["status"] == "closed"))
    n_part = con.execute("SELECT COUNT(DISTINCT student_id) FROM qcm_responses WHERE session_id=?", (s["id"],)).fetchone()[0]
    tot = sum(x["total"] for x in stats)
    corr = sum(x["counts"]["correct"] for x in stats)
    return jsonify(session=brief_session(s, con), participants=n_part, questions=stats,
                   success_rate=round(100 * corr / tot, 1) if tot else None)


@app.get("/api/students/me/progress")
def api_student_progress():
    """Progression personnelle (toutes séances confondues) pour l'identifiant du navigateur."""
    sid = student_id_from_request()
    if not sid:
        return jsonify(error="Identifiant absent ou invalide."), 400
    matiere = request.args.get("matiere")
    con = get_db()
    sql = "SELECT matiere,chapitre,qcm_id,status,submitted_at,session_id FROM qcm_responses WHERE student_id=?"
    args = [sid]
    if matiere:
        sql += " AND matiere=?"
        args.append(matiere)
    rows = con.execute(sql + " ORDER BY submitted_at", args).fetchall()
    # Une question répondue plusieurs fois (séances différentes) : on garde la plus récente.
    last = {}
    for r in rows:
        last[(r["matiere"], r["qcm_id"])] = r
    totals = {"correct": 0, "incorrect": 0, "neutre": 0}
    chap = {}
    for r in last.values():
        totals[r["status"]] += 1
        c = chap.setdefault((r["matiere"], r["chapitre"]), {"matiere": r["matiere"], "chapitre": r["chapitre"],
                                                           "repondues": 0, "correct": 0, "incorrect": 0, "neutre": 0})
        c["repondues"] += 1
        c[r["status"]] += 1
    chap_list = []
    for c in chap.values():
        index, _ = bank(c["matiere"])
        c["total_banque"] = sum(1 for q in (index or {}).values() if q["chapitre"] == c["chapitre"])
        ev = c["correct"] + c["incorrect"]
        c["taux_reussite"] = round(100 * c["correct"] / ev, 1) if ev else None
        chap_list.append(c)
    chap_list.sort(key=lambda c: (c["taux_reussite"] is None, c["taux_reussite"] or 0))   # à retravailler d'abord
    to_review = []
    for r in last.values():
        if r["status"] != "correct":
            index, _ = bank(r["matiere"])
            q = (index or {}).get(r["qcm_id"])
            if q:
                to_review.append({"qcm_id": q["id"], "chapitre": q["chapitre"], "question": q["question"]})
    ev = totals["correct"] + totals["incorrect"]
    return jsonify(total=len(last), counts=totals, taux_reussite=round(100 * totals["correct"] / ev, 1) if ev else None,
                   chapitres=chap_list, a_revoir=to_review[:30],
                   n_seances=len({r["session_id"] for r in rows}))


# ----------------------------------------------------------------------
# API enseignant
# ----------------------------------------------------------------------

@app.get("/api/teacher/check")
@teacher_required
def teacher_check():
    return jsonify(ok=True)


@app.get("/api/teacher/<matiere>/questions")
@teacher_required
def teacher_questions(matiere):
    index, order = bank(matiere)
    if index is None:
        return jsonify(error="Matière sans QCM."), 404
    return jsonify([{"id": i, "chapitre": index[i]["chapitre"], "moment": index[i]["moment"],
                     "difficulte": index[i].get("difficulte"), "question": index[i]["question"],
                     "n_choix": len(index[i]["choix"])} for i in order])


@app.get("/api/teacher/sessions")
@teacher_required
def teacher_sessions():
    matiere = request.args.get("matiere")
    con = get_db()
    rows = con.execute("SELECT * FROM qcm_sessions" + (" WHERE matiere=?" if matiere else "") +
                       " ORDER BY created_at DESC LIMIT 100", ([matiere] if matiere else [])).fetchall()
    return jsonify([brief_session(r, con) | {"active_qcm_id": r["active_qcm_id"]} for r in rows])


@app.post("/api/teacher/sessions")
@teacher_required
def teacher_create_session():
    data = request.get_json(silent=True) or {}
    matiere = data.get("matiere", "")
    mode = data.get("mode", "direct")
    chapitre = data.get("chapitre") or None
    title = (data.get("title") or "").strip()
    index, order = bank(matiere)
    if index is None:
        return jsonify(error="Matière inconnue ou sans QCM."), 400
    if mode not in ("direct", "serie"):
        return jsonify(error="Mode inconnu (direct | serie)."), 400
    pool = [i for i in order if not chapitre or index[i]["chapitre"] == chapitre]
    if chapitre and not pool:
        return jsonify(error=f"Chapitre inconnu : {chapitre}"), 400
    explicit = data.get("qcm_ids")
    if explicit:
        unknown = [i for i in explicit if i not in index]
        if unknown:
            return jsonify(error=f"Questions inconnues : {', '.join(unknown[:5])}"), 400
        pool = list(explicit)
    if mode == "serie":
        if data.get("ordre") == "aleatoire":
            import random
            random.shuffle(pool)
        if data.get("nb_questions"):
            pool = pool[: int(data["nb_questions"])]
        ids = pool
    else:
        ids = []                                   # direct : se remplit au fil des lancements
    con = get_db()
    code = new_session_code(con)
    title = title or (f"{chapitre or 'QCM'} — {datetime.now().strftime('%d/%m/%Y')}")
    with con:
        con.execute("INSERT INTO qcm_sessions(id,matiere,title,mode,chapitre,qcm_ids,created_at) VALUES(?,?,?,?,?,?,?)",
                    (code, matiere, title, mode, chapitre, json.dumps(ids), now_iso()))
    return jsonify(session_id=code, url=f"/qcm/{matiere}/?s={code}", n_questions=len(ids)), 201


@app.post("/api/teacher/sessions/<session_id>/launch")
@teacher_required
def teacher_launch(session_id):
    data = request.get_json(silent=True) or {}
    qcm_id = data.get("qcm_id")
    con = get_db()
    s = session_row(con, session_id)
    if not s:
        return jsonify(error="Séance introuvable."), 404
    if s["mode"] != "direct":
        return jsonify(error="Lancement question par question : séances en mode direct seulement."), 400
    if s["status"] != "open":
        return jsonify(error="Séance close."), 409
    index, _ = bank(s["matiere"])
    if qcm_id not in (index or {}):
        return jsonify(error="Question inconnue pour cette matière."), 400
    ids = session_qcm_ids(s)
    if qcm_id not in ids:
        ids.append(qcm_id)
    with con:
        con.execute("UPDATE qcm_sessions SET active_qcm_id=?, qcm_ids=? WHERE id=?", (qcm_id, json.dumps(ids), s["id"]))
    return jsonify(ok=True, active_qcm_id=qcm_id)


@app.post("/api/teacher/sessions/<session_id>/stop")
@teacher_required
def teacher_stop(session_id):
    """Arrête la question en cours (les réponses sont refusées) ; la séance reste ouverte."""
    con = get_db()
    with con:
        cur = con.execute("UPDATE qcm_sessions SET active_qcm_id=NULL WHERE id=?", (session_id.upper(),))
    return (jsonify(ok=True) if cur.rowcount else (jsonify(error="Séance introuvable."), 404))


@app.post("/api/teacher/sessions/<session_id>/close")
@teacher_required
def teacher_close(session_id):
    """Clôt la séance : plus de réponses ; les résultats collectifs deviennent visibles de tous."""
    con = get_db()
    with con:
        cur = con.execute("UPDATE qcm_sessions SET status='closed', active_qcm_id=NULL, closed_at=? WHERE id=?",
                          (now_iso(), session_id.upper()))
    return (jsonify(ok=True) if cur.rowcount else (jsonify(error="Séance introuvable."), 404))


@app.post("/api/teacher/sessions/<session_id>/reopen")
@teacher_required
def teacher_reopen(session_id):
    con = get_db()
    with con:
        cur = con.execute("UPDATE qcm_sessions SET status='open', closed_at=NULL WHERE id=?", (session_id.upper(),))
    return (jsonify(ok=True) if cur.rowcount else (jsonify(error="Séance introuvable."), 404))


@app.post("/api/teacher/sessions/<session_id>/reset")
@teacher_required
def teacher_reset(session_id):
    """Efface les réponses de la séance (ou d'une seule question : {"qcm_id": …})."""
    data = request.get_json(silent=True) or {}
    con = get_db()
    with con:
        if data.get("qcm_id"):
            cur = con.execute("DELETE FROM qcm_responses WHERE session_id=? AND qcm_id=?", (session_id.upper(), data["qcm_id"]))
        else:
            cur = con.execute("DELETE FROM qcm_responses WHERE session_id=?", (session_id.upper(),))
    return jsonify(ok=True, supprimees=cur.rowcount)


@app.delete("/api/teacher/sessions/<session_id>")
@teacher_required
def teacher_delete(session_id):
    con = get_db()
    with con:
        con.execute("DELETE FROM qcm_responses WHERE session_id=?", (session_id.upper(),))
        cur = con.execute("DELETE FROM qcm_sessions WHERE id=?", (session_id.upper(),))
    return (jsonify(ok=True) if cur.rowcount else (jsonify(error="Séance introuvable."), 404))


@app.get("/api/teacher/sessions/<session_id>/report")
@teacher_required
def teacher_report(session_id):
    """Bilan complet : par question (avec bonne réponse, répartition) + questions les plus difficiles."""
    con = get_db()
    s = session_row(con, session_id)
    if not s:
        return jsonify(error="Séance introuvable."), 404
    index, _ = bank(s["matiere"])
    index = index or {}
    stats = [question_stats(con, s, index[i], include_correct=True) for i in session_qcm_ids(s) if i in index]
    hardest = sorted((x for x in stats if x["success_rate_evaluated"] is not None and x["success_rate_evaluated"] < 100), key=lambda x: x["success_rate_evaluated"])[:5]
    n_part = con.execute("SELECT COUNT(DISTINCT student_id) FROM qcm_responses WHERE session_id=?", (s["id"],)).fetchone()[0]
    tot = sum(x["total"] for x in stats)
    corr = sum(x["counts"]["correct"] for x in stats)
    return jsonify(session=brief_session(s, con), participants=n_part, questions=stats,
                   plus_difficiles=[x["qcm_id"] for x in hardest],
                   success_rate=round(100 * corr / tot, 1) if tot else None)


# ----------------------------------------------------------------------
# Pages (dev / sans nginx ; en prod nginx sert build/public/qcm/ en statique)
# ----------------------------------------------------------------------

@app.route("/")
def root():
    return redirect("/qcm/")


@app.route("/qcm/")
def qcm_index():
    if not (QCM_PUBLIC / "index.html").exists():
        return "Aucun QCM publié -- lance web/publish_hosting.py", 404
    return send_from_directory(QCM_PUBLIC, "index.html")


@app.route("/qcm/<matiere>/")
def qcm_matiere(matiere):
    if not SLUG_RE.fullmatch(matiere) or not (QCM_PUBLIC / matiere / "index.html").exists():
        return "QCM introuvable pour cette matière", 404
    return send_from_directory(QCM_PUBLIC / matiere, "index.html")


@app.route("/figures/<path:name>")
def dev_figures(name):
    """Dev local seulement (en prod nginx sert /figures/ directement)."""
    return send_from_directory(qcm_data.FIG_DIR, name)


@app.route("/animations/<path:name>")
def dev_animations(name):
    """Dev local seulement (en prod nginx sert /animations/ directement)."""
    return send_from_directory(qcm_data.ANIM_DIR, name)


# ----------------------------------------------------------------------
# Ancienne API clé/valeur (désactivée par défaut -- QCM_LEGACY_KV=1 pour migrer)
# ----------------------------------------------------------------------

if os.environ.get("QCM_LEGACY_KV") == "1":
    @app.route("/api/kv/<path:key>", methods=["GET", "POST", "DELETE"])
    def kv_one(key):
        shared = (request.args.get("shared", "0") in ("1", "true")) if request.method != "POST" \
            else bool((request.get_json(silent=True) or {}).get("shared", False))
        scope = "shared" if shared else request.cookies.get(COOKIE_NAME)
        con = get_db()
        if request.method == "POST":
            body = request.get_json(force=True)
            value = body["value"] if isinstance(body["value"], str) else json.dumps(body["value"], ensure_ascii=False)
            new_cookie = False
            if not scope:
                scope, new_cookie = secrets.token_hex(16), True
            with con:
                con.execute("INSERT INTO kv(scope,key,value) VALUES(?,?,?) ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value,"
                            " updated_at=CURRENT_TIMESTAMP", (scope, key, value))
            resp = jsonify(key=key, value=value, shared=shared)
            if new_cookie:
                resp.set_cookie(COOKIE_NAME, scope, max_age=31536000, samesite="Lax")
            return resp
        if not scope:
            return jsonify(error="no anon id"), 404
        if request.method == "DELETE":
            with con:
                con.execute("DELETE FROM kv WHERE scope=? AND key=?", (scope, key))
            return jsonify(key=key, deleted=True)
        row = con.execute("SELECT value FROM kv WHERE scope=? AND key=?", (scope, key)).fetchone()
        return jsonify(key=key, value=row[0], shared=shared) if row else (jsonify(error="not found"), 404)

    @app.route("/api/kv-list")
    def kv_list():
        shared = request.args.get("shared", "0") in ("1", "true")
        scope = "shared" if shared else request.cookies.get(COOKIE_NAME)
        prefix = request.args.get("prefix", "")
        rows = get_db().execute("SELECT key FROM kv WHERE scope=? AND key LIKE ?", (scope, prefix + "%")).fetchall() if scope else []
        return jsonify(keys=[r[0] for r in rows], prefix=prefix, shared=shared)


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not teacher_token():
        print("⚠️  QCM_TEACHER_TOKEN n'est pas défini : la vue enseignant sera inaccessible.")
    # debug=True ouvre un débogueur à distance : host 127.0.0.1 par défaut (HOST=0.0.0.0 pour tester depuis un téléphone du même Wi-Fi, sans FLASK_DEBUG).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
