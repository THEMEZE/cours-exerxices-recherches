#!/usr/bin/env python3
"""
Copie les médias référencés par les pages Markdown dans le dossier content/ de
Quartz, aux MÊMES adresses que celles écrites dans les .md :

    web/public/figures/     -> content/figures/       (/figures/x.svg)
    animations/outputs/     -> content/animations/    (/animations/x/animation.gif)
    build/public/pdfs/      -> content/pdfs/          (/pdfs/x.pdf, seulement les PDF publiés)

Pourquoi : Quartz publie lui-même les fichiers non-Markdown de content/. Avec
ça, figures et PDF s'affichent aussi avec `npx quartz build --serve`, sans nginx
ni serveur annexe (avant, ils n'existaient qu'à travers nginx / serve_local.py).

C'est un MIROIR : un média disparu de la source disparaît de content/. Seuls ces
trois sous-dossiers sont touchés. Conseil : les ajouter au .gitignore du dépôt
Quartz (ce sont des fichiers générés, parfois lourds).
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm", ".pdf"}

SOURCES = {
    "figures": ROOT / "web" / "public" / "figures",
    "animations": ROOT / "animations" / "outputs",
    "pdfs": ROOT / "build" / "public" / "pdfs",
}


def mirror(src: Path, dst: Path):
    copied = removed = 0
    wanted = set()
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_file() and f.suffix.lower() in EXT and not any(p.startswith(".") for p in f.relative_to(src).parts):
                rel = f.relative_to(src)
                wanted.add(rel)
                target = dst / rel
                if not target.exists() or target.stat().st_size != f.stat().st_size or target.stat().st_mtime < f.stat().st_mtime:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
                    copied += 1
    if dst.is_dir():
        for f in sorted(dst.rglob("*"), reverse=True):
            if f.is_file() and f.relative_to(dst) not in wanted:
                f.unlink()
                removed += 1
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()
        if not any(dst.iterdir()):
            dst.rmdir()
    return len(wanted), copied, removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quartz-content", default=str(ROOT.parent / "Quartz5" / "content"))
    args = ap.parse_args()
    content = Path(args.quartz_content).expanduser().resolve()
    if not content.is_dir():
        print(f"   ⚠️  {content} introuvable -- médias non copiés.")
        return 0
    for name, src in SOURCES.items():
        total, copied, removed = mirror(src, content / name)
        print(f"   {name:<11}: {total} fichier(s) ({copied} copié(s), {removed} retiré(s))"
              + ("" if src.is_dir() else f"  [source absente : {src.relative_to(ROOT)}]"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
