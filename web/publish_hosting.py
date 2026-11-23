#!/usr/bin/env python3
"""
Prépare ce que nginx HÉBERGE, dans build/public/ (rien n'est servi directement
depuis build/output/ -- c'est un dossier de travail) :

    build/public/
        pdfs/<nom>.pdf        PDF publiés (lien en dur vers build/output/, pas de copie)
        pdfs/index.html|json  liste « fait / périmé / à venir », par matière
        qcm/index.html        sommaire des QCM
        qcm/<matiere>/index.html   l'appli QCM de chaque matière (build/output/qcm_app_<matiere>.html)
        graph.json            graphe des sujets (nœuds + arêtes pondérées) pour une vue D3 éventuelle

Ce que ça apporte par rapport à « nginx sert build/output/*.pdf » :
  1. Le code regarde ce qui est FAIT ou DÉFAIT : seuls les PDF réellement
     présents sont publiés ; un PDF dont la cible a été retirée de config.yaml,
     ou supprimé du disque, disparaît de l'hébergement à la synchronisation.
  2. Le profil de visibilité s'applique aux PDF (voir `pdf_publies` dans
     web/visibility_profiles.yaml) : en `avant_seance`, aucun corrigé en ligne.
  3. Les pages QCM de chaque matière ont leur URL (/qcm/<matiere>/).

Usage :
    python3 web/publish_hosting.py --profile avant_seance
"""
import argparse
import html
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "build"))
import pdf_status  # noqa: E402
from common_data import (  # noqa: E402
    expand_profile,
    list_matieres, load_matiere_meta, load_sujets_graph, resolve_profile, load_visibility_profiles,
    title_parts, en_color_css,
)
from web.build_qcm_artifact import resolved_theme  # noqa: E402
from web import fichiers_joints  # noqa: E402  (fichiers rattachés : build/config.yaml > fichiers)

OUT_DIR = ROOT / "build" / "output"
PUBLIC_DIR = ROOT / "build" / "public"
PROFILES_FILE = ROOT / "web" / "visibility_profiles.yaml"

KIND_LABEL = {"enonce": "Énoncé", "aides": "Aides", "corrige": "Corrigé", "fiche": "Fiche enseignant", "autre": "PDF"}
KIND_ORDER = ["enonce", "aides", "corrige", "autre", "fiche"]

CSS = """
:root{--bg:#fafaf7;--fg:#1d2328;--mut:#6b7780;--card:#fff;--line:#e3e6e8;--ok:#2e7d62;--warn:#b7791f;--todo:#8a96a0}
@media(prefers-color-scheme:dark){:root{--bg:#161a1d;--fg:#e8ecee;--mut:#98a4ad;--card:#1f2428;--line:#2d343a;--ok:#5fc4a0;--warn:#e0b04a;--todo:#7b8791}}
body{font:16px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:820px;margin:0 auto;padding:1.5rem 1rem 4rem}
h1{font-size:1.5rem}h2{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:.3rem}
ul{list-style:none;padding:0}li{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:.4rem 0;padding:.6rem .9rem;display:flex;gap:.6rem;align-items:baseline;flex-wrap:wrap}
a{color:inherit}.tag{font-size:.75rem;border:1px solid var(--line);border-radius:99px;padding:0 .5rem;color:var(--mut)}
.ok{color:var(--ok)}.warn{color:var(--warn)}.todo{color:var(--todo)}.sz{margin-left:auto;color:var(--mut);font-size:.8rem}
"""


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{CSS}</style></head><body><h1>{html.escape(title)}</h1>{body}</body></html>')


def fmt_size(n):
    if not n:
        return ""
    return f"{n / 1024 / 1024:.1f} Mo" if n >= 1024 * 1024 else f"{n / 1024:.0f} Ko"


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------

def link_or_copy(src: Path, dst: Path):
    if dst.exists():
        try:
            if os.path.samefile(src, dst):
                return
        except OSError:
            pass
        dst.unlink()
    try:
        os.link(src, dst)           # lien en dur : pas de doublon de 40 Mo
    except OSError:
        shutil.copy2(src, dst)      # autre système de fichiers


def title_html(raw: str) -> str:
    fr, en = title_parts(raw)
    return html.escape(fr) + (f' <span style="color:{en_color_css()}">{html.escape(en)}</span>' if en else "")


def sync_pdfs(rows: list, profiles: dict, forced):
    """Les types de PDF publiés dépendent du PROFIL DU DOCUMENT (publication: dans
    build/config.yaml) -- ou du profil forcé en ligne de commande."""
    def allowed_for(r):
        pname = resolve_profile(r["matiere"], r["type_doc"], r["doc"], forced=forced)
        return set(profiles[pname].get("pdf_publies", ["enonce"]))

    pdf_dir = PUBLIC_DIR / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    wanted = {}
    for r in rows:
        if r["pdf_exists"] and r["state"] != "cible_cassee" and pdf_status.is_published(r, allowed_for(r)):
            wanted[r["pdf"]] = r

    # PDF construits RATTACHÉS à un autre document (build/config.yaml > fichiers > cible:) : hébergés
    # aussi, sous la même règle de profil que leur lien (jamais un corrigé en avant_seance).
    statics, pdf_targets, conflicts = fichiers_joints.hosting_needs(forced, profiles)
    by_name = {r["name"]: r for r in rows}
    for cible, allowed in pdf_targets:
        r = by_name.get(cible)
        if r and r["pdf_exists"] and r["state"] != "cible_cassee" and pdf_status.is_published(r, allowed):
            wanted[r["pdf"]] = r

    removed = []
    for f in pdf_dir.glob("*.pdf"):
        if f.name not in wanted:
            f.unlink()
            removed.append(f.name)
    for name in wanted:
        link_or_copy(OUT_DIR / name, pdf_dir / name)

    # Fichiers STATIQUES rattachés (xlsx, csv, zip...) : copiés ici (/pdfs/<nom>) ; ceux qui ne sont plus
    # rattachés / visibles disparaissent (registre .fichiers.json : on ne supprime jamais que nos fichiers).
    reg_path = pdf_dir / ".fichiers.json"
    try:
        previous = set(json.loads(reg_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        previous = set()
    for name in sorted(previous - set(statics)):
        if (pdf_dir / name).is_file() and not name.endswith(".pdf"):
            (pdf_dir / name).unlink()
            removed.append(name)
    for name, src in statics.items():
        link_or_copy(src, pdf_dir / name)
    reg_path.write_text(json.dumps(sorted(statics), ensure_ascii=False), encoding="utf-8")
    for name in conflicts:
        print(f"   ⚠️  deux fichiers rattachés s'appellent « {name} » : un seul est hébergé (renomme l'un des deux)")

    # À venir = cible de type autorisé par le profil mais PDF pas encore fait
    todo = [r for r in rows if not r["pdf_exists"] and r["state"] == "manquant" and pdf_status.is_published(r, allowed_for(r))]

    index = {
        "published": [
            {k: r[k] for k in ("name", "titre", "matiere", "doc", "kind", "state", "size", "pdf")}
            for r in wanted.values()
        ],
        "a_venir": [{k: r[k] for k in ("name", "titre", "matiere", "doc", "kind")} for r in todo],
        "fichiers": sorted(statics),
    }
    (pdf_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    by_matiere = {}
    for r in list(wanted.values()) + todo:
        by_matiere.setdefault(r["matiere"], []).append(r)
    body = []
    for m in sorted(by_matiere):
        meta = load_matiere_meta(m)
        body.append(f'<h2>{html.escape(meta["nom"])}</h2><ul>')
        items = sorted(by_matiere[m], key=lambda r: (r["doc"] or "", KIND_ORDER.index(r["kind"]) if r["kind"] in KIND_ORDER else 9))
        for r in items:
            tag = f'<span class="tag">{KIND_LABEL.get(r["kind"], r["kind"])}</span>'
            if r["pdf_exists"]:
                st = '<span class="warn" title="Les sources ont changé depuis la dernière compilation">🟠 mise à jour en cours</span>' if r["state"] == "perime" else ""
                body.append(f'<li>{tag}<a href="{html.escape(r["pdf"])}" target="_blank" rel="noopener">{title_html(r["titre"])}</a>{st}'
                            f'<span class="sz">{fmt_size(r["size"])}</span></li>')
            else:
                body.append(f'<li>{tag}<span class="todo">{title_html(r["titre"])} — ⬜ à venir</span></li>')
        body.append("</ul>")
    (pdf_dir / "index.html").write_text(page("PDF", "".join(body) or "<p>Aucun PDF publié pour l'instant.</p>"), encoding="utf-8")
    return wanted, todo, removed, statics


# ----------------------------------------------------------------------
# QCM
# ----------------------------------------------------------------------

def sync_qcm():
    qcm_root = PUBLIC_DIR / "qcm"
    qcm_root.mkdir(parents=True, exist_ok=True)
    present = {}
    for f in sorted(OUT_DIR.glob("qcm_app_*.html")):
        slug = f.stem[len("qcm_app_"):]
        if slug in list_matieres():
            present[slug] = f
    # retire les QCM dont la matière n'existe plus / n'a plus de QCM
    for d in qcm_root.iterdir():
        if d.is_dir() and d.name not in present:
            shutil.rmtree(d)
    for slug, f in present.items():
        d = qcm_root / slug
        d.mkdir(exist_ok=True)
        shutil.copy2(f, d / "index.html")
    items = []
    for slug in sorted(present):
        th = resolved_theme(slug)
        items.append(f'<li><a href="{slug}/">{html.escape(th["titre_app"])}</a>'
                     f'<span class="sz">{html.escape(th["sous_titre_app"])}</span></li>')
    (qcm_root / "index.html").write_text(
        page("QCM en direct", "<ul>" + "".join(items) + "</ul>" if items else "<p>Aucun QCM.</p>"), encoding="utf-8")
    return sorted(present)


# ----------------------------------------------------------------------
# Graphe des sujets (pondéré) pour une vue personnalisée
# ----------------------------------------------------------------------

def write_graph_json():
    sujets, liens = load_sujets_graph()
    matieres_par_sujet = {}
    for m in list_matieres():
        for s in load_matiere_meta(m)["sujets"]:
            matieres_par_sujet.setdefault(s, []).append(m)
    nodes = [{"id": s["id"], "nom": s["nom"], "page": s["quartz_path"],
              "matieres": matieres_par_sujet.get(s["id"], [])} for s in sujets.values()]
    edges = [{"source": l["de"], "target": l["a"], "poids": l.get("poids", 0), "type": l.get("type"),
              "note": l.get("note", "")} for l in liens if l["de"] in sujets and l["a"] in sujets]
    (PUBLIC_DIR / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(nodes), len(edges)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()

    profiles = load_visibility_profiles()
    forced = None if args.profile == "auto" else expand_profile(args.profile)
    if forced and forced not in profiles:
        print(f"!! profil inconnu : {args.profile} (disponibles : auto, {', '.join(profiles)})")
        return 1

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    _, status = pdf_status.reconcile()           # réécrit manifest.json d'après le disque
    c = status["counts"]
    print(f"-- PDF : {c['ok']} à jour · {c['present_sans_empreinte']} sans empreinte · {c['perime']} périmés · "
          f"{c['manquant']} à faire · {c['cible_cassee']} cassés")
    if status["orphans"]:
        print(f"   ℹ️  {len(status['orphans'])} PDF sans cible dans config.yaml (non publiés) : {', '.join(status['orphans'])}")

    for n in pdf_status.solution_leaks():
        if f"{n}.pdf" in {r["pdf"] for r in status["targets"] if r["pdf_exists"]}:
            print(f"   ⚠️  {n} est un énoncé/aide avec show_solution/show_correction=true : "
                  f"les solutions sont dans ce PDF (config.yaml)")
    wanted, todo, removed, statics = sync_pdfs(status["targets"], profiles, forced)
    print(f"-- Hébergement PDF (profil '{args.profile}'" + (" : par document" if not forced else "") + ") : "
          f"{len(wanted)} publié(s), {len(todo)} à venir, {len(removed)} retiré(s) ; "
          f"{len(statics)} fichier(s) rattaché(s) ({', '.join(statics) or 'aucun'})")
    for n in removed:
        print(f"   🗑️  retiré de l'hébergement : {n}")

    qcms = sync_qcm()
    print(f"-- Hébergement QCM : {len(qcms)} appli(s) -> /qcm/<matiere>/ ({', '.join(qcms) or 'aucune'})")

    n, e = write_graph_json()
    print(f"-- graph.json : {n} sujets, {e} liens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
