#!/usr/bin/env python3
"""
Vérifie les liens de ce qui est HÉBERGÉ, à lancer après web/publish_profile.sh :

  - [[wikilinks]] des .md de Quartz (=> les arêtes du graphe) : la page cible existe ?
  - /pdfs/*.pdf   : le PDF est bien publié dans build/public/pdfs/ ?
  - /qcm/<m>/     : l'appli QCM existe dans build/public/qcm/ ?
  - /figures/, /animations/ : le média existe (si les dossiers de rendu sont présents) ?

Affiche aussi les pages ORPHELINES (aucun lien entrant) : ce sont les nœuds
isolés du graphe Quartz.

Usage :
    python3 tools/check_quartz_links.py --quartz-content ../Quartz5/content
Code de sortie 1 s'il y a des liens cassés (utilisable dans un script / cron).
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = re.compile(r"\[\[([^\]|#]+)(#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MDLINK = re.compile(r"(?:\]\(|(?:href|src)=\")(/(?:pdfs|qcm|figures|animations)/[^)\s\"]*)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quartz-content", default=str(ROOT.parent / "Quartz5" / "content"),
                    help="défaut : ../Quartz5/content")
    ap.add_argument("--max", type=int, default=25, help="nb max de lignes affichées par catégorie")
    args = ap.parse_args()
    content = Path(args.quartz_content).expanduser().resolve()
    if not content.is_dir():
        print(f"dossier introuvable : {content}")
        return 2

    pages = {}
    for f in content.rglob("*.md"):
        rel = f.relative_to(content).with_suffix("")
        slug = str(rel.parent) if rel.name == "index" and rel.parent != Path(".") else str(rel)
        pages[slug] = f
    slugs = set(pages)
    by_tail = defaultdict(set)
    for s in slugs:
        by_tail[s.rsplit("/", 1)[-1]].add(s)

    def resolve(target: str):
        t = target.strip().strip("/")
        if t.endswith("/index"):
            t = t[: -len("/index")]
        if t in slugs:
            return t
        if "/" not in t and t in by_tail and len(by_tail[t]) == 1:   # lien « court » à la Obsidian
            return next(iter(by_tail[t]))
        for s in slugs:
            if s.endswith("/" + t):
                return s
        return None

    pdf_dir, qcm_dir = ROOT / "build" / "public" / "pdfs", ROOT / "build" / "public" / "qcm"
    fig_dir, anim_dir = ROOT / "web" / "public" / "figures", ROOT / "animations" / "outputs"
    broken = defaultdict(list)
    incoming = defaultdict(int)
    n_wiki = 0
    for slug, f in pages.items():
        text = f.read_text(encoding="utf-8")
        for m in WIKI.finditer(text):
            n_wiki += 1
            tgt = resolve(m.group(1))
            if tgt is None:
                broken["wikilinks"].append(f"{slug}  ->  [[{m.group(1)}]]")
            elif tgt != slug:
                incoming[tgt] += 1
        for url in sorted(set(m.group(1) for m in MDLINK.finditer(text))):
            if url.startswith("/pdfs/") and pdf_dir.is_dir() and not (pdf_dir / url[len("/pdfs/"):]).exists():
                broken["pdf non publié / absent"].append(f"{slug}  ->  {url}")
            elif url.startswith("/qcm/") and qcm_dir.is_dir():
                parts = [p for p in url.split("/") if p]
                if len(parts) > 1 and not (qcm_dir / parts[1] / "index.html").exists():
                    broken["qcm"].append(f"{slug}  ->  {url}")
            elif url.startswith("/figures/") and fig_dir.is_dir() and any(fig_dir.iterdir()) and not (fig_dir / url[len("/figures/"):]).exists():
                broken["figure"].append(f"{slug}  ->  {url}")
            elif url.startswith("/animations/") and anim_dir.is_dir() and any(anim_dir.iterdir()) and not (anim_dir / url[len("/animations/"):]).exists():
                broken["animation"].append(f"{slug}  ->  {url}")

    orphans = sorted(s for s in slugs if incoming[s] == 0 and s != "index")
    print(f"{len(pages)} pages, {n_wiki} wikilinks, {sum(incoming.values())} arêtes internes")
    for k, v in broken.items():
        print(f"\n❌ {k} : {len(v)}")
        for line in v[: args.max]:
            print("   ", line)
        if len(v) > args.max:
            print(f"    ... (+{len(v) - args.max})")
    if orphans:
        print(f"\n🟡 {len(orphans)} page(s) sans lien entrant (nœuds isolés du graphe)")
        for s in orphans[: args.max]:
            print("   ", s)
    if not broken:
        print("\n✅ aucun lien cassé")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
