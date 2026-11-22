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
import unicodedata
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

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def resolve_child(parent: Path, name: str) -> Path:
    """parent/name, tolérant à la normalisation Unicode : un zip fait sur macOS
    stocke « é » en NFD (e + accent combinant), alors que le YAML est en NFC --
    ça marche sur le Mac (APFS normalise) mais PAS sur le Raspberry (ext4).
    Si le chemin exact n'existe pas, on cherche l'entrée équivalente."""
    direct = parent / name
    if direct.exists() or not parent.is_dir():
        return direct
    target = _nfc(name)
    for child in parent.iterdir():
        if _nfc(child.name) == target:
            return child
    return direct


def is_ignored_name(name: str) -> bool:
    """Dossiers/fichiers jamais traités comme documents : brouillons « xxx copie »
    (copies Finder), préfixes _ ou ., fichiers cachés."""
    n = name.lower()
    return n.startswith(("_", ".")) or " copie" in n or n.endswith(("_copie", "-copie"))


def _is_published(meta_path: Path) -> bool:
    """`publier: false` dans _meta.yaml (ou dans un cours) exclut le document."""
    try:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return True
    return meta.get("publier", True) is not False


def list_matieres():
    """Toute matière = dossier de data/matieres/ avec un _matiere.yaml OU au
    moins un sous-dossier td/tp/cours/qcm (meta par défaut sinon)."""
    if not DATA_DIR.exists():
        return []
    out = []
    for p in DATA_DIR.iterdir():
        if not p.is_dir() or is_ignored_name(p.name):
            continue
        if (p / "_matiere.yaml").exists() or any((p / s).is_dir() for s in ("td", "tp", "cours", "qcm")):
            out.append(p.name)
    return sorted(out)


def load_matiere_meta(matiere_slug: str) -> dict:
    path = DATA_DIR / matiere_slug / "_matiere.yaml"
    meta = {}
    if path.exists():
        meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # Valeurs par défaut : une matière sans _matiere.yaml reste exportable.
    meta.setdefault("id", matiere_slug)
    meta.setdefault("nom", matiere_slug.replace("-", " ").replace("_", " ").capitalize())
    meta.setdefault("quartz_namespace", matiere_slug)
    meta.setdefault("sujets", [])
    meta["sujets"] = [s for s in (meta["sujets"] or []) if isinstance(s, str) and len(s) > 1]
    return meta


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
    return sorted(
        p.name for p in d.iterdir()
        if p.is_dir() and not is_ignored_name(p.name)
        and (p / "_meta.yaml").exists() and _is_published(p / "_meta.yaml")
    )


def load_td(matiere_slug: str, doc_slug: str, type_doc: str = "td", only_exercices=None):
    """Retourne (meta, [exercices]) pour un document td-like, exercices dans
    l'ordre déclaré dans _meta.yaml (exercices_ordre)."""
    doc_dir = resolve_child(_type_dir(matiere_slug, type_doc), doc_slug)
    meta = yaml.safe_load((doc_dir / "_meta.yaml").read_text(encoding="utf-8"))
    meta["matiere"] = matiere_slug
    meta["type_doc"] = type_doc
    meta["doc_slug"] = doc_slug

    order = only_exercices or meta["exercices_ordre"]
    exercices = []
    for numero, ex_slug in enumerate(order, start=1):
        ex_path = resolve_child(doc_dir, f"{ex_slug}.yaml")
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
    return sorted(p.stem for p in d.glob("*.yaml")
                  if not is_ignored_name(p.name) and _is_published(p))


def load_cours(matiere_slug: str, doc_slug: str, type_doc: str = "cours") -> dict:
    path = resolve_child(_type_dir(matiere_slug, type_doc), f"{doc_slug}.yaml")
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


_MATH_RE = re.compile(r"(\$\$.*?\$\$|\$[^$\n]*?\$|\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)
_ENV_RE = re.compile(r"\\begin\{(enumerate|itemize)\}(\[[^\]]*\])?((?:(?!\\begin\{(?:enumerate|itemize)\}).)*?)\\end\{\1\}", re.DOTALL)


def _list_env_to_md(m):
    kind, opt, body = m.group(1), m.group(2) or "", m.group(3)
    items = [i.strip() for i in re.split(r"\\item\b\s*", body) if i.strip()]
    out = []
    for n, it in enumerate(items):
        if kind == "itemize":
            mark = "-"
        elif "alph" in opt:
            mark = f"({chr(ord('a') + n)})"
        else:
            mark = f"{n + 1}."
        out.append(f"{mark} {it}" if kind == "enumerate" else f"- {it}")
    sep = "\n\n" if (kind == "enumerate" and "alph" in opt) else "\n"   # (a) (b) : pas une vraie liste Markdown
    return "\n\n" + sep.join(out) + "\n\n"


def _latex_text_to_md(seg: str) -> str:
    """Macros de TEXTE courantes -> Markdown (les maths sont protégées par l'appelant)."""
    seg = re.sub(r"\{\\(?:bf|bfseries)\s+((?:[^{}]|\{[^{}]*\})*)\}", r"**\1**", seg)
    seg = re.sub(r"\\textbf\{((?:[^{}]|\{[^{}]*\})*)\}", r"**\1**", seg)
    seg = re.sub(r"\{\\(?:it|em|itshape)\s+((?:[^{}]|\{[^{}]*\})*)\}", r"*\1*", seg)
    seg = re.sub(r"\\(?:textit|emph)\{((?:[^{}]|\{[^{}]*\})*)\}", r"*\1*", seg)
    seg = seg.replace("\\newline", "\n").replace("\\medskip", "\n").replace("\\smallskip", "").replace("\\bigskip", "\n")
    return seg


def clean_text_for_web(text):
    if not isinstance(text, str):
        return text
    for pat in _LATEX_DELETE_PATTERNS:
        text = pat.sub("", text)
    for pat, repl in _LATEX_UNWRAP_PATTERNS:
        text = pat.sub(repl, text)
    # listes (structurelles, leurs items contiennent des formules) : sur tout le texte,
    # les plus internes d'abord
    for _ in range(3):
        text = _ENV_RE.sub(_list_env_to_md, text)
    # gras/italique : en laissant les formules ($...$, $$...$$) intactes
    parts = _MATH_RE.split(text)
    parts = [p if i % 2 else _latex_text_to_md(p) for i, p in enumerate(parts)]
    return "".join(parts)


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


def _enrich_figure(fig):
    """`figure:` est un dict {ref, legende...} OU une liste de tels dicts. Les
    refs vides ou « ??? » (gabarits non remplis, ~40 dans tes YAML) sont
    ignorées : pas d'image cassée sur le site."""
    if not fig:
        return None
    if isinstance(fig, list):
        out = [f for f in (_enrich_figure(x) for x in fig) if f]
        return out or None
    ref = fig.get("ref")
    if not ref or "?" in str(ref):
        return None
    return {**fig, "src": figure_web_path(ref)}


def _fix_figure(d: dict) -> None:
    if "figure" in d:
        f = _enrich_figure(d["figure"])
        if f:
            d["figure"] = f
        else:
            d.pop("figure")


def _fix_animation(d: dict) -> None:
    anim = d.get("animation")
    if anim:
        if isinstance(anim, dict) and anim.get("ref") and "?" not in str(anim["ref"]):
            d["animation"] = {**anim, "src": animation_web_path(anim["ref"])}
        else:
            d.pop("animation")


def _enrich_sub_block_media(block_list):
    """Enrichit les figures/animations contenues dans une liste de sous-blocs (coup_de_pouce, etc.)."""
    if not isinstance(block_list, list):
        return block_list
    enriched = []
    for item in block_list:
        if isinstance(item, dict):
            it = dict(item)
            _fix_figure(it)
            _fix_animation(it)
            enriched.append(it)
        else:
            enriched.append(item)
    return enriched


def enrich_media_paths(exercice: dict) -> dict:
    """Ajoute un champ `src` (chemin web) à chaque `figure`/`animation`
    référencée dans un exercice td-like, en plus du `ref` d'origine."""
    ex = dict(exercice)
    _fix_figure(ex)
    _fix_animation(ex)

    def enrich_q(q):
        q = dict(q)
        _fix_figure(q)
        _fix_animation(q)
        
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
        _fix_figure(s)
        _fix_animation(s)
        if "aller_plus_loin" in s:
            s["aller_plus_loin"] = _enrich_sub_block_media(s["aller_plus_loin"])
        return s

    doc2["sections"] = [enrich_section(s) for s in doc.get("sections", [])]
    return doc2