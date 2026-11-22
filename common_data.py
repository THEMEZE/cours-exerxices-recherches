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
BUILD_CONFIG_FILE = ROOT / "build" / "config.yaml"
PROFILES_FILE = ROOT / "web" / "visibility_profiles.yaml"

NIVEAU_LABELS = {
    "lycee": "Lycée",
    "cpge": "CPGE",
    "prepa": "CPGE",
    "licence": "Licence",
    "master": "Master",
    "doctorat": "Doctorat",
    "agregation": "Agrégation",
}


# ----------------------------------------------------------------------
# build/config.yaml : couleur de l'anglais + profil de publication par document
# ----------------------------------------------------------------------

_BUILD_CONFIG = None


def load_build_config() -> dict:
    global _BUILD_CONFIG
    if _BUILD_CONFIG is None:
        try:
            _BUILD_CONFIG = yaml.safe_load(BUILD_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        except OSError:
            _BUILD_CONFIG = {}
    return _BUILD_CONFIG


_HEX_RE = re.compile(r"#?([0-9A-Fa-f]{6})")


def _en_color_raw(web: bool) -> str:
    cfg = load_build_config().get("couleurs") or {}
    raw = (cfg.get("anglais_web") if web else None) or cfg.get("anglais") or "#1565C0"
    return str(raw).strip()


def en_color_css() -> str:
    """Couleur de l'anglais pour le SITE (couleurs.anglais_web, sinon couleurs.anglais)."""
    raw = _en_color_raw(web=True)
    m = _HEX_RE.fullmatch(raw)
    return f"#{m.group(1).upper()}" if m else raw


def en_color_latex_definition() -> str:
    """Ligne LaTeX qui définit la couleur `colorEN` pour les PDF (couleurs.anglais)."""
    raw = _en_color_raw(web=False)
    m = _HEX_RE.fullmatch(raw)
    return rf"\definecolor{{colorEN}}{{HTML}}{{{m.group(1).upper()}}}" if m else rf"\colorlet{{colorEN}}{{{raw}}}"


_EN_BLUE_RE = re.compile(r"(\\(?:text)?color)\{blue\}")


def read_yaml(path: Path):
    """yaml.safe_load avec un message d'erreur qui NOMME le fichier et la ligne
    (avant : « mapping values are not allowed here » sans dire où)."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        try:
            shown = path.resolve().relative_to(ROOT)
        except ValueError:
            shown = path
        where = f"{shown}" + (f", ligne {mark.line + 1}, colonne {mark.column + 1}" if mark else "")
        problem = getattr(e, "problem", None) or str(e).splitlines()[0]
        hint = ""
        if "mapping values are not allowed" in str(problem):
            hint = (" -- astuce : un texte contenant « : » (ou finissant par « :», fréquent en français) "
                    "doit être entre guillemets \"...\" ou écrit en bloc  > / |")
        raise ValueError(f"YAML invalide : {where} : {problem}{hint}") from None


def normalize_en_color(obj):
    """Dans les YAML, l'anglais est écrit {\\color{blue} ...}. On le redirige vers
    la couleur NOMMÉE `colorEN`, réglée dans config.yaml (couleurs.anglais) :
    même teinte pour les PDF (\\definecolor) et pour le site. Convention : « blue »
    = anglais ; pour un vrai bleu ailleurs, utilise \\colorFour ou un hex."""
    if isinstance(obj, str):
        return _EN_BLUE_RE.sub(r"\1{colorEN}", obj)
    if isinstance(obj, dict):
        return {k: normalize_en_color(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_en_color(v) for v in obj]
    return obj


def load_visibility_profiles() -> dict:
    return yaml.safe_load(PROFILES_FILE.read_text(encoding="utf-8"))["profiles"]


def publication_config() -> dict:
    return load_build_config().get("publication") or {}


def resolve_profile(matiere: str, type_doc: str, doc_slug: str, ex_slug: str = None, forced: str = None) -> str:
    """Profil de visibilité d'un document (ou d'un exercice) :

      1. `forced` (argument en ligne de commande, ex. `all`) l'emporte, sauf « auto » ;
      2. sinon publication: dans build/config.yaml :
             publication.matieres.<matiere>.<td|tp|cours>.<doc>        -> profil du document
             ... .<doc>.exercices.<ex>                                  -> surcharge d'un exercice
      3. sinon le `defaut` de la matière, puis le `defaut` global, puis avant_seance.
    """
    if forced and forced != "auto":
        return forced
    pub = publication_config()
    default = pub.get("defaut", "avant_seance")
    m = (pub.get("matieres") or {}).get(matiere) or {}
    default = m.get("defaut", default)
    entry = (m.get(type_doc) or {}).get(doc_slug)
    prof, exs = default, {}
    if isinstance(entry, str):
        prof = entry
    elif isinstance(entry, dict):
        prof = entry.get("profil", prof)
        exs = entry.get("exercices") or {}
    if ex_slug and ex_slug in exs:
        prof = exs[ex_slug]
    return prof


def split_en_text(raw: str):
    """« Titre FR {\\color{colorEN}English title} » -> (FR, EN) en texte propre.
    Sert aux URL (slug = français seul), au titre de page (français) et à la
    ligne d'anglais en couleur sous le titre."""
    if not isinstance(raw, str):
        return "", ""
    text = normalize_en_color(raw)
    rest, groups, pos = [], [], 0
    for m in _COLOR_START.finditer(text):
        if m.start() < pos:
            continue
        color = m.group(1) or m.group(2)
        if color != "colorEN":
            continue
        depth, i = 1, m.end()
        while i < len(text) and depth:
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            depth += (ch == "{") - (ch == "}")
            i += 1
        if depth:
            continue
        rest.append(text[pos:m.start()])
        groups.append(text[m.end():i - 1])
        pos = i
    rest.append(text[pos:])

    def tidy(s):
        s = re.sub(r"\\\\|\\newline", " ", s)
        s = clean_text_for_web(s)
        s = re.sub(r"\s+", " ", s).strip()
        return re.sub(r"^[\s—–/:;,|-]+|[\s—–/:;,|-]+$", "", s)

    return tidy("".join(rest)), tidy(" ".join(groups))


def title_parts(raw: str):
    """Alias lisible : (titre_fr, titre_en)."""
    return split_en_text(raw)


def en_span(en: str) -> str:
    """Texte anglais dans la couleur du site (HTML inline, accepté par Quartz)."""
    return f'<span style="color:{en_color_css()}">{en}</span>' if en else ""



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
    meta = normalize_en_color(read_yaml(doc_dir / "_meta.yaml"))
    meta["matiere"] = matiere_slug
    meta["type_doc"] = type_doc
    meta["doc_slug"] = doc_slug

    order = only_exercices or meta["exercices_ordre"]
    exercices = []
    for numero, ex_slug in enumerate(order, start=1):
        ex_path = resolve_child(doc_dir, f"{ex_slug}.yaml")
        ex = normalize_en_color(read_yaml(ex_path))
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
    doc = normalize_en_color(read_yaml(path))
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
    """QCM normalisés. Délègue à qcm_data.py (format compact ou liste, autant de questions
    que voulu par chapitre) ; mêmes clés qu'avant + `chapitre`."""
    import qcm_data
    return [{k: v for k, v in q.items() if not k.startswith("_")}
            for q in qcm_data.load_all_qcm(matiere_slug, td_filter)]


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


_COLOR_START = re.compile(r"\{\s*\\color\{(#?[A-Za-z0-9]+)\}\s*|\\textcolor\{(#?[A-Za-z0-9]+)\}\{")


def _convert_color_groups(text: str) -> str:
    """`{\\color{blue} ...}` et `\\textcolor{blue}{...}` -> <span style="color:blue">...</span>.
    Accolades équilibrées (les formules $\\frac{a}{b}$ à l'intérieur sont OK) ;
    un groupe sur plusieurs paragraphes est découpé (un <span> ne traverse pas
    une ligne vide en Markdown)."""
    out, pos = [], 0
    while True:
        m = _COLOR_START.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        depth, i = 1, m.end()
        while i < len(text) and depth:
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            depth += (ch == "{") - (ch == "}")
            i += 1
        if depth:                       # accolade jamais fermée : on laisse tel quel
            out.append(text[m.start():m.end()])
            pos = m.end()
            continue
        color = m.group(1) or m.group(2)
        inner = _convert_color_groups(text[m.end():i - 1])
        paras = re.split(r"(\n\s*\n)", inner)
        out.append("".join(f'<span style="color:{color}">{p}</span>' if p.strip() and not re.fullmatch(r"\n\s*\n", p) else p
                           for p in paras))
        pos = i
    return "".join(out)


_THEME_COLORS = None


def _theme_colors() -> dict:
    """\\colorOne.. -> #RRGGBB, lus dans templates/styles/theme_academique.tex
    (les mêmes couleurs que dans les PDF)."""
    global _THEME_COLORS
    if _THEME_COLORS is None:
        _THEME_COLORS = {}
        f = Path(__file__).resolve().parent / "templates" / "styles" / "theme_academique.tex"
        if f.exists():
            for name, hexv in re.findall(r"\\definecolor\{(color\w+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}", f.read_text(encoding="utf-8")):
                _THEME_COLORS[name] = "#" + hexv.upper()
    return _THEME_COLORS


def _replace_theme_colors(text: str) -> str:
    colors = {**_theme_colors(), "colorEN": en_color_css()}
    text = re.sub(r"\\(color[A-Z][A-Za-z]*)\b", lambda m: colors.get(m.group(1), m.group(0)), text)
    # forme « nom TeX » : \color{colorSix}, \textcolor{colorOne}{...}
    return re.sub(r"(\\(?:text)?color)\{(color[A-Z][A-Za-z]*)\}",
                  lambda m: f"{m.group(1)}{{{colors.get(m.group(2), m.group(2))}}}", text)


def clean_text_for_web(text):
    if not isinstance(text, str):
        return text
    for pat in _LATEX_DELETE_PATTERNS:
        text = pat.sub("", text)
    for pat, repl in _LATEX_UNWRAP_PATTERNS:
        text = pat.sub(repl, text)
    text = _replace_theme_colors(text)          # \colorOne -> #8C0000 (utile aussi dans les formules KaTeX)
    # Les formules sont mises de côté : aucune conversion de TEXTE ne doit les toucher
    # (ex. {\color{red} x} dans un $...$ reste du LaTeX).
    maths = []

    def _stash(m):
        maths.append(m.group(0))
        return f"\ue000{len(maths) - 1}\ue001"

    text = _MATH_RE.sub(_stash, text)
    text = _convert_color_groups(text)
    for _ in range(3):                           # listes : les plus internes d'abord
        text = _ENV_RE.sub(_list_env_to_md, text)
    text = _latex_text_to_md(text)
    return re.sub("\ue000(\\d+)\ue001", lambda m: maths[int(m.group(1))], text)


def _clean_field_or_list(val):
    """Auxiliaire permettant de nettoyer soit une chaîne, soit une liste d'objets."""
    if isinstance(val, str):
        return clean_text_for_web(val)
    elif isinstance(val, list):
        res = []
        for item in val:
            if isinstance(item, dict):
                it = dict(item)
                for k in ("texte", "titre"):
                    if k in it:
                        it[k] = clean_text_for_web(it[k])
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
                for k in ("texte", "titre"):
                    if k in it:
                        it[k] = clean_text_for_web(it[k])
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


def blocks_to_markdown(val) -> str:
    """Champ texte (coup_de_pouce, correction, solution, aller_plus_loin...) :
    chaîne OU liste de blocs {titre, texte, [figure]} -> Markdown."""
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
        figs = b.get("figure")
        for f in (figs if isinstance(figs, list) else [figs] if figs else []):
            if f.get("src"):
                seg.append(f"![{(f.get('legende') or '').strip()}]({f['src']})")
        parts.append("\n\n".join(seg))
    return "\n\n".join(p for p in parts if p.strip())


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

  