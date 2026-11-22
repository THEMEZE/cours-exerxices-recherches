#!/usr/bin/env python3

"""
Moteur de génération des TD.

Usage :
    python3 build/build.py                 # génère toutes les cibles de config.yaml
    python3 build/build.py td1_enonce       # ne génère que cette cible
    python3 build/build.py --no-pdf         # génère les .tex seulement (pas de pdflatex)
    python3 build/build.py --stale          # seulement les PDF « à faire » ou « périmés »
    python3 build/build.py --missing        # seulement les PDF « à faire »
    python3 build/build.py --qcm            # seulement les cibles QCM (type_doc: qcm)
    python3 build/pdf_status.py             # voir ce qui est fait / défait sans rien compiler

    python3 build/build.py                       # sans log
    python3 build/build.py td1_enonce --log      # erreurs + avertissements seulement
    python3 build/build.py td1_enonce --full-log # log complet
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

import threading
import time



ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    load_td, load_cours, niveau_label, normalize_en_color, en_color_latex_definition,
)  # noqa: E402  (source de vérité partagée)
import qcm_data  # noqa: E402  (QCM : chargement, validation, to_latex)
sys.path.insert(0, str(ROOT / "build"))
import pdf_status  # noqa: E402  (état fait / défait des PDF)

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

def to_texdim(value, base="\\linewidth"):
    """Convertit un nombre (fraction de page, ex: 0.7) en dimension LaTeX
    ('0.700\\linewidth'), ou renvoie tel quel si c'est déjà une unité ('5cm')."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{value:.3f}{base}"
    return str(value)  # déjà une unité explicite, ex: "8cm", "0.5\\textheight"

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
    env.filters["qcm_tex"] = qcm_data.to_latex   # texte QCM (plain + $maths$ + **gras**) -> LaTeX sûr
    env.filters["texdim_w"] = lambda v: to_texdim(v, base="\\linewidth")
    env.filters["texdim_h"] = lambda v: to_texdim(v, base="\\textheight")
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

    # 3. Chargement du document (QCM, cours ou TD) et rendu Jinja2
    if type_doc == "qcm":
        # doc = un chapitre (data/matieres/<matiere>/qcm/<doc>.yaml) ou « all » (toute la matière)
        qcm_doc = qcm_data.load_qcm_doc(matiere, doc_slug, target)
        errs = [e for g in qcm_doc["chapitres"] for q in g["questions"] for e in qcm_data.question_errors(q)]
        if errs:
            raise ValueError(f"QCM invalide(s) : {errs[0]} (python3 tools/qcm.py check)")
        tmpl = env.get_template("qcm.tex.j2")
        return tmpl.render(
            titre_document=target["titre"],
            qcm=qcm_doc,
            opts=target,
            matiere_meta=matiere_meta,
            auteur=auteur_final,
        )

    if type_doc == "cours":
        cours = load_cours(matiere, doc_slug)
        tmpl = env.get_template("cours.tex.j2")
        return tmpl.render(
            titre_document=normalize_en_color(target["titre"]),
            couleur_en_definition=en_color_latex_definition(),
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
        titre_document=normalize_en_color(target["titre"]),
        couleur_en_definition=en_color_latex_definition(),
        td=meta,
        exercices=exercices,
        opts=target,
        matiere_meta=matiere_meta,
        auteur=auteur_final,
    )



# ----------------------------------------------------------------------
# Compilation
# ----------------------------------------------------------------------

GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
BLUE = "\033[1;34m"
MAGENTA = "\033[1;35m"
CYAN = "\033[1;36m"
RESET = "\033[0m"


def format_time(total_seconds: float) -> str:
    total_seconds = int(total_seconds)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}h {m:02d}m {s:02d}s"
    return f"{m:02d}m {s:02d}s"


def format_size(size: int) -> str:
    if size >= 1024 ** 3:
        return f"{size / 1024 ** 3:.2f} Go"
    if size >= 1024 ** 2:
        return f"{size / 1024 ** 2:.2f} Mo"
    if size >= 1024:
        return f"{size / 1024:.2f} Ko"
    return f"{size} o"


def extract_log_issues(log: str, include_warnings: bool = True) -> list[str]:
    """Extrait les erreurs LaTeX (lignes '!' + 3 lignes de contexte)
    et, si demandé, les lignes contenant 'warning'."""
    lines = log.splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.startswith("!") or "Fatal error" in line:
            out.append(f"{RED}{line}{RESET}")
            out.extend(f"   {l}" for l in lines[i + 1:i + 4])
            out.append("")
        elif include_warnings and "warning" in line.lower():
            out.append(f"{YELLOW}{line}{RESET}")
    return out


def compile_pdf(tex_path: Path) -> dict:
    start = time.time()
    stop = threading.Event()

    def chrono():
        while not stop.is_set():
            print(f"\r   ⏱️  Temps compilation : {format_time(time.time() - start)}",
                  end="", flush=True)
            stop.wait(1)

    timer = threading.Thread(target=chrono, daemon=True)
    timer.start()

    log = ""
    for _ in range(2):
        res = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory", str(tex_path.parent),
                str(tex_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
        )
        log += res.stdout

    stop.set()
    timer.join()
    print("\r" + " " * 60 + "\r", end="")  # efface la ligne du chrono

    duration = time.time() - start
    pdf_path = tex_path.with_suffix(".pdf")

    dest = None
    size = None
    if pdf_path.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / pdf_path.name
        shutil.copy(pdf_path, dest)
        size = dest.stat().st_size

    # Analyse du log (même logique que compile_all_tex.sh)
    if dest is None or "Fatal error" in log or "! LaTeX Error" in log:
        status = "fail"
    elif "warning" in log.lower():
        status = "warning"
    else:
        status = "success"

    return {"pdf": dest, "status": status, "duration": duration, "size": size, "log": log}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", help="noms de cibles à générer (défaut : toutes)")
    parser.add_argument("--no-pdf", action="store_true", help="ne pas lancer pdflatex")
    parser.add_argument("--log", action="store_true",
                        help="afficher les erreurs et avertissements extraits du log pdflatex")
    parser.add_argument("--full-log", action="store_true",
                        help="afficher le log pdflatex complet")
    parser.add_argument("--stale", action="store_true",
                        help="ne (re)construire que les cibles sans PDF ou dont les sources ont changé")
    parser.add_argument("--missing", action="store_true",
                        help="ne construire que les cibles sans PDF")
    parser.add_argument("--qcm", action="store_true",
                        help="ne construire que les cibles de type QCM (type_doc: qcm)")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "build" / "config.yaml").read_text(encoding="utf-8"))
    targets = config["targets"]
    if args.names:
        unknown = [n for n in args.names if n not in {t["name"] for t in targets}]
        if unknown:
            print(f"{RED}Cibles inconnues dans config.yaml : {', '.join(unknown)}{RESET}")
        targets = [t for t in targets if t["name"] in args.names]
    if args.qcm:
        targets = [t for t in targets if t.get("type_doc") == "qcm"]
    if args.stale or args.missing:
        todo = set(pdf_status.todo_names(config, include_perime=args.stale and not args.missing))
        targets = [t for t in targets if t["name"] in todo]
        print(f"{BLUE}🔎 {len(targets)} cible(s) à construire (le reste est à jour){RESET}")

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    env = make_env()
    counts = {"success": 0, "warning": 0, "fail": 0}
    global_start = time.time()

    print(f"{BLUE}🔹 Génération et compilation des cibles...{RESET}\n")

    for target in targets:
        print(f"{CYAN}🔄 Génération de{RESET} {target['name']}")
        try:
            tex = render_target(env, target, config)
        except Exception as exc:  # source cassée : on continue avec les autres cibles
            print(f"   ❌ {RED}Impossible de générer le .tex : {type(exc).__name__}: {exc}{RESET}\n")
            counts["fail"] += 1
            continue
        tex_path = GEN_DIR / f"{target['name']}.tex"
        tex_path.write_text(tex, encoding="utf-8")
        print(f"   📝 .tex écrit : {tex_path}")

        if args.no_pdf:
            print()
            continue

        result = compile_pdf(tex_path)
        status = result["status"]
        color = {"success": GREEN, "warning": YELLOW, "fail": RED}[status]
        pdf_size = format_size(result["size"]) if result["size"] is not None else "PDF non généré"

        if status == "fail":
            print(f"   ❌ {RED}Erreur de compilation{RESET} : {target['name']}")
            print(f"   🔎 Voir {tex_path.with_suffix('.log')}")
        elif status == "warning":
            print(f"   ⚠️  {YELLOW}Compilation avec avertissements{RESET} : {target['name']}")
        else:
            print(f"   ✅ {GREEN}Compilation réussie{RESET} : {target['name']}")

        print(f"   ⏱️  Temps : {color}{format_time(result['duration'])}{RESET}")
        print(f"   📄 Taille PDF : {color}{pdf_size}{RESET}")
        if args.full_log:
            print(f"   {MAGENTA}──── Log complet ────{RESET}")
            print(result["log"])
        elif args.log and status != "success":
            issues = extract_log_issues(result["log"])
            if issues:
                print(f"   {MAGENTA}──── Erreurs / avertissements ────{RESET}")
                print("\n".join(f"   {l}" for l in issues))
        elif status == "fail":
            print(f"   💡 Relancez avec {CYAN}--log{RESET} pour voir les erreurs.")
        print()

        counts[status] += 1

        if result["pdf"] is not None and status != "fail":
            pdf_status.record_build(target["name"], target, config)

    global_duration = time.time() - global_start

    if not args.no_pdf:
        # Manifeste = réalité du disque (plus d'entrée fantôme) + status.json
        _, status = pdf_status.reconcile(config)
        c = status["counts"]
        print(f"-> Manifeste PDF réécrit : {MANIFEST_PATH}")
        print(f"   état : {c['ok']} à jour · {c['present_sans_empreinte']} sans empreinte · "
              f"{c['perime']} périmés · {c['manquant']} à faire · {c['cible_cassee']} cassés\n")

        print(f"{MAGENTA}──────────── Résumé ────────────{RESET}")
        print(f"✅ {GREEN}Réussies : {counts['success']}{RESET}")
        print(f"⚠️  {YELLOW}Avec avertissements : {counts['warning']}{RESET}")
        print(f"❌ {RED}Échouées : {counts['fail']}{RESET}")
        print()
        print(f"🏁 {BLUE}Temps total : {format_time(global_duration)}{RESET}")
        print(f"{MAGENTA}────────────────────────────────{RESET}")

    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
