#!/usr/bin/env python3
"""
manage.py — vue d'ensemble + ménage, pour ne pas surcharger le Raspberry Pi.

Répond à trois questions concrètes :
  1. Qu'est-ce qu'on PEUT construire ?           -> manage.py list
  2. Qu'est-ce qui est DÉJÀ construit ?           -> manage.py status
  3. Comment nettoyer sans tout casser ?          -> manage.py clean ...

Rien ici ne lit/écrit en dehors de build/output/, animations/outputs/,
web/public/, et le dossier Quartz (content/, public/) que TU précises --
jamais data/ (source de vérité, jamais touchée par le ménage).

Usage :
    python3 manage.py list                        # tout ce qui peut être généré
    python3 manage.py status                       # ce qui existe déjà + poids disque
    python3 manage.py disk-usage                    # détail des tailles par catégorie

    python3 manage.py clean pdf td1_enonce           # supprime UN pdf
    python3 manage.py clean pdf td1_enonce td1_corrige
    python3 manage.py clean pdf --all                 # supprime TOUS les pdf

    python3 manage.py clean frames --all              # supprime les frames \animategraphics
                                                        # (non utilisées actuellement --
                                                        # voir `status`, gros gain de place)

    python3 manage.py clean md --matiere physique-ondes-ipsa --quartz-content ~/Quartz5/content
    python3 manage.py clean md --all --quartz-content ~/Quartz5/content

    python3 manage.py clean all --quartz-content ~/Quartz5/content --yes   # tout, sans confirmation
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    list_matieres, load_matiere_meta, list_docs_td_like, load_td,
    list_docs_cours,
)
from web.export_markdown import slugify, TYPE_LABELS  # noqa: E402

BUILD_CONFIG = ROOT / "build" / "config.yaml"
PDF_DIR = ROOT / "build" / "output"
MANIFEST_PATH = PDF_DIR / "manifest.json"
ANIM_DIR = ROOT / "animations" / "outputs"
FIGURES_DIR = ROOT / "web" / "public" / "figures"
DEFAULT_QUARTZ_CONTENT = ROOT / ".." / "Quartz5" / "content"


# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------

def human_size(n_bytes: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n_bytes < 1024:
            return f"{n_bytes:.0f} {unit}" if unit == "o" else f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} To"


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def load_build_targets():
    return yaml.safe_load(BUILD_CONFIG.read_text(encoding="utf-8"))["targets"]


def confirm(question: str, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    reponse = input(f"{question} [o/N] ").strip().lower()
    return reponse in ("o", "oui", "y", "yes")


# ----------------------------------------------------------------------
# list — tout ce qu'on PEUT construire
# ----------------------------------------------------------------------

def cmd_list(args):
    print("=== Cibles PDF déclarées (build/config.yaml) ===")
    for t in load_build_targets():
        print(f"  {t['name']:<40} matiere={t['matiere']:<28} type={t.get('type_doc','td'):<6} doc={t.get('doc', t.get('td'))}")

    print("\n=== Documents disponibles dans data/matieres/ (indépendamment des cibles PDF) ===")
    for matiere in list_matieres():
        meta = load_matiere_meta(matiere)
        print(f"\n  📚 {matiere} — {meta['nom']}")
        for type_doc in ("td", "tp"):
            docs = list_docs_td_like(matiere, type_doc)
            for d in docs:
                print(f"     [{type_doc}]    {d}")
        for d in list_docs_cours(matiere):
            print(f"     [cours] {d}")


# ----------------------------------------------------------------------
# status — ce qui est DÉJÀ construit (PDF + Quartz .md) + poids disque
# ----------------------------------------------------------------------

def expected_quartz_paths(quartz_content: Path):
    """Retourne {(matiere, type_doc, doc_slug): [chemins .md attendus]}
    en se basant uniquement sur data/ (jamais en devinant depuis le disque)."""
    expected = {}
    for matiere in list_matieres():
        meta = load_matiere_meta(matiere)
        ns = quartz_content / meta.get("quartz_namespace", matiere)
        for type_doc in ("td", "tp"):
            for doc_slug in list_docs_td_like(matiere, type_doc):
                td_meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
                chap = slugify(td_meta["chapitre_cours"])
                name = slugify(td_meta["titre"])
                doc_dir = ns / TYPE_LABELS[type_doc] / chap / name
                paths = [doc_dir / "index.md"] + [
                    doc_dir / f"ex{ex['numero']}-{slugify(ex['intitule'])}.md" for ex in exercices
                ]
                expected[(matiere, type_doc, doc_slug)] = paths
        for doc_slug in list_docs_cours(matiere):
            expected[(matiere, "cours", doc_slug)] = [ns / "Cours" / f"{doc_slug}.md"]
    return expected


def cmd_status(args):
    quartz_content = Path(args.quartz_content).expanduser().resolve()
    manifest = load_manifest()

    print("=== PDF (build/output/) ===")
    targets = load_build_targets()
    for t in targets:
        pdf_path = PDF_DIR / f"{t['name']}.pdf"
        if pdf_path.exists():
            size = human_size(pdf_path.stat().st_size)
            mtime = pdf_path.stat().st_mtime
            import datetime
            date = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  ✅ {t['name']:<40} {size:>8}   ({date})")
        else:
            print(f"  ⬜ {t['name']:<40} (pas encore construit)")
    stale = set(manifest.keys()) - {t["name"] for t in targets}
    if stale:
        print(f"  ⚠️  entrées dans manifest.json sans cible correspondante (obsolètes) : {sorted(stale)}")

    print(f"\n=== Markdown Quartz ({quartz_content}) ===")
    if not quartz_content.exists():
        print("  (dossier introuvable -- rien construit ici pour l'instant)")
    else:
        expected = expected_quartz_paths(quartz_content)
        for (matiere, type_doc, doc_slug), paths in expected.items():
            n_present = sum(1 for p in paths if p.exists())
            if n_present == 0:
                mark = "⬜"
            elif n_present == len(paths):
                mark = "✅"
            else:
                mark = "🟡"
            print(f"  {mark} {matiere}/{type_doc}/{doc_slug:<30} {n_present}/{len(paths)} fichier(s)")

    print("\n=== Résumé disque ===")
    print(f"  PDF                : {human_size(dir_size(PDF_DIR))}")
    print(f"  Animations (total) : {human_size(dir_size(ANIM_DIR))}")
    frames_total = sum(dir_size(p) for p in ANIM_DIR.glob("*/frames")) if ANIM_DIR.exists() else 0
    if frames_total:
        print(f"    dont frames \\animategraphics : {human_size(frames_total)}  "
              f"⚠️  actuellement JAMAIS utilisées par les templates (voir `manage.py disk-usage`, "
              f"nettoyable via `manage.py clean frames --all`)")
    print(f"  Figures SVG        : {human_size(dir_size(FIGURES_DIR))}")
    if quartz_content.exists():
        print(f"  Quartz content/    : {human_size(dir_size(quartz_content))}")
        quartz_public = quartz_content.parent / "public"
        if quartz_public.exists():
            print(f"  Quartz public/     : {human_size(dir_size(quartz_public))}")


# ----------------------------------------------------------------------
# disk-usage — détail, sans la partie "status" (pratique en isolation)
# ----------------------------------------------------------------------

def cmd_disk_usage(args):
    quartz_content = Path(args.quartz_content).expanduser().resolve()
    rows = [
        ("PDF (build/output/)", PDF_DIR),
        ("Animations (total)", ANIM_DIR),
        ("Figures SVG", FIGURES_DIR),
    ]
    if quartz_content.exists():
        rows.append(("Quartz content/", quartz_content))
        quartz_public = quartz_content.parent / "public"
        if quartz_public.exists():
            rows.append(("Quartz public/ (build)", quartz_public))

    total = 0
    for label, path in rows:
        size = dir_size(path)
        total += size
        print(f"  {label:<28} {human_size(size):>10}")
    print(f"  {'TOTAL':<28} {human_size(total):>10}")

    if ANIM_DIR.exists():
        print("\n  Détail par animation :")
        for anim_dir in sorted(ANIM_DIR.iterdir()):
            if not anim_dir.is_dir():
                continue
            frames = anim_dir / "frames"
            gif_mp4 = dir_size(anim_dir) - dir_size(frames)
            print(f"    {anim_dir.name:<28} gif/mp4={human_size(gif_mp4):>8}   "
                  f"frames={human_size(dir_size(frames)):>8}")


# ----------------------------------------------------------------------
# clean pdf
# ----------------------------------------------------------------------

def cmd_clean_pdf(args):
    manifest = load_manifest()
    targets = load_build_targets()
    names = [t["name"] for t in targets] if args.all else args.names
    if not names:
        print("Rien à faire (précise des noms de cible, ou --all). Voir `manage.py list`.")
        return

    if not confirm(f"Supprimer {len(names)} PDF ({', '.join(names)}) ?", args.yes):
        print("Annulé.")
        return

    removed = 0
    for name in names:
        pdf_path = PDF_DIR / f"{name}.pdf"
        if pdf_path.exists():
            pdf_path.unlink()
            print(f"  🗑️  {pdf_path}")
            removed += 1
        manifest.pop(name, None)
    save_manifest(manifest)
    print(f"-> {removed} fichier(s) PDF supprimé(s), manifest.json mis à jour.")


# ----------------------------------------------------------------------
# clean md
# ----------------------------------------------------------------------

def cmd_clean_md(args):
    quartz_content = Path(args.quartz_content).expanduser().resolve()
    if not quartz_content.exists():
        print(f"Dossier introuvable : {quartz_content}")
        return

    to_remove = []
    if args.all:
        for matiere in list_matieres():
            meta = load_matiere_meta(matiere)
            to_remove.append((matiere, quartz_content / meta.get("quartz_namespace", matiere)))
    elif args.matiere:
        meta = load_matiere_meta(args.matiere)
        to_remove.append((args.matiere, quartz_content / meta.get("quartz_namespace", args.matiere)))
    else:
        print("Précise --matiere <slug> ou --all. Voir `manage.py list`.")
        return

    # Sécurité : on ne supprime JAMAIS un dossier qui ne correspond pas
    # EXACTEMENT au quartz_namespace déclaré d'une matière -- on ne touche
    # donc jamais tes notes personnelles écrites à la main, quelle que soit
    # l'option utilisée.
    print("Dossiers concernés :")
    for matiere, path in to_remove:
        exists = "existe" if path.exists() else "n'existe pas (rien à faire)"
        print(f"  - {path}  ({exists}, matière : {matiere})")

    if not confirm(f"Supprimer ces {len(to_remove)} dossier(s) Quartz générés ?", args.yes):
        print("Annulé.")
        return

    for matiere, path in to_remove:
        if path.exists():
            shutil.rmtree(path)
            print(f"  🗑️  {path}")
    print("-> Markdown Quartz nettoyé. Relance web/export_markdown.py pour reconstruire.")


# ----------------------------------------------------------------------
# clean frames
# ----------------------------------------------------------------------

def cmd_clean_frames(args):
    if not ANIM_DIR.exists():
        print("Aucune animation générée.")
        return
    refs = [d.name for d in ANIM_DIR.iterdir() if d.is_dir()] if args.all else args.refs
    if not refs:
        print("Précise des refs d'animation, ou --all. Voir `manage.py status`.")
        return

    total_freed = 0
    frame_dirs = []
    for ref in refs:
        fd = ANIM_DIR / ref / "frames"
        if fd.exists():
            frame_dirs.append(fd)
            total_freed += dir_size(fd)

    if not frame_dirs:
        print("Rien à supprimer (aucun dossier frames/ trouvé pour ces refs).")
        return

    print(f"⚠️  Rappel : ces frames ne sont utilisées par AUCUN template actuellement "
          f"(\\animategraphics n'est pas encore câblé) -- suppression sans impact visible.")
    if not confirm(f"Supprimer {len(frame_dirs)} dossier(s) frames/ ({human_size(total_freed)}) ?", args.yes):
        print("Annulé.")
        return

    for fd in frame_dirs:
        shutil.rmtree(fd)
        print(f"  🗑️  {fd}")
    print(f"-> {human_size(total_freed)} libéré(s).")


# ----------------------------------------------------------------------
# clean all
# ----------------------------------------------------------------------

def cmd_clean_all(args):
    print("Ceci va supprimer : tous les PDF, toutes les animations (gif/mp4/frames), "
          "toutes les figures SVG, et le Markdown Quartz généré (jamais tes notes perso).")
    if not confirm("Confirmer le nettoyage complet ?", args.yes):
        print("Annulé.")
        return

    if PDF_DIR.exists():
        shutil.rmtree(PDF_DIR)
        print(f"  🗑️  {PDF_DIR}")
    if ANIM_DIR.exists():
        shutil.rmtree(ANIM_DIR)
        print(f"  🗑️  {ANIM_DIR}")
    if FIGURES_DIR.exists():
        shutil.rmtree(FIGURES_DIR)
        print(f"  🗑️  {FIGURES_DIR}")

    quartz_content = Path(args.quartz_content).expanduser().resolve()
    if quartz_content.exists():
        for matiere in list_matieres():
            meta = load_matiere_meta(matiere)
            path = quartz_content / meta.get("quartz_namespace", matiere)
            if path.exists():
                shutil.rmtree(path)
                print(f"  🗑️  {path}")

    print("-> Nettoyage complet terminé. Relance build/build.py + web/publish_profile.sh pour tout regénérer.")


# ----------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="tout ce qu'on PEUT construire").set_defaults(func=cmd_list)

    sp = sub.add_parser("status", help="ce qui est déjà construit + poids disque")
    sp.add_argument("--quartz-content", default=str(DEFAULT_QUARTZ_CONTENT))
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("disk-usage", help="détail des tailles sur disque")
    sp.add_argument("--quartz-content", default=str(DEFAULT_QUARTZ_CONTENT))
    sp.set_defaults(func=cmd_disk_usage)

    clean = sub.add_parser("clean", help="supprimer des fichiers générés (jamais data/)")
    clean_sub = clean.add_subparsers(dest="clean_target", required=True)

    sp = clean_sub.add_parser("pdf", help="supprimer un/plusieurs/tous les PDF")
    sp.add_argument("names", nargs="*", help="noms de cibles (voir `manage.py list`)")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--yes", action="store_true", help="ne pas demander confirmation")
    sp.set_defaults(func=cmd_clean_pdf)

    sp = clean_sub.add_parser("md", help="supprimer le Markdown Quartz généré (une matière ou tout)")
    sp.add_argument("--matiere", default=None)
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--quartz-content", default=str(DEFAULT_QUARTZ_CONTENT))
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(func=cmd_clean_md)

    sp = clean_sub.add_parser("frames", help="supprimer les frames \\animategraphics (gros gain de place)")
    sp.add_argument("refs", nargs="*", help="refs d'animation (voir `manage.py status`)")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(func=cmd_clean_frames)

    sp = clean_sub.add_parser("all", help="tout nettoyer (PDF + animations + figures + Quartz généré)")
    sp.add_argument("--quartz-content", default=str(DEFAULT_QUARTZ_CONTENT))
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(func=cmd_clean_all)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
