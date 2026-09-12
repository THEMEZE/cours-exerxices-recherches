#!/usr/bin/env python3
"""
Exporte data/matieres/**/* en Markdown pour Quartz (callouts façon Obsidian),
avec le système de PROFIL DE VISIBILITÉ (web/visibility_profiles.yaml).

Généralisé à N matières et 2 formes de documents :
  - "td"/"tp"  : dossier d'exercices (questions groupables a/b/c, corrections)
  - "cours"    : fichier unique de sections de lecture (pas de questions)

La structure Quartz générée MIROITE la structure des PDF, matière par
matière, type de document par type de document :

    content/<quartz_namespace>/
        index.md
        TD/<chapitre_slug>/<doc_slug>/{index.md, ex1-....md, ...}
        TP/<chapitre_slug>/<doc_slug>/{...}                      (même format que TD)
        Cours/<doc_slug>.md

Usage :
    python3 web/export_markdown.py --profile avant_seance --out ~/Quartz5/content
    python3 web/export_markdown.py --profile corrige_complet --matiere physique-ondes-ipsa --out ~/Quartz5/content

Après ceci, lance web/build_subject_links.py pour injecter les sections
"Sujets liés" tirées de data/graph/sujets.yaml (indépendant du profil).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    list_matieres, load_matiere_meta, list_docs_td_like, load_td,
    list_docs_cours, load_cours, load_all_qcm,
    apply_visibility_to_exercice, apply_visibility_to_cours,
    niveau_label, enrich_media_paths, enrich_cours_media,
    clean_exercice_for_web, clean_cours_for_web,
    animation_format_web_path,
)

DEFAULT_OUT = ROOT / "web" / "public" / "quartz_content"
PDF_OUT_DIR = ROOT / "build" / "output"
MANIFEST_PATH = PDF_OUT_DIR / "manifest.json"

TYPE_LABELS = {"td": "TD", "tp": "TP", "cours": "Cours"}

# États de repli des callouts (voir DEPLOY_RASPBERRY.md / SCHEMA.md pour la
# justification) : '' fixe, '+' ouvert-repliable, '-' fermé-repliable.
COLLAPSE = {
    "coup_de_pouce": "-",
    "aller_plus_loin": "-",
    "correction": "+",
    "solution": "-",
    "qcm": "-",
    "info_td": "",
    "remarque": "",
    "encadre": "-",
}


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[àâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôö]", "o", text)
    text = text.replace("ç", "c")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "sans-titre"


def callout(kind: str, title: str, body: str, collapse_key: str) -> str:
    modifier = COLLAPSE.get(collapse_key, "")
    lines = body.strip("\n").split("\n")
    quoted = "\n".join((("> " + l) if l.strip() else ">") for l in lines)
    return f"> [!{kind}]{modifier} {title}\n{quoted}\n"


def clickable_image(src: str, alt: str) -> str:
    return f"[![{alt}]({src})]({src})"


def render_animation_block(anim: dict) -> str:
    parts = [clickable_image(anim["src"], "animation")]
    extra_links = []
    for fmt in anim.get("formats", []):
        if fmt == "gif":
            continue
        alt_src = animation_format_web_path(anim["ref"], fmt)
        if alt_src and fmt != "frames_pdf":
            label = {"mp4": "🎞️ Voir en .mp4"}.get(fmt, fmt)
            extra_links.append(f"[{label}]({alt_src})")
    if extra_links:
        parts.append(" · ".join(extra_links))
    return "\n\n".join(parts)


def load_pdf_manifest():
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def find_pdf_for_doc(manifest: dict, matiere: str, type_doc: str, doc_slug: str, suffix: str = None):
    """Retourne le chemin web du PDF le plus pertinent pour ce document, en
    utilisant le manifeste écrit par build/build.py (jamais de nom de
    fichier deviné par convention -- un vrai bug de ce genre a été trouvé
    et corrigé : un document 'cours' dont le nom de cible PDF ne suivait
    pas la convention <id>_<suffixe> ne recevait silencieusement aucun
    lien). S'il existe plusieurs cibles pour ce document (ex: enonce/
    corrige) et qu'un `suffix` est demandé, on préfère la cible dont le
    nom se termine par `_<suffix>` ; sinon on prend la première par ordre
    alphabétique (déterministe)."""
    matches = {name: e for name, e in manifest.items()
               if e.get("matiere") == matiere and e.get("type_doc") == type_doc and e.get("doc") == doc_slug}
    if not matches:
        return None
    if suffix:
        for name, e in matches.items():
            if name.endswith(f"_{suffix}"):
                return f"/pdfs/{e['pdf']}"
    name = sorted(matches.keys())[0]
    return f"/pdfs/{matches[name]['pdf']}"


# ----------------------------------------------------------------------
# Rendu td-like (exercices)
# ----------------------------------------------------------------------

def render_encadre_md(enc: dict) -> str:
    """Rendu web d'un `encadre` (style \\EncadreDeux en LaTeX) : callout
    Obsidian, titre = "type — titre" (les deux champs texte de
    \\EncadreDeux), replié par défaut comme les autres compléments."""
    titre = f"{enc.get('type', '')} — {enc.get('titre', '')}".strip(" —")
    return callout("info", f"📦 {titre}", enc.get("contenu", ""), "encadre")


def render_question_md(q: dict) -> str:
    parts = [q["enonce"].strip()]
    if q.get("figure"):
        parts.append(clickable_image(q["figure"]["src"], q["figure"].get("legende", "")))
    if q.get("animation"):
        parts.append(render_animation_block(q["animation"]))
    if q.get("coup_de_pouce"):
        parts.append(callout("tip", "💡 Coup de pouce", q["coup_de_pouce"], "coup_de_pouce"))
    for niveau, texte in q.get("aller_plus_loin", {}).items():
        parts.append(callout("question", f"🔭 Aller plus loin — {niveau_label(niveau)}", texte, "aller_plus_loin"))
    if q.get("correction"):
        parts.append(callout("success", "✅ Correction", q["correction"], "correction"))
    if q.get("solution"):
        parts.append(callout("example", "📝 Solution détaillée", q["solution"], "solution"))
    if q.get("encadre"):
        parts.append(render_encadre_md(q["encadre"]))
    return "\n\n".join(parts)


def render_exercice_md(ex: dict, voir_aussi: list) -> str:
    out = [f"### Exercice {ex['numero']}. {ex['intitule']}" + (" *(facultatif)*" if ex.get("facultatif") else "")]
    out.append(ex.get("enonce_intro", "").strip())
    if ex.get("figure"):
        out.append(clickable_image(ex["figure"]["src"], ex["figure"].get("legende", "")))
    if ex.get("animation"):
        out.append(render_animation_block(ex["animation"]))

    for item in ex.get("contenu", []):
        if item["kind"] == "intro":
            out.append(item["enonce"])
        elif item["kind"] == "single":
            out.append(f"**{item.get('id','')}.** " + render_question_md(item))
        elif item["kind"] == "group":
            out.append(f"**{item['label']}.**")
            for i, sq in enumerate(item["subquestions"]):
                letter = chr(ord("a") + i)
                out.append(f"  **{letter})** " + render_question_md(sq))

    if voir_aussi:
        links = " · ".join(f"[[{path}|{label}]]" for path, label in voir_aussi)
        out.append(callout("note", "🔗 Voir aussi", links, "info_td"))

    return "\n\n".join(p for p in out if p.strip())


def render_qcm_md(qcm_list: list, exercice_paths: dict) -> str:
    if not qcm_list:
        return ""
    blocks = ["## QCM de réveil liés à ce document\n"]
    moment_titles = {"debut": "🌅 Début de cours", "milieu": "🔄 Milieu de cours", "fin": "🌇 Fin de cours"}
    for q in qcm_list:
        choices = "\n".join(f"- {c['texte']}" for c in q["choix"])
        body = f"**{q['question']}**\n\n{choices}\n\n*Réponds en direct sur [l'appli QCM](/qcm/) (QR code affiché en cours).*"
        if q.get("lie_a") and q["lie_a"] in exercice_paths:
            body += f"\n\nEn lien avec [[{exercice_paths[q['lie_a']]}|cet exercice]]."
        blocks.append(callout("question", f"QCM — {moment_titles.get(q['moment'], q['moment'])}", body, "qcm"))
    return "\n\n".join(blocks)


def build_tag_index(all_exercices):
    idx = defaultdict(list)
    for matiere, type_doc, chap_slug, td_slug, ex in all_exercices:
        for tag in ex.get("cours_rattache", []):
            idx[tag].append((matiere, type_doc, ex["slug"], ex["numero"], ex["intitule"], chap_slug, td_slug))
    return idx


def voir_aussi_for(ex, tag_index, self_key):
    seen = {}
    for tag in ex.get("cours_rattache", []):
        for (matiere, type_doc, ex_slug, numero, intitule, c_slug, t_slug) in tag_index.get(tag, []):
            key = (matiere, type_doc, ex_slug)
            if key == self_key or key in seen:
                continue
            fname = f"ex{numero}-{slugify(intitule)}"
            path = f"{TYPE_LABELS[type_doc]}/{c_slug}/{t_slug}/{fname}"
            seen[key] = (path, f"Exercice {numero} — {intitule}")
    return list(seen.values())


def export_td_doc(matiere, type_doc, doc_slug, opts, ns_dir, tag_index, exercice_paths, manifest):
    meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
    chapitre_slug = slugify(meta["chapitre_cours"])
    td_name_slug = slugify(meta["titre"])
    td_dir = ns_dir / TYPE_LABELS[type_doc] / chapitre_slug / td_name_slug
    td_dir.mkdir(parents=True, exist_ok=True)

    pdf_url = find_pdf_for_doc(manifest, matiere, type_doc, doc_slug, opts.get("pdf_suffix"))

    index_lines = [
        "---", f"title: \"{meta['titre']}\"", "tags:", "  - " + type_doc,
        f"  - {chapitre_slug}", "---", "",
        callout("info", f"ℹ️ {meta['chapitre_cours']}", f"Séance {meta.get('seance', '?')}", "info_td"), "",
    ]
    if pdf_url:
        index_lines += [f"📄 **[Télécharger le PDF complet]({pdf_url})**", ""]

    for ex in exercices:
        ex_filtered = clean_exercice_for_web(apply_visibility_to_exercice(enrich_media_paths(ex), opts))
        self_key = (matiere, type_doc, ex["slug"])
        voir_aussi = voir_aussi_for(ex, tag_index, self_key)
        md_body = render_exercice_md(ex_filtered, voir_aussi)
        fname = f"ex{ex['numero']}-{slugify(ex['intitule'])}.md"

        breadcrumb = f"[[{TYPE_LABELS[type_doc]}/{chapitre_slug}/{td_name_slug}/index|⬅ Retour]]"
        if pdf_url:
            breadcrumb += f" · [📄 PDF]({pdf_url})"

        frontmatter = (
            "---\n" f"title: \"Exercice {ex['numero']} — {ex['intitule']}\"\n"
            "tags:\n" f"  - {type_doc}\n" f"  - {chapitre_slug}\n" "---\n\n" f"{breadcrumb}\n\n"
        )
        (td_dir / fname).write_text(frontmatter + md_body + "\n", encoding="utf-8")
        index_lines.append(f"- [[{fname[:-3]}|Exercice {ex['numero']} — {ex['intitule']}]]")

    qcm_all = load_all_qcm(matiere)
    qcm_td = [q for q in qcm_all if q.get("td") == meta["id"]]
    qcm_md = render_qcm_md(qcm_td, exercice_paths)
    if qcm_md:
        index_lines += ["", qcm_md]

    (td_dir / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"   -> {td_dir.relative_to(ns_dir)}/ ({len(exercices)} exercices)")
    return meta, pdf_url, chapitre_slug, td_name_slug


# ----------------------------------------------------------------------
# Rendu cours-like (sections de lecture)
# ----------------------------------------------------------------------

def render_section_md(sec: dict) -> str:
    parts = [f"## {sec['numero']}. {sec['titre']}", sec.get("contenu", "").strip()]
    if sec.get("figure"):
        parts.append(clickable_image(sec["figure"]["src"], sec["figure"].get("legende", "")))
    if sec.get("animation"):
        parts.append(render_animation_block(sec["animation"]))
    if sec.get("remarque"):
        parts.append(callout("info", "💡 Remarque", sec["remarque"], "remarque"))
    for niveau, texte in sec.get("aller_plus_loin", {}).items():
        parts.append(callout("question", f"🔭 Aller plus loin — {niveau_label(niveau)}", texte, "aller_plus_loin"))
    if sec.get("encadre"):
        parts.append(render_encadre_md(sec["encadre"]))
    return "\n\n".join(p for p in parts if p.strip())


def export_cours_doc(matiere, doc_slug, opts, ns_dir, manifest):
    doc = load_cours(matiere, doc_slug)
    doc_filtered = clean_cours_for_web(apply_visibility_to_cours(enrich_cours_media(doc), opts))
    cours_dir = ns_dir / "Cours"
    cours_dir.mkdir(parents=True, exist_ok=True)

    pdf_url = find_pdf_for_doc(manifest, matiere, "cours", doc_slug, opts.get("pdf_suffix"))

    lines = [
        "---", f"title: \"{doc['titre']}\"", "tags:", "  - cours", "---",
    ]
    frontmatter = "\n".join(lines)
    body_parts = []
    if doc.get("sous_titre"):
        body_parts.append(f"*{doc['sous_titre']}*")
    if pdf_url:
        body_parts.append(f"📄 **[Télécharger le PDF]({pdf_url})**")

    for sec in doc_filtered.get("sections", []):
        body_parts.append(render_section_md(sec))

    fname = f"{doc_slug}.md"
    full_text = frontmatter + "\n\n" + "\n\n".join(body_parts)
    (cours_dir / fname).write_text(full_text + "\n", encoding="utf-8")
    print(f"   -> Cours/{fname}")
    return doc


# ----------------------------------------------------------------------
# Export d'une matière entière
# ----------------------------------------------------------------------

def export_matiere(matiere, opts, out_dir, tag_index, exercice_paths, manifest):
    meta = load_matiere_meta(matiere)
    namespace = meta.get("quartz_namespace", matiere)
    ns_dir = out_dir / namespace
    ns_dir.mkdir(parents=True, exist_ok=True)

    sections_index = ["---", f"title: \"{meta['nom']}\"", "tags:", "  - matiere", "---", "",
                       meta.get("description", "").strip(), ""]

    for type_doc in ("td", "tp"):
        docs = list_docs_td_like(matiere, type_doc)
        if not docs:
            continue
        sections_index.append(f"## {TYPE_LABELS[type_doc]}\n")
        for doc_slug in docs:
            td_meta, pdf_url, chap_slug, td_slug = export_td_doc(
                matiere, type_doc, doc_slug, opts, ns_dir, tag_index, exercice_paths, manifest)
            line = f"- [[{TYPE_LABELS[type_doc]}/{chap_slug}/{td_slug}/index|{td_meta['titre']}]]"
            if pdf_url:
                line += f" ([PDF]({pdf_url}))"
            sections_index.append(line)
        sections_index.append("")

    cours_docs = list_docs_cours(matiere)
    if cours_docs:
        sections_index.append("## Cours\n")
        for doc_slug in cours_docs:
            doc = export_cours_doc(matiere, doc_slug, opts, ns_dir, manifest)
            sections_index.append(f"- [[Cours/{doc_slug}|{doc['titre']}]]")
        sections_index.append("")

    (ns_dir / "index.md").write_text("\n".join(sections_index) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True, help="voir web/visibility_profiles.yaml")
    p.add_argument("--matiere", default=None, help="une seule matière ; défaut : toutes")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="dossier content/ de Quartz")
    args = p.parse_args()

    profiles = yaml.safe_load((ROOT / "web" / "visibility_profiles.yaml").read_text())["profiles"]
    if args.profile not in profiles:
        print(f"!! profil inconnu : {args.profile} (disponibles : {list(profiles.keys())})")
        return
    opts = profiles[args.profile]

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    matieres = [args.matiere] if args.matiere else list_matieres()

    # Index "voir aussi" (tags cours_rattache) et table des chemins pour les
    # QCM (lie_a) -- construits sur toutes les matières concernées, pour que
    # les liens croisés fonctionnent aussi ENTRE matières (ex: une leçon
    # d'agrégation qui cite un TD IPSA).
    all_exercices = []
    exercice_paths = {}
    for matiere in matieres:
        for type_doc in ("td", "tp"):
            for doc_slug in list_docs_td_like(matiere, type_doc):
                td_meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
                chap_slug = slugify(td_meta["chapitre_cours"])
                td_name_slug = slugify(td_meta["titre"])
                for ex in exercices:
                    all_exercices.append((matiere, type_doc, chap_slug, td_name_slug, ex))
                    key = f"{td_meta['id']}_ex{ex['numero']}"
                    exercice_paths[key] = f"{TYPE_LABELS[type_doc]}/{chap_slug}/{td_name_slug}/ex{ex['numero']}-{slugify(ex['intitule'])}"
    tag_index = build_tag_index(all_exercices)

    print(f"-- Export Markdown, profil '{args.profile}' -> {out_dir}")
    manifest = load_pdf_manifest()
    if not manifest:
        print("   ⚠️  build/output/manifest.json introuvable -- lance build/build.py "
              "d'abord si tu veux les liens PDF cliquables.")
    for matiere in matieres:
        export_matiere(matiere, opts, out_dir, tag_index, exercice_paths, manifest)


if __name__ == "__main__":
    main()
