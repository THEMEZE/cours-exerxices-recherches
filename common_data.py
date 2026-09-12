"""
Chargement + normalisation des données data/matieres/**, partagé par :
  - build/build.py            (PDF)
  - web/export_json.py        (site interactif / carrousel)
  - web/export_markdown.py    (site Quartz)
  - web/build_subject_links.py (graphe de sujets -> liens Quartz)
  - notebooks/build_notebooks.py

Structure générale (voir data/SCHEMA.md pour le détail) :

    data/matieres/<matiere_slug>/
        _matiere.yaml
        td/<doc_slug>/_meta.yaml + ex*.yaml      (type "td" -- dossier de fichiers)
        tp/<doc_slug>/_meta.yaml + ex*.yaml       (type "tp" -- même format que "td")
        cours/<doc_slug>.yaml                     (type "cours" -- fichier unique, sections)
        qcm/*.yaml

    data/graph/sujets.yaml                        (graphe des sujets, transverse aux matières)

Toute la logique de regroupement des questions (a/b/c), de contrôle de
visibilité (coup de pouce / correction / solution / aller plus loin par
niveau) et de nettoyage pour le web vit ici pour ne jamais diverger entre
les différentes sorties.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "matieres"
GRAPH_FILE = ROOT / "data" / "graph" / "sujets.yaml"

NIVEAU_LABELS = {
    "lycee": "Lycée",
    "cpge": "CPGE",
    "prepa": "CPGE",
    "licence": "Licence",
    "master": "Master",
    "doctorat": "Doctorat",
    "agregation": "Agrégation",
}


def niveau_label(niveau: str) -> str:
    return NIVEAU_LABELS.get(niveau, niveau)


# ----------------------------------------------------------------------
# Matières
# ----------------------------------------------------------------------

def list_matieres():
    if not DATA_DIR.exists():
        return []
    return sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir() and (p / "_matiere.yaml").exists())


def load_matiere_meta(matiere_slug: str) -> dict:
    return yaml.safe_load((DATA_DIR / matiere_slug / "_matiere.yaml").read_text(encoding="utf-8"))


def _type_dir(matiere_slug: str, type_doc: str) -> Path:
    return DATA_DIR / matiere_slug / type_doc


# ----------------------------------------------------------------------
# Documents "td-like" (td/, tp/) : un dossier par document, un _meta.yaml
# + plusieurs fichiers ex*.yaml (questions groupables a/b/c, corrections...)
# ----------------------------------------------------------------------

def list_docs_td_like(matiere_slug: str, type_doc: str = "td"):
    d = _type_dir(matiere_slug, type_doc)
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and (p / "_meta.yaml").exists())


def load_td(matiere_slug: str, doc_slug: str, type_doc: str = "td", only_exercices=None):
    """Retourne (meta, [exercices]) pour un document td-like, exercices dans
    l'ordre déclaré dans _meta.yaml (exercices_ordre)."""
    doc_dir = _type_dir(matiere_slug, type_doc) / doc_slug
    meta = yaml.safe_load((doc_dir / "_meta.yaml").read_text(encoding="utf-8"))
    meta["matiere"] = matiere_slug
    meta["type_doc"] = type_doc
    meta["doc_slug"] = doc_slug

    order = only_exercices or meta["exercices_ordre"]
    exercices = []
    for numero, ex_slug in enumerate(order, start=1):
        ex_path = doc_dir / f"{ex_slug}.yaml"
        ex = yaml.safe_load(ex_path.read_text(encoding="utf-8"))
        ex["numero"] = numero
        ex["slug"] = ex_slug
        ex["contenu"] = group_questions(ex.get("questions", []))
        exercices.append(ex)
    return meta, exercices


# ----------------------------------------------------------------------
# Documents "cours-like" (cours/) : un seul fichier YAML, avec une liste
# `sections:` de prose (pas de questions/corrections -- c'est un cours, pas
# un TD). Chaque section peut avoir : contenu, figure, animation, remarque
# (toujours visible, jamais masquée par un profil), aller_plus_loin (filtré
# par niveau comme pour les td).
# ----------------------------------------------------------------------

def list_docs_cours(matiere_slug: str, type_doc: str = "cours"):
    d = _type_dir(matiere_slug, type_doc)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_cours(matiere_slug: str, doc_slug: str, type_doc: str = "cours") -> dict:
    path = _type_dir(matiere_slug, type_doc) / f"{doc_slug}.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["matiere"] = matiere_slug
    doc["type_doc"] = type_doc
    doc["doc_slug"] = doc_slug
    for i, sec in enumerate(doc.get("sections", [])):
        sec["numero"] = i + 1
    return doc


# ----------------------------------------------------------------------
# QCM
# ----------------------------------------------------------------------

def load_all_qcm(matiere_slug: str = None, td_filter: str = None):
    items = []
    matieres = [matiere_slug] if matiere_slug else list_matieres()
    for m in matieres:
        qcm_dir = DATA_DIR / m / "qcm"
        if not qcm_dir.exists():
            continue
        for path in sorted(qcm_dir.glob("*.yaml")):
            docs = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            for d in docs:
                if td_filter and d.get("td") != td_filter:
                    continue
                d["matiere"] = m
                items.append(d)
    return items


# ----------------------------------------------------------------------
# Graphe des sujets (data/graph/sujets.yaml)
# ----------------------------------------------------------------------

def load_sujets_graph():
    """Retourne (sujets: {id: {...}}, liens: [{de, a, poids, type, note}])."""
    if not GRAPH_FILE.exists():
        return {}, []
    doc = yaml.safe_load(GRAPH_FILE.read_text(encoding="utf-8")) or {}
    sujets = {s["id"]: s for s in doc.get("sujets", [])}
    liens = doc.get("liens", [])
    return sujets, liens


def liens_pour_sujet(sujet_id: str, liens: list, seuil: float = 0.0):
    """Retourne trois listes pour un sujet donné : (parent, enfants, associes),
    chacune triée par |poids| décroissant, en ne gardant que |poids| >= seuil."""
    parent, enfants, associes = [], [], []
    for lien in liens:
        poids = lien.get("poids", 0)
        if abs(poids) < seuil:
            continue
        if lien["type"] == "parent":
            if lien["a"] == sujet_id:
                parent.append(lien)
            elif lien["de"] == sujet_id:
                enfants.append(lien)
        elif lien["type"] == "associe":
            if lien["de"] == sujet_id:
                associes.append(dict(lien, autre=lien["a"]))
            elif lien["a"] == sujet_id:
                associes.append(dict(lien, autre=lien["de"]))
    associes.sort(key=lambda l: -abs(l.get("poids", 0)))
    return parent, enfants, associes


# ----------------------------------------------------------------------
# Regroupement des sous-questions a/b/c sous un même numéro (td-like)
# ----------------------------------------------------------------------

def group_questions(questions):
    items = []
    groups = {}
    for q in questions:
        if q.get("is_intro_only"):
            items.append({"kind": "intro", "enonce": q["enonce"]})
            continue
        parent = q.get("parent")
        if parent:
            if parent not in groups:
                group_item = {"kind": "group", "label": parent, "subquestions": []}
                groups[parent] = group_item
                items.append(group_item)
            groups[parent]["subquestions"].append(q)
        else:
            items.append({"kind": "single", **q})
    return items


# ----------------------------------------------------------------------
# Contrôle de visibilité -- le point commun entre PDF, JSON et Quartz.
# ----------------------------------------------------------------------

def apply_visibility(question: dict, opts: dict) -> dict:
    q = dict(question)
    if not opts.get("show_coup_de_pouce"):
        q.pop("coup_de_pouce", None)
    if not opts.get("show_correction"):
        q.pop("correction", None)
    if not opts.get("show_solution"):
        q.pop("solution", None)

    niveaux_gardes = set(opts.get("aller_plus_loin_niveaux", []))
    if "aller_plus_loin" in q:
        apl = q["aller_plus_loin"]
        if isinstance(apl, dict):
            # Ancien format dictionnaire
            apl_filt = {k: v for k, v in apl.items() if k in niveaux_gardes}
            if apl_filt:
                q["aller_plus_loin"] = apl_filt
            else:
                q.pop("aller_plus_loin", None)
        elif isinstance(apl, list):
            # Nouveau format liste d'objets
            apl_filt = [item for item in apl if item.get("niveau") in niveaux_gardes]
            if apl_filt:
                q["aller_plus_loin"] = apl_filt
            else:
                q.pop("aller_plus_loin", None)

    if not opts.get("show_figure", True):
        q.pop("figure", None)
    if not opts.get("show_animation_note", True):
        q.pop("animation", None)
    return q


def apply_visibility_to_exercice(ex: dict, opts: dict) -> dict:
    ex2 = dict(ex)
    if not opts.get("show_figure", True):
        ex2.pop("figure", None)
    if not opts.get("show_animation_note", True):
        ex2.pop("animation", None)

    def filt(item):
        if item["kind"] == "single":
            return apply_visibility(item, opts)
        if item["kind"] == "group":
            g = dict(item)
            g["subquestions"] = [apply_visibility(sq, opts) for sq in item["subquestions"]]
            return g
        return item

    ex2["contenu"] = [filt(it) for it in ex2.get("contenu", [])]
    return ex2


def apply_visibility_to_cours(doc: dict, opts: dict) -> dict:
    """Équivalent de apply_visibility_to_exercice pour un document 'cours'."""
    doc2 = dict(doc)
    niveaux_gardes = set(opts.get("aller_plus_loin_niveaux", []))

    def filt_section(sec):
        s = dict(sec)
        if not opts.get("show_figure", True):
            s.pop("figure", None)
        if not opts.get("show_animation_note", True):
            s.pop("animation", None)
        if "aller_plus_loin" in s:
            apl = s["aller_plus_loin"]
            if isinstance(apl, dict):
                apl_filt = {k: v for k, v in apl.items() if k in niveaux_gardes}
            else:
                apl_filt = [item for item in apl if item.get("niveau") in niveaux_gardes]
            if apl_filt:
                s["aller_plus_loin"] = apl_filt
            else:
                s.pop("aller_plus_loin", None)
        return s

    doc2["sections"] = [filt_section(s) for s in doc.get("sections", [])]
    return doc2


# ----------------------------------------------------------------------
# Nettoyage pour le WEB (JSON / Markdown Quartz)
# ----------------------------------------------------------------------
_LATEX_DELETE_PATTERNS = [
    re.compile(r"\\tikzmark\{[^}]*\}"),
]
_LATEX_UNWRAP_PATTERNS = [
    (re.compile(r"\\ptFleche\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}"), r"\1"),
]


def clean_text_for_web(text):
    if not isinstance(text, str):
        return text
    for pat in _LATEX_DELETE_PATTERNS:
        text = pat.sub("", text)
    for pat, repl in _LATEX_UNWRAP_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _clean_field_or_list(val):
    """Auxiliaire permettant de nettoyer soit une chaîne, soit une liste d'objets."""
    if isinstance(val, str):
        return clean_text_for_web(val)
    elif isinstance(val, list):
        res = []
        for item in val:
            if isinstance(item, dict):
                it = dict(item)
                if "texte" in it:
                    it["texte"] = clean_text_for_web(it["texte"])
                res.append(it)
            else:
                res.append(clean_text_for_web(item))
        return res
    return val


def _clean_question_for_web(q: dict) -> dict:
    q = dict(q)
    q.pop("overlay_tikz", None)  # PDF-only
    for key in ("enonce", "coup_de_pouce", "correction", "solution"):
        if key in q:
            q[key] = _clean_field_or_list(q[key])
    if "aller_plus_loin" in q:
        apl = q["aller_plus_loin"]
        if isinstance(apl, dict):
            q["aller_plus_loin"] = {k: clean_text_for_web(v) for k, v in apl.items()}
        elif isinstance(apl, list):
            res = []
            for item in apl:
                it = dict(item)
                if "texte" in it:
                    it["texte"] = clean_text_for_web(it["texte"])
                res.append(it)
            q["aller_plus_loin"] = res
    if "encadre" in q:
        enc = dict(q["encadre"])
        enc["contenu"] = clean_text_for_web(enc.get("contenu"))
        q["encadre"] = enc
    return q


def clean_exercice_for_web(ex: dict) -> dict:
    ex2 = dict(ex)
    ex2.pop("overlay_tikz", None)  # PDF-only
    ex2.pop("questions", None)     # liste BRUTE
    if "enonce_intro" in ex2:
        ex2["enonce_intro"] = clean_text_for_web(ex2["enonce_intro"])

    def clean_item(item):
        if item["kind"] == "single":
            return _clean_question_for_web(item)
        if item["kind"] == "group":
            g = dict(item)
            g["subquestions"] = [_clean_question_for_web(sq) for sq in item["subquestions"]]
            return g
        if item["kind"] == "intro":
            return {**item, "enonce": clean_text_for_web(item["enonce"])}
        return item

    ex2["contenu"] = [clean_item(it) for it in ex2.get("contenu", [])]
    return ex2


def clean_cours_for_web(doc: dict) -> dict:
    doc2 = dict(doc)

    def clean_section(sec):
        s = dict(sec)
        s.pop("overlay_tikz", None)  # PDF-only
        for key in ("contenu", "remarque"):
            if key in s:
                s[key] = clean_text_for_web(s[key])
        if "aller_plus_loin" in s:
            apl = s["aller_plus_loin"]
            if isinstance(apl, dict):
                s["aller_plus_loin"] = {k: clean_text_for_web(v) for k, v in apl.items()}
            elif isinstance(apl, list):
                s["aller_plus_loin"] = [_clean_field_or_list(item) for item in apl]
        if "encadre" in s:
            enc = dict(s["encadre"])
            enc["contenu"] = clean_text_for_web(enc.get("contenu"))
            s["encadre"] = enc
        return s

    doc2["sections"] = [clean_section(s) for s in doc.get("sections", [])]
    return doc2


# ----------------------------------------------------------------------
# Chemins web des médias pré-rendus (figures SVG, animations GIF/MP4, PDF)
# ----------------------------------------------------------------------

def figure_web_path(ref):
    return f"/figures/{ref.lower()}.svg" if ref else None


def animation_web_path(ref):
    return f"/animations/{ref.lower()}/animation.gif" if ref else None


def animation_format_web_path(ref, fmt):
    ref = ref.lower()
    if fmt == "mp4":
        return f"/animations/{ref}/animation.mp4"
    if fmt == "gif":
        return f"/animations/{ref}/animation.gif"
    return None


def pdf_web_path(td_id, suffix):
    if not td_id or not suffix:
        return None
    return f"/pdfs/{td_id}_{suffix}.pdf"


def _enrich_sub_block_media(block_list):
    """Enrichit les figures/animations contenues dans une liste de sous-blocs (coup_de_pouce, etc.)."""
    if not isinstance(block_list, list):
        return block_list
    enriched = []
    for item in block_list:
        if isinstance(item, dict):
            it = dict(item)
            if it.get("figure"):
                it["figure"] = {**it["figure"], "src": figure_web_path(it["figure"]["ref"])}
            if it.get("animation"):
                it["animation"] = {**it["animation"], "src": animation_web_path(it["animation"]["ref"])}
            enriched.append(it)
        else:
            enriched.append(item)
    return enriched


def enrich_media_paths(exercice: dict) -> dict:
    """Ajoute un champ `src` (chemin web) à chaque `figure`/`animation`
    référencée dans un exercice td-like, en plus du `ref` d'origine."""
    ex = dict(exercice)
    if ex.get("figure"):
        ex["figure"] = {**ex["figure"], "src": figure_web_path(ex["figure"]["ref"])}
    if ex.get("animation"):
        ex["animation"] = {**ex["animation"], "src": animation_web_path(ex["animation"]["ref"])}

    def enrich_q(q):
        q = dict(q)
        if q.get("figure"):
            q["figure"] = {**q["figure"], "src": figure_web_path(q["figure"]["ref"])}
        if q.get("animation"):
            q["animation"] = {**q["animation"], "src": animation_web_path(q["animation"]["ref"])}
        
        # Enrichissement des figures/animations dans les sous-blocs
        for key in ("coup_de_pouce", "correction", "solution", "aller_plus_loin"):
            if key in q:
                q[key] = _enrich_sub_block_media(q[key])
        return q

    contenu = []
    for item in ex.get("contenu", []):
        if item["kind"] == "single":
            contenu.append(enrich_q(item))
        elif item["kind"] == "group":
            g = dict(item)
            g["subquestions"] = [enrich_q(sq) for sq in item["subquestions"]]
            contenu.append(g)
        else:
            contenu.append(item)
    ex["contenu"] = contenu
    return ex


def enrich_cours_media(doc: dict) -> dict:
    """Équivalent de enrich_media_paths pour un document cours-like."""
    doc2 = dict(doc)

    def enrich_section(sec):
        s = dict(sec)
        if s.get("figure"):
            s["figure"] = {**s["figure"], "src": figure_web_path(s["figure"]["ref"])}
        if s.get("animation"):
            s["animation"] = {**s["animation"], "src": animation_web_path(s["animation"]["ref"])}
        if "aller_plus_loin" in s:
            s["aller_plus_loin"] = _enrich_sub_block_media(s["aller_plus_loin"])
        return s

    doc2["sections"] = [enrich_section(s) for s in doc.get("sections", [])]
    return doc2