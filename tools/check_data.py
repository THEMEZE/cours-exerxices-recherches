#!/usr/bin/env python3
"""
Contrôle de la « base de données » YAML (data/) AVANT de générer quoi que ce
soit. Code de sortie 1 s'il y a des ERREURS (les avertissements ne bloquent pas).

Vérifie :
  - tous les .yaml se lisent ; _matiere.yaml cohérent avec le nom du dossier
  - quartz_namespace unique (deux matières dans le même dossier Quartz s'écrasent)
  - exercices_ordre <-> fichiers présents ; exercices non listés
  - noms de fichiers non ASCII / en NFD (macOS) : casse sur le Raspberry (Linux)
  - ids de sujets (matière, cours, TD) présents dans data/graph/sujets.yaml
  - liens du graphe : ids connus, poids dans [-1, 1], type parent|associe
  - QCM : `td` et `lie_a` existent dans la même matière
  - cibles de build/config.yaml : source existante
  - figures « ??? » (gabarits non remplis) -> avertissement
Usage : python3 tools/check_data.py
"""
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "build"))
import common_data as cd  # noqa: E402
import pdf_status  # noqa: E402

errors, warnings = [], []
err = lambda m: errors.append(m)
warn = lambda m: warnings.append(m)


def load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        err(f"YAML illisible : {p.relative_to(ROOT)} -- {str(e).splitlines()[0]}")
        return None


def main():
    # 0) Syntaxe de TOUS les YAML d'abord : une erreur ici empêcherait le reste du contrôle
    #    (et tous les exports) -- on liste tous les fichiers fautifs d'un coup.
    broken = []
    for p in sorted(cd.DATA_DIR.rglob("*.yaml")):
        rel = p.relative_to(cd.DATA_DIR).parts
        # on ignore les dossiers brouillon (« xxx copie », cachés) mais PAS _meta.yaml / _matiere.yaml
        if any(cd.is_ignored_name(part) for part in rel[:-1]) or " copie" in rel[-1].lower() or rel[-1].startswith("."):
            continue
        try:
            cd.read_yaml(p)
        except ValueError as e:
            broken.append(str(e))
    if (ROOT / "build" / "config.yaml").exists():
        try:
            cd.read_yaml(ROOT / "build" / "config.yaml")
        except ValueError as e:
            broken.append(str(e))
    if broken:
        for b in broken:
            print("❌", b)
        print(f"\n{len(broken)} fichier(s) YAML illisible(s) : corrige-les, puis relance.")
        return 1

    sujets, liens = cd.load_sujets_graph()

    # --- fichiers : syntaxe + noms + gabarits ---
    for p in sorted(cd.DATA_DIR.rglob("*")):
        rel = p.relative_to(ROOT)
        if any(cd.is_ignored_name(part) for part in p.relative_to(cd.DATA_DIR).parts[:-1]):
            continue
        if p.name != unicodedata.normalize("NFC", p.name).encode("ascii", "ignore").decode() and not p.name.isascii():
            if unicodedata.normalize("NFC", p.name) != p.name:
                err(f"nom de fichier en NFD (macOS) : {rel} -- introuvable sur Linux")
            else:
                warn(f"nom de fichier non ASCII : {rel} (préférer ASCII pour le Raspberry)")
        if p.suffix == ".yaml" and not cd.is_ignored_name(p.name):
            d = load(p)
            if d is not None and "???" in p.read_text(encoding="utf-8"):
                warn(f"gabarit non rempli (« ??? ») : {rel}")

    # --- matières ---
    ns_seen = {}
    for m in cd.list_matieres():
        mp = cd.DATA_DIR / m / "_matiere.yaml"
        raw = load(mp) if mp.exists() else None
        if not mp.exists():
            warn(f"{m} : pas de _matiere.yaml (valeurs par défaut utilisées)")
        elif raw and raw.get("id") != m:
            err(f"{m}/_matiere.yaml : id « {raw.get('id')} » ≠ nom du dossier « {m} » (copier-coller ?)")
        meta = cd.load_matiere_meta(m)
        ns = meta["quartz_namespace"]
        if ns in ns_seen:
            err(f"quartz_namespace « {ns} » partagé par {ns_seen[ns]} et {m} : leurs pages s'écrasent")
        ns_seen[ns] = m
        for s in (raw or {}).get("sujets", []) or []:
            if s not in sujets:
                err(f"{m} : sujet « {s} » absent de data/graph/sujets.yaml")

        # TD / TP
        for ty in ("td", "tp"):
            tdir = cd.DATA_DIR / m / ty
            if not tdir.is_dir():
                continue
            for d in sorted(tdir.iterdir()):
                if d.is_dir() and cd.is_ignored_name(d.name):
                    warn(f"{d.relative_to(ROOT)} : ignoré (copie/brouillon) -- supprime-le ou garde-le, il n'est pas publié")
            for doc in cd.list_docs_td_like(m, ty):
                d = tdir / doc
                meta_d = load(d / "_meta.yaml") or {}
                order = meta_d.get("exercices_ordre", []) or []
                for ex in order:
                    if not cd.resolve_child(d, f"{ex}.yaml").exists():
                        err(f"{m}/{ty}/{doc} : exercice listé mais fichier absent : {ex}.yaml")
                present = {f.stem for f in d.glob("*.yaml") if not f.name.startswith("_")}
                for ex in sorted(present - set(order)):
                    if not cd.is_ignored_name(ex):
                        warn(f"{m}/{ty}/{doc} : {ex}.yaml n'est pas dans exercices_ordre (non publié)")
                for s in meta_d.get("sujets", []) or []:
                    if s not in sujets:
                        err(f"{m}/{ty}/{doc} : sujet « {s} » inconnu")
        for doc in cd.list_docs_cours(m):
            c = load(cd.DATA_DIR / m / "cours" / f"{doc}.yaml") or {}
            for s in c.get("sujets", []) or []:
                if s not in sujets:
                    err(f"{m}/cours/{doc} : sujet « {s} » inconnu")

        # QCM
        ids = {}
        for ty in ("td", "tp"):
            for doc in cd.list_docs_td_like(m, ty):
                mt, exs = cd.load_td(m, doc, type_doc=ty)
                ids[mt["id"]] = {f"{mt['id']}_ex{e['numero']}" for e in exs}
        for q in cd.load_all_qcm(m):
            if q.get("td") not in ids:
                warn(f"QCM {q.get('id')} ({m}) : td « {q.get('td')} » inexistant dans cette matière")
            if q.get("lie_a") and q["lie_a"] not in ids.get(q.get("td"), set()):
                warn(f"QCM {q.get('id')} ({m}) : lie_a « {q['lie_a']} » inexistant dans le td « {q.get('td')} »")

    # --- graphe ---
    for l in liens:
        for k in ("de", "a"):
            if l[k] not in sujets:
                err(f"graphe : sujet inconnu « {l[k]} » dans un lien {l['de']} -> {l['a']}")
        if l.get("type") not in ("parent", "associe"):
            err(f"graphe : type « {l.get('type')} » invalide ({l['de']} -> {l['a']})")
        if not -1 <= l.get("poids", 0) <= 1:
            err(f"graphe : poids {l.get('poids')} hors [-1, 1] ({l['de']} -> {l['a']})")
    linked = {l[k] for l in liens for k in ("de", "a")}
    for s in sujets:
        if s not in linked:
            warn(f"graphe : le sujet « {s} » n'a aucun lien (nœud isolé)")

    # --- publication: (profil par cours / TP / TD / exercice) + couleur de l'anglais ---
    profiles = cd.load_visibility_profiles()
    pub = cd.publication_config()

    def check_profile(name, where):
        if name not in profiles:
            err(f"config.yaml publication : profil « {name} » inconnu ({where}) -- profils : {', '.join(profiles)}")

    check_profile(pub.get("defaut", "avant_seance"), "defaut")
    for m, mcfg in (pub.get("matieres") or {}).items():
        if m not in cd.list_matieres():
            err(f"config.yaml publication : matière « {m} » inexistante dans data/matieres/")
            continue
        if mcfg.get("defaut"):
            check_profile(mcfg["defaut"], f"{m}.defaut")
        for ty in ("cours", "td", "tp"):
            docs = cd.list_docs_cours(m) if ty == "cours" else cd.list_docs_td_like(m, ty)
            for doc, entry in (mcfg.get(ty) or {}).items():
                if doc not in docs:
                    err(f"config.yaml publication : {m}/{ty}/{doc} n'existe pas")
                    continue
                prof = entry if isinstance(entry, str) else (entry or {}).get("profil")
                if prof:
                    check_profile(prof, f"{m}/{ty}/{doc}")
                if isinstance(entry, dict) and entry.get("exercices"):
                    _, exs = cd.load_td(m, doc, type_doc=ty)
                    slugs = {e["slug"] for e in exs}
                    for ex_slug, ex_prof in entry["exercices"].items():
                        if ex_slug not in slugs:
                            err(f"config.yaml publication : exercice « {ex_slug} » absent de {m}/{ty}/{doc}")
                        check_profile(ex_prof, f"{m}/{ty}/{doc}/{ex_slug}")
            for doc in docs:
                if doc not in (mcfg.get(ty) or {}):
                    warn(f"config.yaml publication : {m}/{ty}/{doc} non listé -> profil par défaut « {cd.resolve_profile(m, ty, doc)} »")
    if not (cd.load_build_config().get("couleurs") or {}).get("anglais"):
        warn("config.yaml : couleurs.anglais absent -> #1565C0 par défaut")

    # --- cibles PDF ---
    rows, orphans = pdf_status.compute(include_templates=False)
    for r in rows:
        if r["state"] == "cible_cassee":
            err(f"config.yaml : cible {r['name']} -> source introuvable ({r['matiere']}/{r['type_doc']}/{r['doc']})")
    for n in pdf_status.solution_leaks():
        warn(f"config.yaml : « {n} » est un énoncé/aide mais a show_solution/show_correction à true -- "
             f"les solutions seront dans le PDF publié (voulu ?)")
    names = [r["name"] for r in rows]
    for n in {x for x in names if names.count(x) > 1}:
        err(f"config.yaml : nom de cible en double : {n}")

    for w in warnings:
        print("⚠️ ", w)
    for e in errors:
        print("❌", e)
    print(f"\n{len(errors)} erreur(s), {len(warnings)} avertissement(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
