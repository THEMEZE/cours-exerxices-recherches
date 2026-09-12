#!/usr/bin/env python3
"""
Parcourt data/**/*.yaml, repère tous les champs `animation:` (au niveau
exercice ou question), et appelle le bon script animations/src/<ref>.py
avec les `params` fournis dans la donnée.

Convention : `animation.ref` = nom du fichier script SANS l'extension .py,
ATTENDU dans animations/src/. Si plusieurs exercices référencent le même
`ref` avec les mêmes params, il n'est généré qu'une fois (cache par dossier
de sortie déjà existant -- utiliser --force pour régénérer).

Usage :
    python3 animations/generate_all.py
    python3 animations/generate_all.py --force
    python3 animations/generate_all.py --no-latex   # rendu plus rapide
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    list_matieres, list_docs_td_like, load_td, list_docs_cours, load_cours,
)

SRC_DIR = ROOT / "animations" / "src"
OUT_ROOT = ROOT / "animations" / "outputs"


def find_animation_refs():
    """Parcourt TOUTES les matières/documents (td, tp, cours) via
    common_data -- jamais de glob sur les chemins bruts, pour ne pas se
    dérégler silencieusement à chaque évolution de la structure de data/
    (bug réel rencontré : un ancien glob "data/*/ex*.yaml" ne trouvait plus
    rien après le passage à data/matieres/<m>/td/<doc>/ex*.yaml, et
    plus aucune animation n'était (re)générée, sans le moindre message
    d'erreur)."""
    refs = []
    for matiere in list_matieres():
        for type_doc in ("td", "tp"):
            for doc_slug in list_docs_td_like(matiere, type_doc):
                _, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
                for ex in exercices:
                    source = f"{matiere}/{type_doc}/{doc_slug}/{ex['slug']}"
                    if ex.get("animation"):
                        refs.append((ex["animation"], source))
                    for q in ex.get("questions", []):
                        if q.get("animation"):
                            refs.append((q["animation"], f"{source}::{q.get('id')}"))
        for doc_slug in list_docs_cours(matiere):
            doc = load_cours(matiere, doc_slug)
            source = f"{matiere}/cours/{doc_slug}"
            for sec in doc.get("sections", []):
                if sec.get("animation"):
                    refs.append((sec["animation"], f"{source}::section{sec.get('numero', '?')}"))
    return refs


def run_one(anim, source, force, no_latex):
    ref = anim["ref"]
    script = SRC_DIR / f"{ref}.py"
    outdir = OUT_ROOT / ref
    if outdir.exists() and not force:
        print(f"-- {ref} déjà généré (skip, --force pour régénérer) [{source}]")
        return
    if not script.exists():
        print(f"!! script manquant pour '{ref}' (attendu : {script}) [{source}]")
        return

    params = anim.get("params", {})
    formats = anim.get("formats", ["gif"])
    cmd = [sys.executable, str(script), "--ref", ref, "--formats", *formats]
    for key, val in params.items():
        flag = "--" + key.replace("_", "-")
        if isinstance(val, bool):
            if val:
                cmd.append(flag)
        else:
            cmd += [flag, str(val)]
    if no_latex:
        cmd.append("--no-latex")

    print(f"-> {ref} [{source}]")
    subprocess.run(cmd, check=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-latex", action="store_true")
    args = p.parse_args()

    for anim, source in find_animation_refs():
        run_one(anim, source, args.force, args.no_latex)


if __name__ == "__main__":
    main()
