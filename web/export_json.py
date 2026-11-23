#!/usr/bin/env python3
"""
Exporte les documents td-like (td/, tp/) en JSON, en appliquant un PROFIL DE
VISIBILITÉ (même logique que build/config.yaml pour les PDF).

NB : cet export JSON (site interactif / carrousel) ne couvre pour l'instant
que les documents td-like (exercices+corrections). Les documents "cours"
(sections de lecture) sont exportés en Markdown Quartz uniquement (voir
web/export_markdown.py) -- à étendre ici si un jour tu veux aussi un
carrousel/JSON pour les cours.

Usage :
    python3 web/export_json.py --profile avant_seance --matiere physique-ondes-ipsa
    python3 web/export_json.py --profile corrige_complet
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    list_matieres, list_docs_td_like, load_td, load_all_qcm, exercise_types, expand_profile,
    apply_visibility_to_exercice, enrich_media_paths, clean_exercice_for_web,
    title_parts, en_color_css, resolve_profile,
)

PROFILES_FILE = ROOT / "web" / "visibility_profiles.yaml"
OUT_ROOT = ROOT / "web" / "public" / "data"


def load_profiles():
    return yaml.safe_load(PROFILES_FILE.read_text(encoding="utf-8"))["profiles"]


def _titles(obj: dict, key: str, key_en: str):
    """Remplace obj[key] (avec {\\color{colorEN}...}) par le français seul + obj[key_en] (anglais)."""
    fr, en = title_parts(obj.get(key, ""))
    obj[key] = fr
    if en:
        obj[key_en] = en


def export_profile(profile_name: str, profiles: dict, forced, matiere_filter: str = None):
    """`forced` = un nom de profil imposé à tous les documents, ou None (= « auto » :
    profil de chaque document/exercice d'après publication: dans build/config.yaml)."""
    out_dir = OUT_ROOT / profile_name
    out_dir.mkdir(parents=True, exist_ok=True)

    matieres = [matiere_filter] if matiere_filter else list_matieres()
    index = []
    td_ids = []

    for matiere in matieres:
        for type_doc in exercise_types():
            for doc_slug in list_docs_td_like(matiere, type_doc):
                meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
                td_ids.append(meta["id"])
                pname = resolve_profile(matiere, type_doc, doc_slug, forced=forced)
                filtered = []
                for ex in exercices:
                    ex_opts = profiles[resolve_profile(matiere, type_doc, doc_slug, ex_slug=ex["slug"], forced=forced)]
                    f = clean_exercice_for_web(apply_visibility_to_exercice(enrich_media_paths(ex), ex_opts))
                    _titles(f, "intitule", "intitule_en")
                    filtered.append(f)
                head = {"id": meta["id"], "matiere": matiere, "type_doc": type_doc, "profil": pname,
                        "titre": meta["titre"], "chapitre_cours": meta["chapitre_cours"], "seance": meta.get("seance")}
                _titles(head, "titre", "titre_en")
                _titles(head, "chapitre_cours", "chapitre_cours_en")
                head["couleur_anglais"] = en_color_css()
                doc_json = {**head, "exercices": filtered}
                out_name = f"{matiere}__{meta['id']}.json"
                (out_dir / out_name).write_text(
                    json.dumps(doc_json, ensure_ascii=False, indent=2), encoding="utf-8")
                index.append({**head, "n_exercices": len(filtered)})
                print(f"   -> {profile_name}/{out_name} ({len(filtered)} exercices) [profil : {pname}]")

    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    all_qcm = load_all_qcm(matiere_filter)
    qcm = [q for q in all_qcm if q.get("td") in td_ids] if matiere_filter else all_qcm
    (out_dir / "qcm.json").write_text(
        json.dumps(qcm, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   -> {profile_name}/qcm.json ({len(qcm)} QCM)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", default=None,
                   help="profil de web/visibility_profiles.yaml (forcé partout), ou « auto » (profil de chaque "
                        "document d'après build/config.yaml). Défaut : tous les profils.")
    p.add_argument("--matiere", default=None, help="ne traiter qu'une matière (ex: physique-ondes-ipsa)")
    args = p.parse_args()

    profiles = load_profiles()
    names = [args.profile] if args.profile else list(profiles.keys())

    for name in names:
        name = expand_profile(name)                      # « termine » -> corrige_complet (config.yaml > publication > etats)
        if name != "auto" and name not in profiles:
            print(f"!! profil inconnu : {name} (disponibles : auto, {', '.join(profiles)})")
            continue
        print(f"-- Profil '{name}'")
        export_profile(name, profiles, None if name == "auto" else name, args.matiere)


if __name__ == "__main__":
    main()
