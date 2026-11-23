#!/usr/bin/env python3
"""
Exporte data/matieres/**/* en Markdown pour Quartz (callouts façon Obsidian),
avec le système de PROFIL DE VISIBILITÉ (web/visibility_profiles.yaml).

Généralisé à N matières et 2 formes de documents (types déclarés dans build/config.yaml > types_documents) :
  - forme "exercices" (td, tp, projet, ...) : dossier d'exercices (questions a/b/c, corrections)
  - forme "sections"  (cours, ...)          : fichier unique de sections de lecture

La structure Quartz générée MIROITE la structure des PDF, matière par
matière, type de document par type de document :

    content/<quartz_namespace>/
        index.md                                  (une section par type : TD, TP, Mini-Projet, Cours...)
        TD/<chapitre_slug>/<doc_slug>/{index.md, ex1-....md, ...}
        TP/<chapitre_slug>/<doc_slug>/{...}                      (même format que TD)
        Mini-Projet/<chapitre_slug>/<doc_slug>/{...}             (même format que TD)
        Cours/<doc_slug>.md

Chaque page peut afficher : les rubriques pédagogiques du profil (prérequis, objectifs, point de cours,
bilan...), les fichiers rattachés (build/config.yaml > fichiers) et les liens + QR code des QCM
(build/config.yaml > qcm > liens). Voir web/rubriques_md.py, web/fichiers_joints.py, GUIDE_EVOLUTIONS.md.

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
sys.path.insert(0, str(ROOT / "build"))
import pdf_status  # noqa: E402
from common_data import (  # noqa: E402
    list_matieres, load_matiere_meta, list_docs_td_like, load_td,
    list_docs_cours, load_cours, load_all_qcm, clean_text_for_web,
    apply_visibility_to_exercice, apply_visibility_to_cours,
    niveau_label, enrich_media_paths, enrich_cours_media,
    clean_exercice_for_web, clean_cours_for_web,
    animation_format_web_path, load_sujets_graph,
    title_parts, en_span, resolve_profile, load_visibility_profiles, publication_config,
    doc_types, exercise_types, section_types, type_label, type_quartz_dir, profile_audiences, expand_profile,
)

import qcm_data  # noqa: E402  (QCM : liens d'accès libre + QR code)
from web import fichiers_joints  # noqa: E402  (fichiers rattachés : config.yaml > fichiers)
from web.rubriques_md import render_rubriques, filter_apl  # noqa: E402  (rubriques pédagogiques)

DEFAULT_OUT = ROOT / "web" / "public" / "quartz_content"
PDF_OUT_DIR = ROOT / "build" / "output"
MANIFEST_PATH = PDF_OUT_DIR / "manifest.json"
GENERATED_REGISTRY = ".coursondes-generated.json"   # écrit à côté de content/ (jamais dedans)
KIND_LABEL = {"enonce": "Énoncé", "aides": "Aides", "corrige": "Corrigé", "autre": "PDF", "fiche": "Fiche enseignant"}

TYPE_LABELS = {k: type_quartz_dir(k) for k in doc_types()}      # dossier Quartz de chaque type (config.yaml > types_documents)

# États de repli des callouts (voir DEPLOY_RASPBERRY.md / SCHEMA.md pour la
# justification) : '' fixe, '+' ouvert-repliable, '-' fermé-repliable.
COLLAPSE = {
    "coup_de_pouce": "-",
    "aller_plus_loin": "-",
    "correction": "-",      # repliée : l'étudiant clique pour la voir (avant : "+" = ouverte)
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


def blocks_to_md(val) -> str:
    """Un champ (coup_de_pouce, correction, solution...) est soit une chaîne,
    soit une liste de blocs {titre, texte, [figure]} (c'est le cas de 600 des
    solutions de tes YAML -- l'ancien code plantait dessus)."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    parts = []
    for b in val:
        if isinstance(b, str):
            parts.append(b)
            continue
        seg = []
        if b.get("titre"):
            seg.append(f"**{b['titre']}**")
        if b.get("texte"):
            seg.append(str(b["texte"]).strip())
        fm = figures_md(b.get("figure"))
        if fm:
            seg.append(fm)
        parts.append("\n\n".join(seg))
    return "\n\n".join(p for p in parts if p.strip())


def callout(kind: str, title: str, body, collapse_key: str) -> str:
    modifier = COLLAPSE.get(collapse_key, "")
    lines = blocks_to_md(body).strip("\n").split("\n")
    quoted = "\n".join((("> " + l) if l.strip() else ">") for l in lines)
    return f"> [!{kind}]{modifier} {title}\n{quoted}\n"


def apl_callouts(apl) -> list:
    """aller_plus_loin : dict {niveau: texte} (ancien) ou liste {niveau, titre, texte} (actuel)."""
    out = []
    if isinstance(apl, dict):
        for niveau, texte in apl.items():
            out.append(callout("question", f"🔭 Aller plus loin — {niveau_label(niveau)}", texte, "aller_plus_loin"))
    elif isinstance(apl, list):
        for it in apl:
            niveau = niveau_label(it.get("niveau", ""))
            titre = f" : {it['titre']}" if it.get("titre") else ""
            out.append(callout("question", f"🔭 Aller plus loin — {niveau}{titre}", [{"texte": it.get("texte", ""), "figure": it.get("figure")}], "aller_plus_loin"))
    return out


def chapitre_slug_of(meta: dict) -> str:
    chap_fr, _ = title_parts(meta.get("chapitre_cours") or "")
    return slugify(chap_fr) if chap_fr else "general"       # (avant : « sans-titre » dans l'URL)


def td_base(ns: str, type_doc: str, meta: dict) -> str:
    """Dossier Quartz d'un TD/TP : le slug vient du titre FRANÇAIS seul (plus de
    « -color-blue-standing-waves... » dans les URL)."""
    return f"{ns}/{TYPE_LABELS[type_doc]}/{chapitre_slug_of(meta)}/{slugify(title_parts(meta['titre'])[0])}"


def ex_slug_of(ex: dict) -> str:
    return slugify(title_parts(ex["intitule"])[0])


def title_line(raw: str) -> str:
    """Ligne d'anglais en couleur (vide s'il n'y a pas de partie anglaise)."""
    return en_span(title_parts(raw)[1])


def fm_title(title: str) -> str:
    """Titre sûr pour un frontmatter YAML (guillemets, deux-points, etc.)."""
    return json.dumps(str(title), ensure_ascii=False)


def clickable_image(src: str, alt: str) -> str:
    """Figure centrée, sur une carte blanche (les SVG TikZ sont en traits foncés
    sur fond transparent : invisibles sur un thème sombre), cliquable -> grand
    format dans un nouvel onglet."""
    alt = (alt or "").strip()
    if alt in ("{}", "$ $", "???"):      # légendes de gabarit non remplies
        alt = ""
    alt = alt.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return (f'<p style="text-align:center"><a href="{src}" target="_blank" rel="noopener">'
            f'<img src="{src}" alt="{alt}" loading="lazy" '
            f'style="background:#fff;padding:10px;border-radius:10px;max-width:100%;height:auto"></a></p>')


def figures_md(fig) -> str:
    """Une figure (dict) ou plusieurs (liste) -> images cliquables."""
    if not fig:
        return ""
    figs = fig if isinstance(fig, list) else [fig]
    return "\n\n".join(clickable_image(f["src"], f.get("legende", "")) for f in figs if f.get("src"))


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
    """Manifeste reconstruit d'après le disque (build/pdf_status.py) : jamais de PDF fantôme."""
    manifest, _ = pdf_status.reconcile(write=False)
    return manifest


def pdfs_for_doc(manifest: dict, allowed_kinds, matiere: str, type_doc: str, doc_slug: str, prefer: str = None):
    """Liste [(label, url)] des PDF PUBLIABLES (profil actif) de ce document,
    triés enonce -> aides -> corrige -> autre. Un PDF absent du disque ou non
    autorisé par le profil (ex: corrigé en `avant_seance`, fiche enseignant)
    n'a JAMAIS de lien."""
    found = [(name, e) for name, e in manifest.items()
             if e.get("matiere") == matiere and e.get("type_doc") == type_doc and e.get("doc") == doc_slug
             and pdf_status.is_published(e, allowed_kinds)]
    order = pdf_status.KIND_ORDER
    # Ordre FIXE : Énoncé, Aides, Corrigé, (autres), Fiche enseignant -- quel que soit le profil.
    found.sort(key=lambda ne: (order.index(ne[1].get("kind", "autre")) if ne[1].get("kind") in order else 9, ne[0]))
    kinds_count = {}
    for _, e in found:
        kinds_count[e.get("kind")] = kinds_count.get(e.get("kind"), 0) + 1
    out = []
    for name, e in found:
        label = KIND_LABEL.get(e.get("kind"), "PDF")
        if kinds_count[e.get("kind")] > 1:
            label += f" ({name})"
        out.append((label, f"/pdfs/{e['pdf']}"))
    return out


def a_blank(label: str, url: str) -> str:
    """Lien qui s'ouvre dans un NOUVEL onglet (target=_blank). Le Markdown n'a pas de
    syntaxe pour ça : on écrit le <a> en HTML (Quartz accepte le HTML brut)."""
    return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'


FILE_ICONS = {".xlsx": "📊", ".xlsm": "📊", ".xls": "📊", ".ods": "📊", ".csv": "📊", ".zip": "🗜️",
              ".ipynb": "🐍", ".py": "🐍", ".docx": "📝", ".pptx": "🖼️"}


def pdf_line(pdfs: list) -> str:
    """PDF construits + fichiers rattachés : une icône par type de fichier (📄 par défaut)."""
    return " · ".join(a_blank(f"{FILE_ICONS.get(Path(url).suffix.lower(), '📄')} {label}", url) for label, url in pdfs)


def merge_links(*lists) -> list:
    """Concatène des listes [(label, url)] sans doublon d'adresse (ordre conservé)."""
    seen, out = set(), []
    for lst in lists:
        for label, url in lst:
            if url not in seen:
                seen.add(url)
                out.append((label, url))
    return out


def qcm_links_block(matiere: str, chapitre_ids, intro: str = "**S'entraîner (QCM)**") -> str:
    """Lien + QR code (accès libre, scannable à la maison) pour chaque chapitre en accès libre."""
    chaps = {c["id"]: c for c in qcm_data.chapitres(matiere)}
    liens = []
    for cid in dict.fromkeys(chapitre_ids):
        c = chaps.get(cid)
        if not c:
            print(f"   ⚠️  qcm.liens : chapitre « {cid} » inconnu dans la matière {matiere}")
            continue
        if qcm_data.is_libre(matiere, cid):
            plur = "s" if c["n"] > 1 else ""
            liens.append(qcm_data.qcm_link_html(matiere, cid, f"{c['titre']} — {c['n']} question{plur}"))
    return "\n\n".join([intro] + liens) if liens else ""


# ----------------------------------------------------------------------
# Rendu td-like (exercices)
# ----------------------------------------------------------------------

def render_encadre_md(enc: dict) -> str:
    """Rendu web d'un `encadre` (style \\EncadreDeux en LaTeX) : callout
    Obsidian, titre = "type — titre" (les deux champs texte de
    \\EncadreDeux), replié par défaut comme les autres compléments."""
    titre = f"{enc.get('type', '')} — {enc.get('titre', '')}".strip(" —")
    return callout("info", f"📦 {titre}", enc.get("contenu", ""), "encadre")


def render_question_md(q: dict, opts: dict = None) -> str:
    opts = opts or {}
    parts = [q["enonce"].strip()]
    if q.get("figure"):
        parts.append(figures_md(q["figure"]))
    if q.get("animation"):
        parts.append(render_animation_block(q["animation"]))
    parts.extend(render_rubriques(q, opts, "debut"))          # prérequis, objectifs, point de cours...
    if q.get("coup_de_pouce"):
        parts.append(callout("tip", "💡 Coup de pouce", q["coup_de_pouce"], "coup_de_pouce"))
    parts.extend(apl_callouts(q.get("aller_plus_loin")))
    if q.get("correction"):
        parts.append(callout("success", "✅ Correction", q["correction"], "correction"))
    if q.get("solution"):
        parts.append(callout("example", "📝 Solution détaillée", q["solution"], "solution"))
    parts.extend(render_rubriques(q, opts, "fin"))            # écueils, conseils d'animation, bilan...
    if q.get("encadre"):
        parts.append(render_encadre_md(q["encadre"]))
    return "\n\n".join(parts)


def metadonnees_md(ex: dict) -> str:
    """Ligne de repères d'un exercice (show_metadonnees) : indispensable, difficulté, durée, type -- comme dans le
    titre des PDF. Chaîne vide si l'exercice n'a pas de `metadonnees:`."""
    md = ex.get("metadonnees") or {}
    bits = []
    if md.get("indispensable") is True:
        bits.append("⭐ Indispensable")
    if md.get("difficulte"):
        try:
            n = max(0, min(5, int(md["difficulte"])))
            bits.append(f"Difficulté {'●' * n}{'○' * (5 - n)}")
        except (TypeError, ValueError):
            bits.append(f"Difficulté {md['difficulte']}")
    if md.get("duree_estimee"):
        bits.append(f"⏱ {str(md['duree_estimee']).strip()}")
    if md.get("type_exercice"):
        bits.append(f"Type : {clean_text_for_web(str(md['type_exercice'])).strip()}")
    return "*" + " · ".join(bits) + "*" if bits else ""


def render_exercice_md(ex: dict, voir_aussi: list, opts: dict = None, extras_fin: list = None) -> str:
    t_fr, t_en = title_parts(ex["intitule"])
    out = [f"### Exercice {ex['numero']}. {t_fr}" + (f" {en_span(t_en)}" if t_en else "")
           + (" *(facultatif)*" if ex.get("facultatif") else "")]
    opts = opts or {}
    if opts.get("show_metadonnees") and metadonnees_md(ex):
        out.append(metadonnees_md(ex))                            # repères : indispensable · difficulté · durée · type
    out.append(ex.get("enonce_intro", "").strip())
    if ex.get("figure"):
        out.append(figures_md(ex["figure"]))
    if ex.get("animation"):
        out.append(render_animation_block(ex["animation"]))
    out.extend(render_rubriques(ex, opts, "debut"))           # rubriques de l'EXERCICE (avant les questions)
    if opts.get("show_coup_de_pouce") and ex.get("coup_de_pouce"):
        out.append(callout("tip", "💡 Coup de pouce", ex["coup_de_pouce"], "coup_de_pouce"))

    for item in ex.get("contenu", []):
        if item["kind"] == "intro":
            out.append(item["enonce"])
        elif item["kind"] == "single":
            out.append(f"**{item.get('id','')}.** " + render_question_md(item, opts))
        elif item["kind"] == "group":
            out.append(f"**{item['label']}.**")
            for i, sq in enumerate(item["subquestions"]):
                letter = chr(ord("a") + i)
                out.append(f"  **{letter})** " + render_question_md(sq, opts))

    out.extend(render_rubriques(ex, opts, "fin"))             # rubriques de l'EXERCICE (après les questions)
    apl = filter_apl(ex.get("aller_plus_loin"), opts.get("aller_plus_loin_niveaux"))
    if apl:
        out.extend(apl_callouts(apl))
    out.extend(extras_fin or [])                              # QCM liés à l'exercice

    if voir_aussi:
        links = " · ".join(f"[[{path}|{label}]]" for path, label in voir_aussi)
        out.append(callout("note", "🔗 Voir aussi", links, "info_td"))

    return "\n\n".join(p for p in out if p.strip())


def render_qcm_md(qcm_list: list, exercice_paths: dict, matiere: str, extra_chaps=()) -> str:
    """Questions « réveil » (debut/milieu/fin) détaillées ; toutes les autres (entraînement…)
    ne sont pas listées (un chapitre peut en avoir des dizaines) : lien + QR code d'accès libre."""
    if not qcm_list and not extra_chaps:
        return ""
    blocks = ["## QCM de réveil liés à ce document\n"] if qcm_list else ["## QCM liés à ce document\n"]
    moment_titles = {"debut": "🌅 Début de cours", "milieu": "🔄 Milieu de cours", "fin": "🌇 Fin de cours"}
    appli = a_blank("l'appli QCM", qcm_data.qcm_url(matiere, absolute=False))
    for q in [q for q in qcm_list if q.get("moment") in moment_titles]:
        choices = "\n".join(f"- {c['texte']}" for c in q["choix"])
        mw = qcm_data.media_for_web(q)
        media = [figures_md(mw["figures"])] if mw["figures"] else []
        if mw["animation"]:
            media.append(render_animation_block(mw["animation"]))
        media_md = ("\n\n".join(media) + "\n\n") if media else ""
        body = (f"**{q['question']}**\n\n{media_md}{choices}\n\n"
                f"*Réponds en direct sur {appli} (QR code affiché en cours).*")
        # clé (matiere, id) : « td1 » existe dans plusieurs matières, le lien ne
        # doit jamais partir vers l'exercice d'une autre matière
        target = exercice_paths.get((matiere, q.get("lie_a")))
        if target:
            body += f"\n\nEn lien avec [[{target}|cet exercice]]."
        elif q.get("lie_a"):
            print(f"   ⚠️  QCM {q.get('id')} : lie_a « {q['lie_a']} » introuvable dans la matière {matiere}")
        blocks.append(callout("question", f"QCM — {moment_titles[q['moment']]}", body, "qcm"))
    # accès libre : un lien + QR par chapitre représenté dans ce document (ordre d'apparition)
    titres = {}
    for q in qcm_list:
        if q.get("chapitre"):
            titres.setdefault(q["chapitre"], q.get("chapitre_titre") or f"Chapitre {q['chapitre']}")
    n_questions = len(qcm_list)
    if extra_chaps:                                     # chapitres rattachés par config.yaml > qcm > liens
        all_chaps = {c["id"]: c for c in qcm_data.chapitres(matiere)}
        for cid in extra_chaps:
            if cid in all_chaps and cid not in titres:
                titres[cid] = all_chaps[cid]["titre"]
                n_questions += all_chaps[cid]["n"]
    liens = [qcm_data.qcm_link_html(matiere, c, t) for c, t in titres.items() if qcm_data.is_libre(matiere, c)]
    if liens:       # rien du tout si ces chapitres ne sont pas en accès libre (config.yaml)
        blocks.append("\n\n".join([f"**S'entraîner librement** ({n_questions} question(s) liées à ce document) :"] + liens))
    return "\n\n".join(blocks)


def build_tag_index(all_exercices):
    idx = defaultdict(list)
    for matiere, type_doc, base, ex in all_exercices:
        for tag in ex.get("cours_rattache", []):
            idx[tag].append((matiere, type_doc, ex["slug"], ex["numero"], ex["intitule"], base))
    return idx


def voir_aussi_for(ex, tag_index, self_key):
    """Liens « voir aussi » entre exercices partageant un tag cours_rattache.
    Chemins COMPLETS depuis la racine de content/ (namespace inclus) : les liens
    entre matières fonctionnent, et le graphe Quartz reçoit bien ces arêtes."""
    seen = {}
    for tag in ex.get("cours_rattache", []):
        for (matiere, type_doc, ex_slug, numero, intitule, base) in tag_index.get(tag, []):
            key = (matiere, type_doc, base, ex_slug)
            if key == self_key or key in seen:
                continue
            seen[key] = (f"{base}/ex{numero}-{slugify(title_parts(intitule)[0])}", f"Exercice {numero} — {title_parts(intitule)[0]}")
    return list(seen.values())


class Registry:
    """Fichiers générés par CE script, par matière. Sert à supprimer les pages
    « défaites » (exercice renommé/retiré, document passé en publier:false...)
    sans JAMAIS toucher à tes notes écrites à la main dans Quartz."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir.resolve()
        self.path = self.out_dir.parent / GENERATED_REGISTRY
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.data = {}
        self.current = defaultdict(set)

    def write(self, matiere: str, rel: str, text: str):
        full = self.out_dir / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text, encoding="utf-8")
        self.current[matiere].add(rel)

    def prune(self, matiere: str) -> list:
        removed = []
        for rel in sorted(set(self.data.get(matiere, [])) - self.current[matiere]):
            f = (self.out_dir / rel).resolve()
            if self.out_dir in f.parents and f.is_file():
                f.unlink()
                removed.append(rel)
                d = f.parent                       # remonte en supprimant les dossiers vides
                while d != self.out_dir and d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
                    d = d.parent
        self.data[matiere] = sorted(self.current[matiere])
        return removed

    def save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")


def sujets_line(ids, sujets, own_ns: str) -> str:
    """Wikilinks vers les pages-sujets (data/graph/sujets.yaml) -> arêtes du graphe
    Quartz entre un document et ses sujets. Les sujets dont la page est la
    matière elle-même sont omis (déjà liée par le fil d'Ariane)."""
    links = []
    for sid in ids or []:
        s = sujets.get(sid)
        if not s:
            print(f"   ⚠️  sujet inconnu « {sid} » (absent de data/graph/sujets.yaml)")
            continue
        if s["quartz_path"] != own_ns:
            links.append(f"[[{s['quartz_path']}|{s['nom']}]]")
    return ("**Sujets :** " + " · ".join(links)) if links else ""


def doc_profile(ctx, matiere, type_doc, doc_slug):
    name = resolve_profile(matiere, type_doc, doc_slug, forced=ctx["forced"])
    return name, ctx["profiles"][name]


def export_td_doc(ctx, matiere, type_doc, doc_slug, ns, matiere_meta):
    manifest = ctx["manifest"]
    pname, opts = doc_profile(ctx, matiere, type_doc, doc_slug)
    allowed = set(opts.get("pdf_publies", ["enonce"]))
    meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
    chapitre_slug = chapitre_slug_of(meta)
    t_fr, t_en = title_parts(meta["titre"])
    chap_fr, chap_en = title_parts(meta.get("chapitre_cours", ""))
    base = td_base(ns, type_doc, meta)
    if base in ctx["used_dirs"]:                    # deux documents de même titre ne s'écrasent plus
        base += f"-{slugify(meta['id'])}"
        print(f"   ⚠️  titre déjà utilisé, dossier renommé : {base}")
    ctx["used_dirs"].add(base)

    pdfs = merge_links(pdfs_for_doc(manifest, allowed, matiere, type_doc, doc_slug),
                       fichiers_joints.links_for(matiere, type_doc, doc_slug, None, opts, manifest, warn=ctx["warn"], pname=pname))
    sujet_ids = meta.get("sujets") or matiere_meta.get("sujets") or []
    own = ctx["registry"]
    ctx_sujets = sujets_line(sujet_ids, ctx["sujets"], ns)

    seance = f"Séance {meta.get('seance', '?')}" + (f" · {en_span(chap_en)}" if chap_en else "")
    index_lines = [
        "---", f"title: {fm_title(t_fr)}", "tags:", f"  - {type_doc}", f"  - {chapitre_slug}", "---", "",
        f"[[{ns}/index|⬅ {matiere_meta['nom']}]]", "",
    ]
    if t_en:
        index_lines += [f"<p>{en_span(t_en)}</p>", ""]
    index_lines += [callout("info", f"ℹ️ {chap_fr}", seance, "info_td"), ""]
    if pdfs:
        index_lines += [pdf_line(pdfs), ""]
    if ctx_sujets:
        index_lines += [ctx_sujets, ""]
    debut = render_rubriques(meta, opts, "debut")               # rubriques du DOCUMENT (_meta.yaml)
    if opts.get("show_coup_de_pouce") and meta.get("coup_de_pouce"):
        debut.append(callout("tip", "💡 Coup de pouce", meta["coup_de_pouce"], "coup_de_pouce"))
    if debut:
        index_lines += ["\n".join(debut), "", "## Exercices", ""]

    overrides = []
    for ex in exercices:
        ex_pname = resolve_profile(matiere, type_doc, doc_slug, ex_slug=ex["slug"], forced=ctx["forced"])
        if ex_pname != pname:
            overrides.append(f"{ex['slug']}={ex_pname}")
        ex_opts = ctx["profiles"][ex_pname]
        ex_filtered = clean_exercice_for_web(apply_visibility_to_exercice(enrich_media_paths(ex), ex_opts))
        self_key = (matiere, type_doc, base, ex["slug"])
        voir_aussi = voir_aussi_for(ex, ctx["tag_index"], self_key)
        ex_files = fichiers_joints.links_for(matiere, type_doc, doc_slug, ex["slug"], ex_opts, manifest, warn=ctx["warn"], pname=ex_pname)
        ex_chaps = qcm_data.chapitres_lies(matiere, type_doc, doc_slug, ex["slug"]) + [
            q["chapitre"] for q in ctx["qcm_all"](matiere) if q.get("lie_a") == f"{meta['id']}_ex{ex['numero']}"]
        ex_qcm = qcm_links_block(matiere, ex_chaps, "**S'entraîner sur cet exercice (QCM)**") if ex_chaps else ""
        md_body = render_exercice_md(ex_filtered, voir_aussi, ex_opts, [ex_qcm] if ex_qcm else None)
        e_fr, e_en = title_parts(ex["intitule"])
        fname = f"ex{ex['numero']}-{ex_slug_of(ex)}.md"

        breadcrumb = f"[[{base}/index|⬅ Retour]]"
        if pdfs or ex_files:
            breadcrumb += " · " + pdf_line(merge_links(pdfs, ex_files))
        ex_title = f"Exercice {ex['numero']} — {e_fr}"
        frontmatter = (
            "---\n" f"title: {fm_title(ex_title)}\n"
            "tags:\n" f"  - {type_doc}\n" f"  - {chapitre_slug}\n" "---\n\n" f"{breadcrumb}\n\n"
            + (f"<p>{en_span(e_en)}</p>\n\n" if e_en else "")
        )
        own.write(matiere, f"{base}/{fname}", frontmatter + md_body + "\n")
        index_lines.append(f"- [[{base}/{fname[:-3]}|Exercice {ex['numero']} — {e_fr}]]" + (f" {en_span(e_en)}" if e_en else ""))

    doc_keys = {meta["id"], doc_slug}                           # `td:` d'un QCM : id du document OU nom du dossier
    qcm_td = [q for q in ctx["qcm_all"](matiere) if q.get("td") in doc_keys]
    qcm_md = render_qcm_md(qcm_td, ctx["exercice_paths"], matiere, qcm_data.chapitres_lies(matiere, type_doc, doc_slug))
    if qcm_md:
        index_lines += ["", qcm_md]
    fin = render_rubriques(meta, opts, "fin")                   # écueils, conseils d'animation, bilan, liens...
    apl = filter_apl(meta.get("aller_plus_loin"), opts.get("aller_plus_loin_niveaux"))
    if apl:
        fin.extend(apl_callouts(apl))
    if fin:
        index_lines += ["", "\n".join(fin)]

    own.write(matiere, f"{base}/index.md", "\n".join(index_lines) + "\n")
    print(f"   -> {base}/ ({len(exercices)} exercices, {len(pdfs)} PDF publié(s)) [profil : {pname}"
          + (f" ; exceptions : {', '.join(overrides)}" if overrides else "") + "]")
    return meta, pdfs, base


# ----------------------------------------------------------------------
# Rendu cours-like (sections de lecture)
# ----------------------------------------------------------------------

def render_section_md(sec: dict, opts: dict = None) -> str:
    opts = opts or {}
    s_fr, s_en = title_parts(sec["titre"])
    parts = [f"## {sec['numero']}. {s_fr}" + (f" {en_span(s_en)}" if s_en else ""), sec.get("contenu", "").strip()]
    if sec.get("figure"):
        parts.append(figures_md(sec["figure"]))
    if sec.get("animation"):
        parts.append(render_animation_block(sec["animation"]))
    parts.extend(render_rubriques(sec, opts, "debut"))
    if sec.get("remarque"):
        parts.append(callout("info", "💡 Remarque", sec["remarque"], "remarque"))
    parts.extend(render_rubriques(sec, opts, "fin"))
    parts.extend(apl_callouts(sec.get("aller_plus_loin")))
    if sec.get("encadre"):
        parts.append(render_encadre_md(sec["encadre"]))
    return "\n\n".join(p for p in parts if p.strip())


def export_cours_doc(ctx, matiere, doc_slug, ns, matiere_meta, type_doc="cours"):
    manifest = ctx["manifest"]
    pname, opts = doc_profile(ctx, matiere, type_doc, doc_slug)
    allowed = set(opts.get("pdf_publies", ["enonce"]))
    doc = load_cours(matiere, doc_slug, type_doc=type_doc)
    doc_filtered = clean_cours_for_web(apply_visibility_to_cours(enrich_cours_media(doc), opts))
    pdfs = merge_links(pdfs_for_doc(manifest, allowed, matiere, type_doc, doc_slug),
                       fichiers_joints.links_for(matiere, type_doc, doc_slug, None, opts, manifest, warn=ctx["warn"], pname=pname))
    c_fr, c_en = title_parts(doc["titre"])

    body_parts = [f"[[{ns}/index|⬅ {matiere_meta['nom']}]]"]
    if c_en:
        body_parts.append(f"<p>{en_span(c_en)}</p>")
    if doc.get("sous_titre"):
        body_parts.append(f"*{doc['sous_titre']}*")
    if pdfs:
        body_parts.append(pdf_line(pdfs))
    sl = sujets_line(doc.get("sujets") or matiere_meta.get("sujets"), ctx["sujets"], ns)
    if sl:
        body_parts.append(sl)
    body_parts.extend(render_rubriques(doc, opts, "debut"))
    for sec in doc_filtered.get("sections", []):
        body_parts.append(render_section_md(sec, opts))
    body_parts.extend(render_rubriques(doc, opts, "fin"))
    chaps = qcm_data.chapitres_lies(matiere, type_doc, doc_slug) + [
        q["chapitre"] for q in ctx["qcm_all"](matiere) if q.get("td") in {doc.get("id"), doc_slug}]
    qb = qcm_links_block(matiere, chaps, "**S'entraîner sur ce cours (QCM)**") if chaps else ""
    if qb:
        body_parts.append(qb)

    frontmatter = "\n".join(["---", f"title: {fm_title(c_fr)}", "tags:", f"  - {type_doc}", "---"])
    rel = f"{ns}/{TYPE_LABELS[type_doc]}/{doc_slug}.md"
    ctx["registry"].write(matiere, rel, frontmatter + "\n\n" + "\n\n".join(body_parts) + "\n")
    print(f"   -> {rel} ({len(pdfs)} PDF/fichier(s) publié(s)) [profil : {pname}]")
    return doc, pdfs, rel[:-3]


# ----------------------------------------------------------------------
# Export d'une matière entière
# ----------------------------------------------------------------------

def export_matiere(ctx, matiere):
    meta = load_matiere_meta(matiere)
    ns = meta["quartz_namespace"]
    sections_index = ["---", f"title: {fm_title(meta['nom'])}", "tags:", "  - matiere", "---", "",
                      (meta.get("description") or "").strip(), ""]

    for type_doc, spec in doc_types().items():                 # ordre = celui de config.yaml > types_documents
        if spec["forme"] == "exercices":
            docs = list_docs_td_like(matiere, type_doc)
        else:
            docs = list_docs_cours(matiere, type_doc)
        if not docs:
            continue
        sections_index.append(f"## {spec['label']}\n")
        for doc_slug in docs:
            if spec["forme"] == "exercices":
                d_meta, pdfs, base = export_td_doc(ctx, matiere, type_doc, doc_slug, ns, meta)
                link_target = f"{base}/index"
            else:
                d_meta, pdfs, link_target = export_cours_doc(ctx, matiere, doc_slug, ns, meta, type_doc)
            l_fr, l_en = title_parts(d_meta["titre"])
            line = f"- [[{link_target}|{l_fr}]]" + (f" {en_span(l_en)}" if l_en else "")
            if pdfs:
                line += " (" + ", ".join(a_blank(label, url) for label, url in pdfs) + ")"
            sections_index.append(line)
        sections_index.append("")

    chaps = qcm_data.chapitres_libres(matiere)      # config.yaml > qcm > acces_libre
    if chaps:
        # Entraînement libre : un lien (+ QR code scannable si qcm.base_url est renseigné) par chapitre
        sections_index += ["## QCM d'entraînement\n",
                           f"{sum(c['n'] for c in chaps)} questions, en accès libre (sans compte), "
                           "ou en direct pendant le cours.\n"]
        if len(chaps) > 1:
            sections_index += [qcm_data.qcm_link_html(matiere, "all", "Toute la matière"), ""]
        for c in chaps:
            plur = "s" if c["n"] > 1 else ""
            sections_index += [qcm_data.qcm_link_html(matiere, c["id"], f"{c['titre']} — {c['n']} question{plur}"), ""]
        if not qcm_data.load_qcm_config().get("base_url"):
            print("   ⚠️  qcm.base_url vide dans build/config.yaml : pas de QR code dans Quartz.")
    sl = sujets_line(meta.get("sujets"), ctx["sujets"], ns)
    if sl:
        sections_index += [sl, ""]

    ctx["registry"].write(matiere, f"{ns}/index.md", "\n".join(sections_index) + "\n")
    removed = ctx["registry"].prune(matiere)
    for rel in removed:
        print(f"   🗑️  page défaite supprimée : {rel}")


def _qcm_loader():
    """Questions QCM d'une matière, chargées une seule fois par export (utilisées par chaque page)."""
    cache = {}

    def get(matiere):
        if matiere not in cache:
            cache[matiere] = load_all_qcm(matiere)
        return cache[matiere]
    return get


def _profiles_in_publication() -> set:
    """Tous les noms de profils cités dans publication: (défauts, documents, exercices)."""
    pub, names = publication_config(), set()
    if pub.get("defaut"):
        names.add(pub["defaut"])
    for m in (pub.get("matieres") or {}).values():
        if m.get("defaut"):
            names.add(m["defaut"])
        for ty in doc_types():
            for entry in (m.get(ty) or {}).values():
                if isinstance(entry, str):
                    names.add(entry)
                elif isinstance(entry, dict):
                    if entry.get("profil") or entry.get("etat"):
                        names.add(entry.get("profil") or entry.get("etat"))
                    names.update((entry.get("exercices") or {}).values())
    return {expand_profile(n) for n in names}              # un état compte pour son profil


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True,
                   help="un profil de web/visibility_profiles.yaml (forcé partout) ou « auto » (d'après config.yaml)")
    p.add_argument("--matiere", default=None, help="une seule matière ; défaut : toutes")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="dossier content/ de Quartz")
    args = p.parse_args()

    profiles = load_visibility_profiles()
    forced = None if args.profile == "auto" else expand_profile(args.profile)
    if forced and forced not in profiles:
        print(f"!! profil inconnu : {args.profile} (disponibles : auto, {', '.join(profiles)})")
        return 1
    bad = sorted({p for p in _profiles_in_publication() if p not in profiles})
    if bad and not forced:
        print(f"!! publication: de config.yaml cite des profils inconnus : {bad} (disponibles : {', '.join(profiles)})")
        return 1

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    matieres = [args.matiere] if args.matiere else list_matieres()

    # Garde-fou : deux matières ne doivent jamais partager un namespace (les
    # index.md s'écraseraient -- c'était le cas pour 3 de tes matières).
    seen_ns = {}
    for m in list_matieres():
        ns = load_matiere_meta(m)["quartz_namespace"]
        if ns in seen_ns:
            print(f"!! quartz_namespace « {ns} » utilisé par {seen_ns[ns]} ET {m} -- corrige _matiere.yaml")
            return 1
        seen_ns[ns] = m

    # Index « voir aussi » (tags cours_rattache) et chemins des exercices pour
    # les QCM (lie_a), sur toutes les matières : liens croisés entre matières.
    all_exercices, exercice_paths, used = [], {}, set()
    for matiere in matieres:
        ns = load_matiere_meta(matiere)["quartz_namespace"]
        for type_doc in exercise_types():
            for doc_slug in list_docs_td_like(matiere, type_doc):
                td_meta, exercices = load_td(matiere, doc_slug, type_doc=type_doc)
                base = td_base(ns, type_doc, td_meta)
                for ex in exercices:
                    all_exercices.append((matiere, type_doc, base, ex))
                    exercice_paths[(matiere, f"{td_meta['id']}_ex{ex['numero']}")] = f"{base}/ex{ex['numero']}-{ex_slug_of(ex)}"
    sujets, _ = load_sujets_graph()
    ctx = {
        "profiles": profiles, "forced": forced,
        "manifest": load_pdf_manifest(), "registry": Registry(out_dir),
        "sujets": sujets, "tag_index": build_tag_index(all_exercices),
        "exercice_paths": exercice_paths, "used_dirs": used,
        "warn": lambda m: print(f"   ⚠️  {m}"),
        "qcm_all": _qcm_loader(),
    }
    prof_names = {forced} if forced else _profiles_in_publication()
    teacher = sorted(n for n in prof_names if n in profiles and "prof" in profile_audiences(profiles[n]))
    if teacher:
        print(f"   ⚠️  profil(s) {', '.join(teacher)} : ce site affichera le contenu ENSEIGNANT (objectifs, écueils, "
              "conseils d'animation, bilan, fiches, fichiers `public: prof`). À réserver à un site privé / local ; "
              "pour un site public, utilise all_eleve.")

    print(f"-- Export Markdown, profil '{args.profile}'"
          + (" (par document, d'après config.yaml)" if not forced else " (forcé pour tous les documents)") + f" -> {out_dir}")
    if not ctx["manifest"]:
        print("   ⚠️  aucun PDF présent dans build/output -- pas de liens PDF (lance build/build.py).")
    for matiere in matieres:
        print(f" [{matiere}]")
        export_matiere(ctx, matiere)
    ctx["registry"].save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
