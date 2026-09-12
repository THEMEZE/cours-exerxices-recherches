#!/usr/bin/env python3
"""
Génère web/qcm_app_template.html -> build/output/qcm_app_<matiere>.html en
y injectant le contenu de data/matieres/<matiere>/qcm/*.yaml ET le thème
visuel de la matière (data/matieres/<matiere>/_matiere.yaml -> theme:) --
même DA (mascotte, route, callouts colorés) pour toutes tes matières,
seules les couleurs/le logo/le titre changent. Voir web/README_QCM.md.

Une matière sans QCM n'a pas d'appli générée (rien à afficher).

Usage :
    python3 web/build_qcm_artifact.py                              # toutes les matières qui ont des QCM
    python3 web/build_qcm_artifact.py --matiere physique-ondes-ipsa
    python3 web/build_qcm_artifact.py --matiere physique-ondes-ipsa --td td1   # un seul document
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import list_matieres, load_matiere_meta, load_all_qcm  # noqa: E402
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


def build_for_matiere(matiere_slug: str, qcm_items: list, out_name: str = None):
    theme = resolved_theme(matiere_slug)
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__QCM_DATA_JSON__", json.dumps(qcm_items, ensure_ascii=False, indent=2))
    html = html.replace("__APP_TITLE__", theme["titre_app"])
    html = html.replace("__APP_SUBTITLE__", theme["sous_titre_app"])
    html = html.replace("__LOGO_INNER_SVG__", logo_inner_svg(theme["logo"]))
    c = theme["couleurs"]
    html = html.replace("__COLOR_FOND__", c["fond"])
    html = html.replace("__COLOR_ROUTE__", c["route"])
    html = html.replace("__COLOR_HAPPY__", c["happy"])
    html = html.replace("__COLOR_NEUTRAL__", c["neutral"])
    html = html.replace("__COLOR_SAD__", c["sad"])
    # Le favicon (data URI SVG) a besoin de couleurs URL-encodées : "#"
    # doit devenir "%23" dans une data URI SVG non quotée.
    html = html.replace("__COLOR_ROUTE_URLENC__", c["route"].replace("#", "%23"))
    html = html.replace("__COLOR_HAPPY_URLENC__", c["happy"].replace("#", "%23"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / (out_name or f"qcm_app_{matiere_slug}.html")
    out_path.write_text(html, encoding="utf-8")
    print(f"-> {out_path} ({len(qcm_items)} QCM, thème '{theme['titre_app']}', logo '{theme['logo']}')")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matiere", default=None, help="ne générer que pour cette matière")
    p.add_argument("--td", default=None, help="ne garder que les QCM de ce document (ex: td1)")
    p.add_argument("--out", default=None, help="nom de fichier de sortie (par défaut: qcm_app_<matiere>.html)")
    args = p.parse_args()

    matieres = [args.matiere] if args.matiere else list_matieres()
    any_built = False
    for matiere in matieres:
        qcm_items = load_all_qcm(matiere_slug=matiere, td_filter=args.td)
        if not qcm_items:
            continue
        build_for_matiere(matiere, qcm_items, args.out if args.matiere else None)
        any_built = True

    if not any_built:
        print("Aucun QCM trouvé -- vérifie data/matieres/*/qcm/*.yaml (voir web/README_QCM.md)")


if __name__ == "__main__":
    main()
