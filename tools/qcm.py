#!/usr/bin/env python3
"""
Outil en ligne de commande pour les QCM (data/matieres/<matiere>/qcm/*.yaml).

    python3 tools/qcm.py stats                         # nombre de questions par matière / chapitre
    python3 tools/qcm.py check [matiere]               # valide (1 bonne réponse, ids uniques…) ; code retour 1 si erreur
    python3 tools/qcm.py new <matiere> <chapitre> ["Titre"]   # crée un fichier modèle prêt à remplir
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import qcm_data  # noqa: E402

MODELE = ROOT / "data" / "qcm_modele.yaml"


def cmd_stats(_):
    st = qcm_data.stats()
    if not st:
        print("Aucun QCM.")
        return 0
    total = 0
    for m, chaps in st.items():
        n = sum(chaps.values())
        total += n
        print(f"{m}  ({n})")
        for c, k in chaps.items():
            print(f"    {c:<40} {k:>4}")
    print(f"\nTotal : {total} question(s)")
    return 0


def cmd_check(a):
    errors, warns = qcm_data.validate(a.matiere)
    for w in warns:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")
    n = sum(sum(c.values()) for c in qcm_data.stats().values())
    print(f"\n{n} question(s) — {len(errors)} erreur(s), {len(warns)} avertissement(s)")
    return 1 if errors else 0


def cmd_new(a):
    d = qcm_data.qcm_dir(a.matiere)
    if not (qcm_data.DATA_DIR / a.matiere).is_dir():
        print(f"Matière inconnue : {a.matiere} (dossier data/matieres/{a.matiere}/ absent)")
        return 1
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{a.chapitre}.yaml"
    if out.exists():
        print(f"Existe déjà : {out}")
        return 1
    txt = MODELE.read_text(encoding="utf-8")
    txt = txt.replace("chapitre: mon_chapitre", f"chapitre: {a.chapitre}")
    txt = txt.replace('titre: "Chap. X — Titre du chapitre"', f'titre: "{a.titre or a.chapitre}"')
    out.write_text(txt, encoding="utf-8")
    print(f"Créé : {out.relative_to(ROOT)}  (supprime les questions d'exemple, ajoute les tiennes)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    c = sub.add_parser("check"); c.add_argument("matiere", nargs="?"); c.set_defaults(fn=cmd_check)
    n = sub.add_parser("new"); n.add_argument("matiere"); n.add_argument("chapitre"); n.add_argument("titre", nargs="?")
    n.set_defaults(fn=cmd_new)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
