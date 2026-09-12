#!/usr/bin/env python3
"""
Compile chaque figures/tikz/*.tex (un simple \\begin{tikzpicture}...\\end{tikzpicture},
le même fichier que celui \\input dans les PDF) en SVG autonome, pour le site
Quartz et l'export JSON (une page web ne sait pas compiler du TikZ).

Sortie : web/public/figures/<nom>.svg

Usage :
    python3 figures/render_web.py            # toutes les figures
    python3 figures/render_web.py --force     # ignore le cache (mtime)
"""
import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIKZ_DIR = ROOT / "figures" / "tikz"
OUT_DIR = ROOT / "web" / "public" / "figures"
TMP_DIR = ROOT / "figures" / ".render_tmp"

STANDALONE_TEMPLATE = r"""\documentclass[tikz,border=3pt]{standalone}
\usepackage{amsmath, amssymb}
\usetikzlibrary{calc, positioning, arrows.meta, decorations.pathmorphing}
\begin{document}
\input{%s}
\end{document}
"""


def render_one(tex_path: Path, force: bool):
    name = tex_path.stem.lower()  # cf. common_data.figure_web_path : Quartz
                                    # normalise les chemins d'image en minuscules
                                    # dans son résolveur de liens -- si le fichier
                                    # généré ne l'est pas déjà, l'image casse
                                    # silencieusement sur le site (bug réel trouvé
                                    # et corrigé pendant les tests).
    svg_path = OUT_DIR / f"{name}.svg"
    if svg_path.exists() and not force and svg_path.stat().st_mtime > tex_path.stat().st_mtime:
        print(f"-- {name}.svg à jour (skip)")
        return

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    wrapper = TMP_DIR / f"{name}_standalone.tex"
    wrapper.write_text(STANDALONE_TEMPLATE % str(tex_path.resolve()), encoding="utf-8")

    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(TMP_DIR), str(wrapper)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    pdf_path = wrapper.with_suffix(".pdf")
    if not pdf_path.exists():
        print(f"!! échec de compilation pour {name} -- voir {wrapper.with_suffix('.log')}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conv = subprocess.run(
        ["pdftocairo", "-svg", str(pdf_path), str(svg_path)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if svg_path.exists():
        print(f"-> {svg_path.relative_to(ROOT)}")
    else:
        print(f"!! pdftocairo a échoué pour {name} : {conv.stdout.decode(errors='ignore')[-400:]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    for tex_path in sorted(TIKZ_DIR.glob("*.tex")):
        render_one(tex_path, args.force)

    shutil.rmtree(TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
