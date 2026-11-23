#!/usr/bin/env python3
"""
État « fait / défait » des PDF : compare ce que DEMANDE build/config.yaml, ce
que contiennent les sources (data/**/*.yaml + templates) et ce qui EXISTE
réellement dans build/output/.

États d'une cible :
    ok                      PDF présent, construit avec les sources actuelles
    perime                  PDF présent mais les sources ont changé depuis
    present_sans_empreinte  PDF présent, construit avant ce système (inconnu)
    manquant                aucun PDF : « à faire »
    cible_cassee            la source (matière/document YAML) n'existe pas

Plus : les « orphelins » = PDF dans build/output/ qu'aucune cible ne produit.

Le manifeste (build/output/manifest.json) est RECONSTRUIT d'après la réalité
à chaque appel de `reconcile()` -- il ne garde jamais une entrée dont le PDF a
disparu ou dont la cible a été retirée de config.yaml (c'était le cas avant :
11 entrées périmées, 7 pointant vers des PDF absents).

Usage :
    python3 build/pdf_status.py                # tableau lisible
    python3 build/pdf_status.py --write        # + réécrit manifest.json et status.json
    python3 build/pdf_status.py --todo         # noms à (re)construire, séparés par des espaces
    python3 build/pdf_status.py --json
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import DATA_DIR, resolve_child, apply_visibility_to_target  # noqa: E402
import qcm_data  # noqa: E402  (cibles type_doc: qcm)

OUT_DIR = ROOT / "build" / "output"
MANIFEST_PATH = OUT_DIR / "manifest.json"
STATUS_PATH = OUT_DIR / "status.json"
CONFIG_PATH = ROOT / "build" / "config.yaml"
TEMPLATES_DIR = ROOT / "templates"

KIND_RE = re.compile(r"_(enonces?|aides?|corrige|fiche)$")


def kind_of(name: str) -> str:
    """enonce | aides | corrige | fiche | autre (d'après le suffixe du nom de cible)."""
    m = KIND_RE.search(name)
    if not m:
        return "autre"
    k = m.group(1)
    return {"enonces": "enonce", "aide": "aides"}.get(k, k)


KIND_ORDER = ["enonce", "aides", "corrige", "autre", "fiche"]


def is_published(entry: dict, allowed_kinds) -> bool:
    """Un PDF est publiable si `publier: true` dans sa cible, ou (sans
    `publier`) si son type figure dans `pdf_publies` du profil actif.
    `publier: false` l'exclut toujours. Marche sur une ligne de compute()
    comme sur une entrée de manifest.json."""
    if entry.get("publier") is True:
        return True
    if entry.get("publier") is False:
        return False
    return entry.get("kind") in set(allowed_kinds)


def solution_leaks(config: dict = None) -> list:
    """Cibles de type énoncé/aides dont les options affichent correction ou
    solution (probable copier-coller depuis une cible « corrigé »)."""
    config = config or load_config()
    merged = [apply_visibility_to_target(t) for t in config.get("targets", [])]      # tient compte de `visibilite:`
    return [t["name"] for t in merged
            if kind_of(t["name"]) in ("enonce", "aides")
            and (t.get("show_solution") or t.get("show_correction"))]


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------
# Sources d'une cible
# ----------------------------------------------------------------------

def _doc_sources(target: dict):
    """Fichiers de données dont dépend le PDF de cette cible (ou None si cassé)."""
    matiere = target["matiere"]
    type_doc = target.get("type_doc", "td")
    doc = target.get("doc", target.get("td"))
    mdir = DATA_DIR / matiere
    if not mdir.is_dir():
        return None
    files = []
    if (mdir / "_matiere.yaml").exists():
        files.append(mdir / "_matiere.yaml")
    if type_doc == "qcm":
        # un chapitre = un fichier data/matieres/<m>/qcm/<chapitre>.yaml ; « all » = toute la matière
        qfiles = qcm_data.qcm_doc_files(matiere, doc)
        return files + qfiles if qfiles else None
    tdir = mdir / type_doc
    if type_doc == "cours":
        f = resolve_child(tdir, f"{doc}.yaml")
        if not f.exists():
            return None
        files.append(f)
    else:
        d = resolve_child(tdir, doc)
        if not (d / "_meta.yaml").exists():
            return None
        files.extend(sorted(d.glob("*.yaml")))
    return files


def source_hash(target: dict, config: dict, include_templates: bool = True):
    """Empreinte des sources (None si la source n'existe pas)."""
    files = _doc_sources(target)
    if files is None:
        return None
    h = hashlib.sha256()
    # `visibilite:` d'une cible = réglages repris d'un profil (web/visibility_profiles.yaml) : on hache la cible
    # COMPLÈTE, pour qu'un changement de profil rende le PDF « périmé » (sans `visibilite:` : inchangé).
    h.update(json.dumps(apply_visibility_to_target(target), sort_keys=True, default=str).encode())
    # profils auteur (en-têtes de PDF)
    h.update(json.dumps(config.get("profils", {}), sort_keys=True, default=str).encode())
    h.update(json.dumps(config.get("couleurs", {}), sort_keys=True, default=str).encode())   # couleur de l'anglais
    if target.get("type_doc") == "qcm":                                                       # défauts QCM (neutre, libellé…)
        h.update(json.dumps(config.get("qcm", {}), sort_keys=True, default=str).encode())
    if include_templates and TEMPLATES_DIR.exists():
        files = list(files) + sorted(p for p in TEMPLATES_DIR.rglob("*") if p.is_file())
    for f in files:
        h.update(str(f.relative_to(ROOT)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


# ----------------------------------------------------------------------
# Calcul de l'état
# ----------------------------------------------------------------------

def compute(config: dict = None, include_templates: bool = True):
    """Retourne (liste d'états par cible, liste de PDF orphelins)."""
    config = config or load_config()
    manifest = load_manifest()
    rows = []
    for t in config.get("targets", []):
        name = t["name"]
        pdf = OUT_DIR / f"{name}.pdf"
        cur = source_hash(t, config, include_templates)
        prev = manifest.get(name, {})
        built = prev.get("src_hash")
        if cur is None:
            state = "cible_cassee"
        elif not pdf.exists():
            state = "manquant"
        elif not built:
            state = "present_sans_empreinte"
        elif built != cur:
            state = "perime"
        else:
            state = "ok"
        rows.append({
            "name": name,
            "titre": t.get("titre", name),
            "matiere": t["matiere"],
            "type_doc": t.get("type_doc", "td"),
            "doc": t.get("doc", t.get("td")),
            "kind": kind_of(name),
            "publier": t.get("publier"),          # True / False / None (= règle du profil)
            "pdf": pdf.name,
            "state": state,
            "pdf_exists": pdf.exists(),
            "size": pdf.stat().st_size if pdf.exists() else None,
            "mtime": datetime.fromtimestamp(pdf.stat().st_mtime).isoformat(timespec="seconds") if pdf.exists() else None,
            "src_hash": cur,
            "built_hash": built,
        })
    declared = {f"{r['name']}.pdf" for r in rows}
    orphans = sorted(p.name for p in OUT_DIR.glob("*.pdf") if p.name not in declared) if OUT_DIR.exists() else []
    return rows, orphans


def reconcile(config: dict = None, write: bool = True):
    """Reconstruit manifest.json d'après la réalité (jamais d'entrée fantôme)."""
    config = config or load_config()
    rows, orphans = compute(config)
    old = load_manifest()
    manifest = {}
    for r in rows:
        if not r["pdf_exists"]:
            continue
        prev = old.get(r["name"], {})
        manifest[r["name"]] = {
            "matiere": r["matiere"],
            "type_doc": r["type_doc"],
            "doc": r["doc"],
            "pdf": r["pdf"],
            "kind": r["kind"],
            "src_hash": prev.get("src_hash"),
            "built_at": prev.get("built_at"),
            "size": r["size"],
        }
        if r["publier"] is not None:
            manifest[r["name"]]["publier"] = r["publier"]
    status = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {s: sum(1 for r in rows if r["state"] == s)
                   for s in ("ok", "perime", "present_sans_empreinte", "manquant", "cible_cassee")},
        "orphans": orphans,
        "targets": rows,
    }
    if write:
        save_json(MANIFEST_PATH, manifest)
        save_json(STATUS_PATH, status)
    return manifest, status


def record_build(manifest_name: str, target: dict, config: dict) -> None:
    """À appeler juste après une compilation réussie : mémorise l'empreinte."""
    m = load_manifest()
    m[manifest_name] = {
        "matiere": target["matiere"],
        "type_doc": target.get("type_doc", "td"),
        "doc": target.get("doc", target.get("td")),
        "pdf": f"{manifest_name}.pdf",
        "kind": kind_of(manifest_name),
        "src_hash": source_hash(target, config),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "size": (OUT_DIR / f"{manifest_name}.pdf").stat().st_size,
    }
    if target.get("publier") is not None:
        m[manifest_name]["publier"] = target["publier"]
    save_json(MANIFEST_PATH, m)


def todo_names(config: dict = None, include_perime: bool = True, include_unknown: bool = False):
    rows, _ = compute(config)
    wanted = {"manquant"}
    if include_perime:
        wanted.add("perime")
    if include_unknown:
        wanted.add("present_sans_empreinte")
    return [r["name"] for r in rows if r["state"] in wanted]


# ----------------------------------------------------------------------

LABEL = {
    "ok": "✅ à jour",
    "perime": "🟠 périmé",
    "present_sans_empreinte": "🔵 présent (empreinte inconnue)",
    "manquant": "⬜ à faire",
    "cible_cassee": "❌ source introuvable",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="réécrit manifest.json et status.json")
    ap.add_argument("--todo", action="store_true", help="affiche les noms à (re)construire")
    ap.add_argument("--unknown", action="store_true", help="avec --todo : inclure les PDF sans empreinte")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    config = load_config()
    if args.todo:
        print(" ".join(todo_names(config, include_unknown=args.unknown)))
        return 0
    if args.write:
        _, status = reconcile(config, write=True)
        rows, orphans = status["targets"], status["orphans"]
    else:
        rows, orphans = compute(config)
        status = {"counts": {}, "targets": rows, "orphans": orphans}
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    w = max(len(r["name"]) for r in rows)
    for r in rows:
        print(f"{r['name']:<{w}}  {LABEL[r['state']]:<34} {r['matiere']}/{r['doc']}")
    print()
    for s, lab in LABEL.items():
        n = sum(1 for r in rows if r["state"] == s)
        print(f"  {lab:<36} {n}")
    if orphans:
        print(f"\n  PDF sans cible dans config.yaml ({len(orphans)}) : {', '.join(orphans)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
