#!/usr/bin/env python3
"""
Génère web/qcm_app_template.html -> build/output/qcm_app_<matiere>.html (thème de la
matière : data/matieres/<matiere>/_matiere.yaml -> theme:).

NOUVEAU : la page ne contient plus les questions. Elle les demande au serveur Flask
(web/server/app.py), qui les lit dans data/matieres/<matiere>/qcm/*.yaml, garde les
bonnes réponses côté serveur et les relit tout seul quand un fichier change.
=> ajouter des questions = éditer un YAML (aucune régénération nécessaire pour qu'elles
   apparaissent) ; ce script ne sert qu'à (re)générer l'enveloppe visuelle par matière.

Une matière sans QCM n'a pas d'appli générée.

Usage :
    python3 web/build_qcm_artifact.py                              # toutes les matières qui ont des QCM
    python3 web/build_qcm_artifact.py --matiere physique-ondes-ipsa
    python3 web/build_qcm_artifact.py --strict                     # échoue si un QCM est invalide
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import qcm_data  # noqa: E402
from common_data import load_matiere_meta  # noqa: E402
from web.qcm_logos import logo_inner_svg, DEFAULT_LOGO  # noqa: E402

TEMPLATE = ROOT / "web" / "qcm_app_template.html"
OUT_DIR = ROOT / "build" / "output"

DEFAULT_THEME = {
    "titre_app": "Réveil de Cours",
    "sous_titre_app": "QCM en direct",
    "logo": DEFAULT_LOGO,
    "couleurs": {
        "route": "#1B3A4B", "happy": "#3FA796", "neutral": "#F5B942",
        "sad": "#E8604C", "fond": "#EAF4F4",
    },
}


def resolved_theme(matiere_slug: str) -> dict:
    """Thème de la matière, complété par les valeurs par défaut pour toute
    clé absente (rien à déclarer si tu es content du thème par défaut)."""
    meta = load_matiere_meta(matiere_slug)
    theme = dict(DEFAULT_THEME)
    declared = meta.get("theme", {}) or {}
    theme.update({k: v for k, v in declared.items() if k != "couleurs"})
    theme["couleurs"] = {**DEFAULT_THEME["couleurs"], **(declared.get("couleurs") or {})}
    return theme


def build_for_matiere(matiere_slug: str, out_name: str = None):
    theme = resolved_theme(matiere_slug)
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__MATIERE_ID__", matiere_slug)
    html = html.replace("__APP_TITLE__", theme["titre_app"])
    html = html.replace("__APP_SUBTITLE__", theme["sous_titre_app"])
    html = html.replace("__LOGO_INNER_SVG__", logo_inner_svg(theme["logo"]))
    c = theme["couleurs"]
    html = html.replace("__COLOR_FOND__", c["fond"])
    html = html.replace("__COLOR_ROUTE__", c["route"])
    html = html.replace("__COLOR_HAPPY__", c["happy"])
    html = html.replace("__COLOR_NEUTRAL__", c["neutral"])
    html = html.replace("__COLOR_SAD__", c["sad"])
    # Le favicon (data URI SVG) a besoin de couleurs URL-encodées : "#" -> "%23".
    html = html.replace("__COLOR_ROUTE_URLENC__", c["route"].replace("#", "%23"))
    html = html.replace("__COLOR_HAPPY_URLENC__", c["happy"].replace("#", "%23"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / (out_name or f"qcm_app_{matiere_slug}.html")
    out_path.write_text(html, encoding="utf-8")
    chaps = qcm_data.chapitres(matiere_slug)
    n = sum(c["n"] for c in chaps)
    print(f"-> {out_path} ({n} question(s) en {len(chaps)} chapitre(s), thème '{theme['titre_app']}')")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matiere", default=None, help="ne générer que pour cette matière")
    p.add_argument("--out", default=None, help="nom de fichier de sortie (avec --matiere)")
    p.add_argument("--strict", action="store_true", help="échouer si un QCM est invalide")
    args = p.parse_args()

    errors, warns = qcm_data.validate(args.matiere)
    for w in warns[:10]:
        print(f"   ⚠️  {w}")
    if len(warns) > 10:
        print(f"   ⚠️  … et {len(warns) - 10} autre(s) avertissement(s) (python3 tools/qcm.py check)")
    for e in errors:
        print(f"   ❌ {e}")
    if errors:
        print(f"   {len(errors)} question(s) invalide(s) : le serveur les ignorera tant qu'elles ne sont pas corrigées.")
        if args.strict:
            return 1

    matieres = [args.matiere] if args.matiere else qcm_data.list_matieres_qcm()
    built = [m for m in matieres if qcm_data.qcm_files(m) and build_for_matiere(m, args.out if args.matiere else None)]
    if not built:
        print("Aucun QCM trouvé -- vérifie data/matieres/*/qcm/*.yaml (voir web/README_QCM.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
