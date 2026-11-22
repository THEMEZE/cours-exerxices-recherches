#!/usr/bin/env python3
"""
Ajoute à build/config.yaml, SANS toucher à tes cibles ni à rien d'autre :

  - `couleurs:`     couleur de l'anglais (PDF + site)
  - `publication:`  profil de visibilité de chaque cours / TP / TD (liste générée
                    d'après data/matieres/, tout en `avant_seance` au départ)

Sûr à relancer, y compris si tu as déjà écrit ces blocs À LA MAIN : le fichier est
lu comme du YAML, et un bloc dont la clé de premier niveau (`couleurs:` ou
`publication:`) existe déjà n'est JAMAIS réécrit ni complété. Si les deux existent,
le script répond « Rien à ajouter » et ne touche pas au fichier. Les commentaires
et le reste du fichier sont conservés (insertion de texte avant `targets:`).
`--dry-run` affiche ce qui serait ajouté sans écrire.

Les documents créés plus tard dans data/ ne sont PAS ajoutés automatiquement à
`publication:` (ils prennent le profil par défaut). `--complete` se contente de
les LISTER pour que tu les ajoutes à la main où tu veux.

Usage :
    python3 tools/add_config_blocks.py
    python3 tools/add_config_blocks.py --config build/config.yaml --dry-run
"""
import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import common_data as cd  # noqa: E402

COULEURS = '''# =====================================================================
# Couleur de l'ANGLAIS (titres et textes écrits {\\color{blue} ...} dans les YAML)
# Un seul réglage pour les PDF (LaTeX) et pour le site (Quartz).
# Valeur : un hex ("#1565C0") ou un nom de couleur ("blue", "teal").
# `anglais_web` (optionnel) : autre teinte pour le site seulement -- utile si la
# couleur choisie est trop sombre sur le thème sombre de Quartz (ex. "#4A90E2").
# Changer ce réglage rend les PDF « périmés » (build.py --stale les refait).
# =====================================================================
couleurs:
  anglais: "#1565C0"
  # anglais_web: "#4A90E2"

'''

PUB_HEADER = '''# =====================================================================
# Publication : quel PROFIL de visibilité pour chaque cours, TP et TD
# (voir web/visibility_profiles.yaml : avant_seance, pendant_seance_avec_indices,
#  corrige_resultats_seuls, corrige_complet, all)
#
#   ./web/publish_profile.sh auto        -> applique CE bloc, document par document
#   ./web/publish_profile.sh <profil>    -> force UN profil partout (ignore ce bloc)
#
# Exemple d'usage en classe :
#   chapitre terminé        -> corrige_complet   (tout : corrections et solutions)
#   chapitre en cours       -> pendant_seance_avec_indices   (énoncés + aides)
#   pas encore abordé       -> avant_seance      (énoncés seulement)
#
# Le profil d'un document règle À LA FOIS : le contenu des pages Quartz / JSON /
# notebooks (corrections, solutions, coups de pouce) ET les PDF mis en ligne
# (énoncé / aides / corrigé / fiche enseignant, via `pdf_publies` du profil).
#
# Forme courte :   <document>: <profil>
# Forme détaillée (surcharger certains exercices) :
#   <document>:
#     profil: pendant_seance_avec_indices
#     exercices:
#       ex3_equation_ondes: corrige_complet     # cet exercice-là est déjà corrigé en classe
# Un document non listé prend le `defaut` de sa matière, puis le `defaut` global.
# =====================================================================
'''


def doc_title(m, ty, d):
    try:
        raw = cd.load_cours(m, d).get("titre", "") if ty == "cours" else cd.load_td(m, d, type_doc=ty)[0].get("titre", "")
    except Exception:  # noqa: BLE001
        raw = ""
    return cd.title_parts(raw)[0].replace("\n", " ")[:70]


def docs_of(m, ty):
    return cd.list_docs_cours(m) if ty == "cours" else cd.list_docs_td_like(m, ty)


def publication_block() -> str:
    out = [PUB_HEADER + "publication:", "  defaut: avant_seance", "  matieres:"]
    for m in cd.list_matieres():
        out += [f"    {m}:   # {cd.load_matiere_meta(m)['nom']}", "      defaut: avant_seance"]
        for ty in ("cours", "td", "tp"):
            docs = docs_of(m, ty)
            if docs:
                out.append(f"      {ty}:")
                out += [f"        {d}: avant_seance   # {doc_title(m, ty, d)}" for d in docs]
    return "\n".join(out) + "\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "build" / "config.yaml"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--complete", action="store_true", help="LISTE (sans rien modifier) les documents absents de publication:")
    args = ap.parse_args()

    path = Path(args.config)
    text = path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(text) or {}
    done = []

    add = ""
    if "couleurs" not in cfg:
        add += COULEURS
        done.append("couleurs:")
    if "publication" not in cfg:
        add += publication_block()
        done.append("publication: (tous les documents en avant_seance)")
    if add:
        if "\ntargets:" not in text and not text.startswith("targets:"):
            print("!! 'targets:' introuvable dans le fichier : rien modifié.")
            return 1
        text = text.replace("\ntargets:", "\n" + add + "targets:", 1) if "\ntargets:" in text else add + text

    if args.complete and "publication" in cfg:
        pub = cfg["publication"]
        for m in cd.list_matieres():
            mcfg = (pub.get("matieres") or {}).get(m)
            if mcfg is None:
                print(f"   ℹ️  matière {m} absente de publication: -> utilise `defaut` ; ajoute-la à la main si besoin")
                continue
            for ty in ("cours", "td", "tp"):
                missing = [d for d in docs_of(m, ty) if d not in (mcfg.get(ty) or {})]
                if missing:
                    print(f"   ℹ️  {m}/{ty} non listés (profil par défaut) : {', '.join(missing)}")
        print("   (ajoute-les à la main sous la bonne matière si tu veux un profil particulier)")

    if not add:
        print("Rien à ajouter : couleurs: et publication: existent déjà dans", path)
        return 0
    if args.dry_run:
        print(add)
    else:
        path.write_text(text, encoding="utf-8")
    print("Ajouté à", path, ":", "; ".join(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
