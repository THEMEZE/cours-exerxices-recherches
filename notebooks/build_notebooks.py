#!/usr/bin/env python3
"""
Génère un notebook Jupyter (.ipynb) par exercice : énoncé + figure en Markdown,
une cellule de code qui rejoue l'animation de l'exercice (matplotlib), et
(selon le profil de visibilité) des cellules "coup de pouce" / "correction" /
"solution détaillée" -- taguées `solution` pour pouvoir être masquées par un
lecteur de notebook (nbconvert --TagRemovePreprocessor, JupyterLite, etc.)
même quand elles sont incluses dans le fichier.

Objectif : ces notebooks peuvent être ouverts tels quels (Jupyter classique,
JupyterLab, VS Code) OU embarqués sur le futur site via JupyterLite (exécution
100% dans le navigateur, pas de serveur Python nécessaire côté Raspberry Pi).

Usage :
    python3 notebooks/build_notebooks.py --profile avant_seance --matiere physique-ondes-ipsa
    python3 notebooks/build_notebooks.py --profile corrige_complet --matiere physique-ondes-ipsa --out ~/monsite/notebooks
"""
import argparse
import sys
from pathlib import Path

import nbformat as nbf
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    list_matieres, list_docs_td_like, load_td, apply_visibility_to_exercice,
    enrich_media_paths, clean_exercice_for_web, niveau_label,
)

DEFAULT_OUT = ROOT / "notebooks" / "generated"

ANIM_CODE_TEMPLATE = '''\
# Cellule générée automatiquement -- rejoue l'animation de l'exercice.
# Le code source complet est dans animations/src/{script}.py ; ici on
# n'appelle que les fonctions de construction pour l'afficher inline.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("{root}") / "animations" / "src"))
from common.style import apply_style
import {module} as anim_mod
import matplotlib.pyplot as plt
from matplotlib import animation as mpl_animation
from IPython.display import HTML

apply_style(use_latex=False)

{build_call}

fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2)
ax.set_ylim(-1.3, 1.3)
ax.set_xlabel("$x$"); ax.set_ylabel("$y$")

def _update(i):
    frame = frames[i]
    x, y = frame[0], frame[1]
    line.set_data(x, y)
    return line,

anim = mpl_animation.FuncAnimation(fig, _update, frames=len(frames), interval=60, blit=True)
plt.close(fig)
HTML(anim.to_jshtml())
'''


def build_call_for(animation: dict) -> str:
    ref = animation["ref"]
    params = animation.get("params", {})
    if params.get("mode") == "modes_propres" or ref == "anim_corde_stationnaire":
        n_max = params.get("N_max", 4)
        highlight = params.get("highlight_nodes", False)
        return (f"module = anim_mod\n"
                f"frames = module.build_frames_modes_propres(N_max={n_max}, n_frames=40, "
                f"highlight_nodes={highlight})")
    lam = params.get("lam", 1.0)
    T = params.get("T", 1.0)
    xmax = params.get("xmax", 4)
    return (f"module = anim_mod\n"
            f"frames = module.build_frames_onde_progressive(lam={lam}, T={T}, xmax={xmax}, n_frames=40)")


def question_markdown(q: dict) -> str:
    parts = [q["enonce"].strip()]
    if q.get("coup_de_pouce"):
        parts.append(f"> 💡 **Coup de pouce** — {q['coup_de_pouce'].strip()}")
    for niveau, texte in q.get("aller_plus_loin", {}).items():
        parts.append(f"> 🔭 **Aller plus loin — {niveau_label(niveau)}** — {texte.strip()}")
    return "\n\n".join(parts)


def build_notebook(ex: dict, meta: dict) -> "nbf.NotebookNode":
    nb = nbf.v4.new_notebook()
    cells = []

    header = f"# TD — {meta['titre']}\n## Exercice {ex['numero']}. {ex['intitule']}\n\n{ex.get('enonce_intro','').strip()}"
    cells.append(nbf.v4.new_markdown_cell(header))

    if ex.get("figure"):
        cells.append(nbf.v4.new_markdown_cell(f"![{ex['figure'].get('legende','')}]({ex['figure']['src']})"))

    if ex.get("animation"):
        module = ex["animation"]["ref"]
        code = ANIM_CODE_TEMPLATE.format(
            script=module, module=module, root=str(ROOT),
            build_call=build_call_for(ex["animation"]),
        )
        anim_cell = nbf.v4.new_code_cell(code)
        anim_cell["metadata"]["tags"] = ["animation"]
        cells.append(anim_cell)

    for item in ex.get("contenu", []):
        if item["kind"] == "intro":
            cells.append(nbf.v4.new_markdown_cell(item["enonce"]))
        elif item["kind"] == "single":
            cells.append(nbf.v4.new_markdown_cell(f"**Question {item.get('id','')}.** " + question_markdown(item)))
            if item.get("correction"):
                c = nbf.v4.new_markdown_cell(f"✅ **Correction** — {item['correction'].strip()}")
                c["metadata"]["tags"] = ["solution"]
                cells.append(c)
            if item.get("solution"):
                s = nbf.v4.new_markdown_cell(f"📝 **Solution détaillée**\n\n{item['solution'].strip()}")
                s["metadata"]["tags"] = ["solution"]
                cells.append(s)
        elif item["kind"] == "group":
            cells.append(nbf.v4.new_markdown_cell(f"**Question {item['label']}.**"))
            for i, sq in enumerate(item["subquestions"]):
                letter = chr(ord("a") + i)
                cells.append(nbf.v4.new_markdown_cell(f"**{letter})** " + question_markdown(sq)))
                if sq.get("correction"):
                    c = nbf.v4.new_markdown_cell(f"✅ **Correction** — {sq['correction'].strip()}")
                    c["metadata"]["tags"] = ["solution"]
                    cells.append(c)
                if sq.get("solution"):
                    s = nbf.v4.new_markdown_cell(f"📝 **Solution détaillée**\n\n{sq['solution'].strip()}")
                    s["metadata"]["tags"] = ["solution"]
                    cells.append(s)

    nb["cells"] = cells
    nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return nb


def export_td(matiere: str, doc_slug: str, type_doc: str, opts: dict, out_dir: Path):
    meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
    td_out = out_dir / matiere / doc_slug
    td_out.mkdir(parents=True, exist_ok=True)
    for ex in exercices:
        ex_filtered = clean_exercice_for_web(apply_visibility_to_exercice(enrich_media_paths(ex), opts))
        nb = build_notebook(ex_filtered, meta)
        fname = f"ex{ex['numero']}_{ex['slug']}.ipynb"
        path = td_out / fname
        nbf.write(nb, path)
        # validité du fichier généré
        nbf.read(path, as_version=4)
        print(f"   -> {path.relative_to(out_dir)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("--matiere", default=None, help="ne traiter qu'une matière ; défaut : toutes")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()

    profiles = yaml.safe_load((ROOT / "web" / "visibility_profiles.yaml").read_text())["profiles"]
    if args.profile not in profiles:
        print(f"!! profil inconnu : {args.profile}")
        return
    opts = profiles[args.profile]
    out_dir = Path(args.out).expanduser()
    matieres = [args.matiere] if args.matiere else list_matieres()

    print(f"-- Notebooks, profil '{args.profile}' -> {out_dir}")
    for matiere in matieres:
        for type_doc in ("td", "tp"):
            for doc_slug in list_docs_td_like(matiere, type_doc):
                export_td(matiere, doc_slug, type_doc, opts, out_dir)


if __name__ == "__main__":
    main()
