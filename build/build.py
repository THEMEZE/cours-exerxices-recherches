#!/usr/bin/env python3
"""
Moteur de génération des TD.

Usage :
    python3 build/build.py                 # génère toutes les cibles de config.yaml
    python3 build/build.py td1_enonce       # ne génère que cette cible
    python3 build/build.py --no-pdf         # génère les .tex seulement (pas de pdflatex)

Principe :
    data/*.yaml (une vérité par exercice)
        -> normalisation Python (groupement des questions a/b/c, numérotation)
        -> rendu Jinja2 (templates/*.tex.j2)
        -> compilation pdflatex (2 passes), sortie dans build/output/
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import load_td, load_cours, niveau_label  # noqa: E402  (source de vérité partagée)

TEMPLATES_DIR = ROOT / "templates"
GEN_DIR = ROOT / "build" / "generated"
OUT_DIR = ROOT / "build" / "output"
MANIFEST_PATH = OUT_DIR / "manifest.json"


def load_manifest():
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

# Rendu Jinja2 (délimiteurs adaptés à LaTeX pour éviter les conflits avec {})
# ----------------------------------------------------------------------

from datetime import datetime

def make_env():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["niveau_label"] = niveau_label
    # Injecter la date et l'heure courantes
    env.globals["now"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    env.filters["texid"] = lambda s: str(s).replace("_", r"\_")
    return env


def load_matiere_meta(matiere_slug: str) -> dict:
    """Charge les métadonnées globales de la matière (_matiere.yaml)."""
    path = ROOT / "data" / "matieres" / matiere_slug / "_matiere.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}

def render_target(env, target: dict, config: dict):
    """Un target peut être de type 'td'/'tp' (exercices) ou 'cours' (sections
    de lecture) -- voir data/SCHEMA.md. Le champ `doc` remplace l'ancien `td`."""
    
    type_doc = target.get("type_doc", "td")
    matiere = target["matiere"]
    doc_slug = target.get("doc", target.get("td"))

    # 1. Chargement des métadonnées de la matière (_matiere.yaml)
    matiere_meta = load_matiere_meta(matiere)

    # 2. Résolution du profil auteur depuis config.yaml (ou constante globale PROFILS)
    # Récupère les profils dans config.yaml ou retombe sur la variable globale PROFILS
    profils = config.get("profils", PROFILS if "PROFILS" in globals() else {})
    
    # Établissement de la cible (chaîne de caractères, ex: "IPSA")
    etablissement = target.get("etablissement", "DEFAULT")
    
    # Récupération du profil correspondant ou fallback sur DEFAULT puis dictionnaire vide
    profil_base = profils.get(etablissement, profils.get("DEFAULT", {}))

    # Gestion de la surcharge ponctuelle 'auteur' dans la target
    auteur_target = target.get("auteur", {})
    if isinstance(auteur_target, str):
        auteur_target = {"nom": auteur_target}
    elif not isinstance(auteur_target, dict):
        auteur_target = {}

    # Fusion : profil de base + surcharges explicites de la cible
    auteur_final = {**profil_base, **auteur_target}

    # 3. Chargement du document (cours ou TD) et rendu Jinja2
    if type_doc == "cours":
        cours = load_cours(matiere, doc_slug)
        tmpl = env.get_template("cours.tex.j2")
        return tmpl.render(
            titre_document=target["titre"],
            cours=cours,
            opts=target,
            matiere_meta=matiere_meta,
            auteur=auteur_final,
        )

    meta, exercices = load_td(
        matiere, doc_slug, type_doc=type_doc, only_exercices=target.get("exercices")
    )
    tmpl = env.get_template("td.tex.j2")
    return tmpl.render(
        titre_document=target["titre"],
        td=meta,
        exercices=exercices,
        opts=target,
        matiere_meta=matiere_meta,
        auteur=auteur_final,
    )



# ----------------------------------------------------------------------
# Compilation
# ----------------------------------------------------------------------

def compile_pdf(tex_path: Path):
    for _ in range(2):
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory", str(tex_path.parent),
                str(tex_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    pdf_path = tex_path.with_suffix(".pdf")
    if pdf_path.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / pdf_path.name
        shutil.copy(pdf_path, dest)
        return dest
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", help="noms de cibles à générer (défaut : toutes)")
    parser.add_argument("--no-pdf", action="store_true", help="ne pas lancer pdflatex")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "build" / "config.yaml").read_text(encoding="utf-8"))
    targets = config["targets"]
    if args.names:
        targets = [t for t in targets if t["name"] in args.names]

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    env = make_env()
    manifest = load_manifest()

    for target in targets:
        print(f"-> Génération de {target['name']} ...")
        tex = render_target(env, target, config) # <-- Passer config ici
        tex_path = GEN_DIR / f"{target['name']}.tex"
        tex_path.write_text(tex, encoding="utf-8")
        print(f"   .tex écrit : {tex_path}")

        if not args.no_pdf:
            pdf = compile_pdf(tex_path)
            if pdf:
                print(f"   ✅ PDF généré : {pdf}")
                # Manifeste (matiere, type_doc, doc) -> nom de fichier PDF réel,
                # consommé par web/export_markdown.py pour ne JAMAIS avoir à
                # deviner un nom de fichier par convention (bug réel trouvé et
                # corrigé : un document 'cours' dont le nom de cible ne suivait
                # pas la convention <id>_<suffixe> ne recevait aucun lien PDF).
                manifest[target["name"]] = {
                    "matiere": target["matiere"],
                    "type_doc": target.get("type_doc", "td"),
                    "doc": target.get("doc", target.get("td")),
                    "pdf": pdf.name,
                }
            else:
                print(f"   ❌ Échec de compilation pour {target['name']} "
                      f"(voir {tex_path.with_suffix('.log')})")

    if not args.no_pdf:
        save_manifest(manifest)
        print(f"-> Manifeste PDF écrit : {MANIFEST_PATH}")


if __name__ == "__main__":
    sys.exit(main())
