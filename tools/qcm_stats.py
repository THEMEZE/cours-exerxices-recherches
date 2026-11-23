#!/usr/bin/env python3
"""
Statistiques QCM lues directement dans la base du Raspberry (SQLite) : combien d'élèves ont répondu,
combien ont juste -- par matière, chapitre, séance et question.

Usage (sur le Pi, ou sur une copie de la base) :
    python3 tools/qcm_stats.py                               # résumé par matière / chapitre
    python3 tools/qcm_stats.py --matiere physique-ondes-ipsa # détail question par question
    python3 tools/qcm_stats.py --matiere physique-ondes-ipsa --chapitre td1_qcm
    python3 tools/qcm_stats.py --libre                       # seulement l'entraînement libre (à la maison)
    python3 tools/qcm_stats.py --classe                      # seulement les séances en classe (direct / série)
    python3 tools/qcm_stats.py --csv stats.csv               # export (une ligne par question)
    python3 tools/qcm_stats.py --db /chemin/qcm_2026-12-01.sqlite3   # une sauvegarde

« % juste » = bonnes réponses / (bonnes + mauvaises) : la réponse « Je ne sais pas encore » (neutre) est
comptée à part. Les élèves sont des identifiants anonymes tirés au hasard dans leur navigateur.
(Le serveur donne aussi ces chiffres en direct : « Vue enseignant » > Rapport.)
"""
import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path(os.environ.get("QCM_DB_PATH", ROOT / "web" / "server" / "qcm_data.sqlite3"))


def pct(n, d):
    return f"{100 * n / d:5.1f} %" if d else "    — "


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--matiere")
    ap.add_argument("--chapitre")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--libre", action="store_true", help="entraînement libre seulement (hors cours)")
    g.add_argument("--classe", action="store_true", help="séances en classe seulement (direct / série)")
    ap.add_argument("--csv", help="écrit aussi un CSV (une ligne par question)")
    a = ap.parse_args()

    db = Path(a.db)
    if not db.is_file():
        print(f"Base introuvable : {db}  (QCM_DB_PATH ou --db ; elle est créée par le serveur au premier usage)")
        return 1
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    where, params = ["1=1"], []
    if a.matiere:
        where.append("r.matiere=?"); params.append(a.matiere)
    if a.chapitre:
        where.append("r.chapitre=?"); params.append(a.chapitre)
    if a.libre:
        where.append("s.mode='libre'")
    if a.classe:
        where.append("s.mode IN ('direct','serie')")
    W = " AND ".join(where)
    base = "FROM qcm_responses r JOIN qcm_sessions s ON s.id=r.session_id WHERE " + W

    total = con.execute(f"SELECT COUNT(*) n, COUNT(DISTINCT r.student_id) e {base}", params).fetchone()
    if not total["n"]:
        print("Aucune réponse enregistrée pour ce filtre.")
        return 0
    print(f"{total['n']} réponse(s) de {total['e']} élève(s) (identifiants anonymes) — base {db.name}\n")

    q = f"""SELECT r.matiere, COALESCE(r.chapitre,'(toute la matière)') chapitre,
                   COUNT(DISTINCT r.student_id) eleves, COUNT(*) reponses,
                   SUM(r.status='correct') ok, SUM(r.status='incorrect') ko, SUM(r.status='neutre') ne
            {base} GROUP BY r.matiere, r.chapitre ORDER BY r.matiere, r.chapitre"""
    print(f"{'matière':<34}{'chapitre':<26}{'élèves':>7}{'rép.':>6}{'% juste':>10}")
    for r in con.execute(q, params):
        print(f"{r['matiere']:<34}{r['chapitre']:<26}{r['eleves']:>7}{r['reponses']:>6}{pct(r['ok'], r['ok'] + r['ko']):>10}")

    if a.matiere or a.chapitre or a.csv:
        qq = f"""SELECT r.matiere, COALESCE(r.chapitre,'') chapitre, r.qcm_id,
                        COUNT(DISTINCT r.student_id) eleves, COUNT(*) reponses,
                        SUM(r.status='correct') ok, SUM(r.status='incorrect') ko, SUM(r.status='neutre') ne
                 {base} GROUP BY r.matiere, r.chapitre, r.qcm_id ORDER BY r.matiere, r.chapitre, (ok*1.0/MAX(ok+ko,1)), r.qcm_id"""
        rows = con.execute(qq, params).fetchall()
        print(f"\nPar question (de la plus difficile à la plus facile) :")
        print(f"{'question':<34}{'élèves':>7}{'juste':>7}{'faux':>6}{'neutre':>8}{'% juste':>10}")
        for r in rows:
            print(f"{r['qcm_id']:<34}{r['eleves']:>7}{r['ok']:>7}{r['ko']:>6}{r['ne']:>8}{pct(r['ok'], r['ok'] + r['ko']):>10}")
        if a.csv:
            with open(a.csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["matiere", "chapitre", "question", "eleves", "reponses", "justes", "fausses", "neutres", "pourcent_juste"])
                for r in rows:
                    d = r["ok"] + r["ko"]
                    w.writerow([r["matiere"], r["chapitre"], r["qcm_id"], r["eleves"], r["reponses"], r["ok"], r["ko"], r["ne"],
                                round(100 * r["ok"] / d, 1) if d else ""])
            print(f"\nCSV écrit : {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
