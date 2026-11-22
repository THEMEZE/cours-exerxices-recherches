"""
Chargement, normalisation et validation des QCM  (data/matieres/<matiere>/qcm/*.yaml).

Un fichier = un CHAPITRE (nom du fichier, ou clé `chapitre:`), avec autant de
questions que tu veux. Deux formats coexistent, mélangeables dans un même fichier :

1. COMPACT (recommandé pour écrire vite) -- un dict :

    chapitre: chap1_ondes            # facultatif (défaut : nom du fichier)
    titre: "Chap. 1 — Ondes mécaniques"
    td: td1_corde                    # facultatif : rattache les questions à un document (Quartz)
    defauts:                         # appliqué à chaque question (écrasable question par question)
      moment: entrainement           # debut | milieu | fin | entrainement | revision | bilan ...
      difficulte: moyen              # facile | moyen | difficile
      ajouter_neutre: true           # ajoute « Je ne sais pas encore » (réponse neutre)
    questions:
      - q: "Qu'est-ce qui change la fréquence quand on serre la corde ?"
        choix: ["La tension F", "La couleur", "Rien"]
        bonne: 1                     # numéro (1 = première) OU lettre (a, b, …)
        explication: "c = sqrt(F/mu) : plus F est grand, plus c est grand."
        # facultatifs : id, moment, difficulte, sujets, lie_a, figure, animation,
        #               feedback: {correct:…, incorrect:…, neutre:…}

2. LEGACY (ancien format, inchangé) -- une liste de questions complètes :

    - id: td1_qcm_debut1
      td: td1
      moment: debut
      question: "…"
      choix: [{id: a, texte: "…", correct: true}, {id: c, texte: "…", neutre: true}]
      feedback: {correct: "…", incorrect: "…", neutre: "…"}

Les fichiers dont le nom commence par « _ » sont ignorés (gabarits, brouillons).

Ce module ne dépend PAS de common_data.py : il est importé par le serveur, par
web/build_qcm_artifact.py, par build/build.py (PDF) et par build/pdf_status.py.
"""
from __future__ import annotations

import re
import string
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "matieres"
CONFIG_PATH = ROOT / "build" / "config.yaml"

LIBELLE_NEUTRE = "Je ne sais pas encore"
MOMENTS_CLASSIQUES = ("debut", "milieu", "fin")
MOMENT_DEFAUT = "entrainement"
FEEDBACK_DEFAUT = {
    "correct": "Exactement !",
    "incorrect": "Pas tout à fait.",
    "neutre": "Aucun souci, on y revient.",
}


# ----------------------------------------------------------------------
# Découverte
# ----------------------------------------------------------------------

def _ignored(name: str) -> bool:
    return name.startswith((".", "_")) or name == "__pycache__"


def qcm_dir(matiere: str) -> Path:
    return DATA_DIR / matiere / "qcm"


def list_matieres_qcm() -> list[str]:
    """Matières qui ont au moins un fichier QCM."""
    if not DATA_DIR.exists():
        return []
    return sorted(p.name for p in DATA_DIR.iterdir()
                  if p.is_dir() and not _ignored(p.name) and qcm_files(p.name))


def qcm_files(matiere: str) -> list[Path]:
    d = qcm_dir(matiere)
    if not d.is_dir():
        return []
    return sorted(p for p in d.rglob("*.yaml") if not _ignored(p.name)
                  and not any(_ignored(part) for part in p.relative_to(d).parts[:-1]))


def matiere_meta(matiere: str) -> dict:
    path = DATA_DIR / matiere / "_matiere.yaml"
    meta = {}
    if path.exists():
        meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    meta.setdefault("id", matiere)
    meta.setdefault("nom", matiere.replace("-", " ").replace("_", " ").capitalize())
    return meta


_cfg_cache: dict = {"sig": None, "val": {}}


def load_qcm_config() -> dict:
    """Bloc `qcm:` de build/config.yaml (valeurs par défaut globales). Relu seulement si le fichier change."""
    try:
        sig = CONFIG_PATH.stat().st_mtime_ns
    except OSError:
        return {}
    if _cfg_cache["sig"] != sig:
        try:
            cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}
        _cfg_cache.update(sig=sig, val=cfg.get("qcm") or {})
    return _cfg_cache["val"]


def is_libre(matiere: str, chapitre: str | None = None) -> bool:
    """Chapitre ouvert à l'entraînement libre ? Réglé dans build/config.yaml > qcm > acces_libre :
    chapitre explicite > défaut de la matière > défaut global (vrai si rien n'est écrit)."""
    al = load_qcm_config().get("acces_libre")
    if isinstance(al, bool):
        return al
    al = al or {}
    default = al.get("defaut", True)
    m = (al.get("matieres") or {}).get(matiere)
    if isinstance(m, bool):
        return m
    m = m or {}
    default = m.get("defaut", default)
    if chapitre:
        ch = (m.get("chapitres") or {}).get(chapitre)
        if ch is not None:
            return bool(ch)
    return bool(default)


# ----------------------------------------------------------------------
# Normalisation
# ----------------------------------------------------------------------

def _letters():
    return string.ascii_lowercase


def _chapitre_of(path: Path, qdir: Path, raw) -> str:
    if isinstance(raw, dict) and raw.get("chapitre"):
        return str(raw["chapitre"])
    return path.stem


def _bonne_index(bonne, choix_ids: list[str]) -> list[int]:
    """`bonne:` -> indices (0-based). Accepte 1, "1", "b", ["a", "c"]."""
    vals = bonne if isinstance(bonne, (list, tuple)) else [bonne]
    out = []
    for v in vals:
        if isinstance(v, bool) or v is None:
            continue
        s = str(v).strip().lower()
        if s.isdigit():
            out.append(int(s) - 1)
        elif s in choix_ids:
            out.append(choix_ids.index(s))
        else:
            out.append(-1)
    return out


def _normalize_choix(raw_choix, bonne, ajouter_neutre: bool, libelle_neutre: str) -> list[dict]:
    choix = []
    for i, c in enumerate(raw_choix or []):
        letter = _letters()[i]
        if isinstance(c, dict):
            d = dict(c)
            d.setdefault("id", letter)
            d["id"] = str(d["id"]).lower()
            d["texte"] = str(d.get("texte", d.get("text", "")))
            d["correct"] = bool(d.get("correct", False))
            if d.get("neutre"):
                d["neutre"] = True
            else:
                d.pop("neutre", None)
            choix.append(d)
        else:
            choix.append({"id": letter, "texte": str(c), "correct": False})
    if bonne is not None:
        ids = [c["id"] for c in choix]
        for idx in _bonne_index(bonne, ids):
            if 0 <= idx < len(choix):
                choix[idx]["correct"] = True
    if ajouter_neutre and not any(c.get("neutre") for c in choix):
        choix.append({"id": _letters()[len(choix)], "texte": libelle_neutre,
                      "correct": False, "neutre": True})
    return choix


def _normalize_question(raw: dict, *, matiere, chapitre, titre, td, defauts, index, source,
                        cfg) -> dict:
    q = {**defauts, **raw}
    question = q.get("question", q.get("q", ""))
    ajouter_neutre = bool(q.get("ajouter_neutre", cfg.get("ajouter_neutre", False)))
    libelle = str(q.get("libelle_neutre", cfg.get("libelle_neutre", LIBELLE_NEUTRE)))
    choix = _normalize_choix(q.get("choix"), q.get("bonne"), ajouter_neutre, libelle)

    expl = (q.get("explication") or "").strip()
    fb = {**FEEDBACK_DEFAUT, **(q.get("feedback") or {})}
    if expl and not q.get("feedback"):
        fb = {"correct": f"Exactement ! {expl}", "incorrect": f"Pas tout à fait. {expl}",
              "neutre": f"Aucun souci. {expl}"}

    n = index + 1
    out = {
        "id": str(q.get("id") or f"{chapitre}_q{n:03d}"),
        "matiere": matiere,
        "chapitre": chapitre,
        "chapitre_titre": titre,
        "td": q.get("td", td),
        "moment": q.get("moment") or MOMENT_DEFAUT,
        "lie_a": q.get("lie_a"),
        "difficulte": q.get("difficulte"),
        "sujets": q.get("sujets") or [],
        "question": str(question).strip(),
        "choix": choix,
        "feedback": fb,
        "explication": expl or None,
        "_source": source,
        "_ordre": n,
    }
    for k in ("animation", "figure"):
        if q.get(k):
            out[k] = q[k]
    return out


def load_file(path: Path, matiere: str) -> list[dict]:
    """Normalise un fichier QCM (format compact OU legacy)."""
    qdir = qcm_dir(matiere)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    cfg = {**load_qcm_config()}
    if isinstance(raw, list):                       # legacy : jamais de « neutre » ajouté d'office
        cfg = {}
        chapitre, titre, td, defauts, questions = _chapitre_of(path, qdir, raw), None, None, {}, raw
    elif isinstance(raw, dict):
        chapitre = _chapitre_of(path, qdir, raw)
        titre = raw.get("titre")
        td = raw.get("td")
        defauts = raw.get("defauts") or {}
        questions = raw.get("questions") or []
    else:
        raise ValueError(f"{path}: format inattendu (liste ou dict attendu)")
    out = []
    rel = str(path.relative_to(ROOT)) if ROOT in path.parents else str(path)
    for i, r in enumerate(questions):
        if not isinstance(r, dict):
            raise ValueError(f"{rel}: question n°{i + 1} n'est pas un dict")
        out.append(_normalize_question(r, matiere=matiere, chapitre=chapitre, titre=titre, td=td,
                                       defauts=defauts, index=i, source=rel, cfg=cfg))
    return out


def load_all_qcm(matiere_slug: str | None = None, td_filter: str | None = None,
                 chapitre: str | None = None) -> list[dict]:
    """Toutes les questions (normalisées). Remplace/complète common_data.load_all_qcm :
    mêmes clés qu'avant (id, td, moment, lie_a, question, choix, feedback, matiere…) + chapitre."""
    items = []
    matieres = [matiere_slug] if matiere_slug else list_matieres_qcm()
    for m in matieres:
        for path in qcm_files(m):
            for q in load_file(path, m):
                if td_filter and q.get("td") != td_filter:
                    continue
                if chapitre and q["chapitre"] != chapitre:
                    continue
                items.append(q)
    return items


def chapitres(matiere: str) -> list[dict]:
    """[{id, titre, n, moments, source}] -- un par fichier/chapitre, dans l'ordre alphabétique."""
    res = {}
    for q in load_all_qcm(matiere):
        c = res.setdefault(q["chapitre"], {"id": q["chapitre"],
                                            "titre": q.get("chapitre_titre") or q["chapitre"],
                                            "n": 0, "source": q["_source"]})
        c["n"] += 1
    out = sorted(res.values(), key=lambda c: c["id"])
    for c in out:
        c["libre"] = is_libre(matiere, c["id"])
    return out


def chapitres_libres(matiere: str) -> list[dict]:
    """Chapitres ouverts à l'entraînement libre (voir `is_libre`)."""
    return [c for c in chapitres(matiere) if c["libre"]]


def signature(matiere: str) -> tuple:
    """Empreinte légère (chemins + mtime) pour invalider un cache quand tu ajoutes des questions."""
    return tuple((str(p), p.stat().st_mtime_ns) for p in qcm_files(matiere))


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

def question_errors(q: dict) -> list[str]:
    """Problèmes bloquants d'une question normalisée (liste vide = OK)."""
    errs = []
    if not q["question"]:
        errs.append("énoncé vide")
    if len([c for c in q["choix"] if not c.get("neutre")]) < 2:
        errs.append("au moins 2 propositions (hors « je ne sais pas »)")
    ncorr = sum(1 for c in q["choix"] if c.get("correct"))
    if ncorr != 1:
        errs.append(f"{ncorr} bonne(s) réponse(s) (il en faut exactement 1)")
    if any(c.get("correct") and c.get("neutre") for c in q["choix"]):
        errs.append("une réponse ne peut pas être à la fois correcte et neutre")
    ids = [c["id"] for c in q["choix"]]
    if len(ids) != len(set(ids)):
        errs.append("ids de propositions dupliqués")
    return errs


def validate(matiere_slug: str | None = None) -> tuple[list[str], list[str]]:
    """(erreurs, avertissements) sur toute la base de QCM."""
    errors, warns, seen = [], [], {}
    matieres = [matiere_slug] if matiere_slug else list_matieres_qcm()
    for m in matieres:
        for path in qcm_files(m):
            try:
                items = load_file(path, m)
            except Exception as exc:  # YAML invalide, etc.
                errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
                continue
            for q in items:
                where = f"{m}/{q['_source'].split('/')[-1]} · {q['id']}"
                if q["id"] in seen:
                    errors.append(f"{where}: identifiant déjà utilisé dans {seen[q['id']]}")
                seen.setdefault(q["id"], where)
                errors.extend(f"{where}: {e}" for e in question_errors(q))
                if not q.get("explication") and q["feedback"] == FEEDBACK_DEFAUT:
                    warns.append(f"{where}: pas d'explication ni de feedback (le retour élève sera générique)")
    return errors, warns


def stats() -> dict:
    """{matiere: {chapitre: n}} pour un coup d'œil rapide."""
    out = {}
    for m in list_matieres_qcm():
        out[m] = {c["id"]: c["n"] for c in chapitres(m)}
    return out


# ----------------------------------------------------------------------
# PDF (build.py, type_doc: qcm)
# ----------------------------------------------------------------------

def qcm_doc_files(matiere: str, doc: str) -> list[Path]:
    """Fichiers sources d'un document PDF « qcm » : `doc` = un chapitre, ou `all`."""
    files = qcm_files(matiere)
    if doc in (None, "", "all"):
        return files
    out = []
    for p in files:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        chap = _chapitre_of(p, qcm_dir(matiere), raw)
        if chap == doc or p.stem == doc:
            out.append(p)
    return out


_MATH = re.compile(r"(\$\$.+?\$\$|\$.+?\$|\\\(.+?\\\)|\\\[.+?\\\])", re.S)
_TEX_SPECIALS = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                 "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}


# Symboles Unicode courants dans un énoncé web -> commande LaTeX (math). pdflatex ne les connaît pas.
_UNI = {
    "∝": r"\propto", "≈": r"\approx", "≠": r"\neq", "≤": r"\leq", "≥": r"\geq", "×": r"\times",
    "÷": r"\div", "±": r"\pm", "→": r"\rightarrow", "←": r"\leftarrow", "⇒": r"\Rightarrow",
    "⇔": r"\Leftrightarrow", "∞": r"\infty", "∈": r"\in", "∑": r"\sum", "∫": r"\int", "∂": r"\partial",
    "∇": r"\nabla", "·": r"\cdot", "−": "-",
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\varepsilon", "ζ": r"\zeta",
    "η": r"\eta", "θ": r"\theta", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi",
    "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "φ": r"\varphi", "χ": r"\chi", "ψ": r"\psi",
    "ω": r"\omega", "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda", "Ξ": r"\Xi",
    "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega", "ℏ": r"\hbar",
}
_SQRT = re.compile(r"√(\w+|\([^)]*\))")


_SUP = str.maketrans("⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹", "-+0123456789")
_SUP_RUN = re.compile("[⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹]+")


def _uni_math(seg: str) -> str:
    """Unicode -> commandes math (le segment est déjà en mode math)."""
    seg = _SUP_RUN.sub(lambda m: "^{" + m.group(0).translate(_SUP) + "}", seg)
    seg = _SQRT.sub(lambda m: r"\sqrt{" + m.group(1).strip("()") + "}", seg)
    seg = seg.replace("√", r"\surd ")
    return "".join((_UNI[ch] + " ") if ch in _UNI and _UNI[ch].startswith("\\") else _UNI.get(ch, ch) for ch in seg)


def _uni_text(seg: str) -> str:
    """Unicode -> $…$ dans un segment de texte brut (hors maths)."""
    if not any(ch in _UNI or ch == "√" or ch in "⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹" for ch in seg):
        return seg
    def wrap(m):
        return "$" + _uni_math(m.group(0)) + "$"
    return re.sub(r"(?:√(?:\w+|\([^)]*\))?|[" + "".join(re.escape(c) for c in _UNI) + "⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹" + r"])+", wrap, seg)


def _escape_outside_dollars(seg: str) -> str:
    """Échappe les caractères spéciaux sauf dans les $…$ que _uni_text vient d'insérer."""
    parts = re.split(r"(\$[^$]*\$)", seg)
    return "".join(p if i % 2 else "".join(_TEX_SPECIALS.get(ch, ch) for ch in p) for i, p in enumerate(parts))


def to_latex(text) -> str:
    """Texte QCM (plain + $maths$ + **gras** + *italique*) -> LaTeX sûr."""
    if text is None:
        return ""
    parts = _MATH.split(str(text))
    out = []
    for i, seg in enumerate(parts):
        if i % 2:                                # bloc math : tel quel (+ Unicode éventuel converti)
            out.append(_uni_math(seg))
            continue
        seg = _uni_text(seg)
        seg = _escape_outside_dollars(seg)
        seg = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", seg)
        seg = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\emph{\1}", seg)
        seg = re.sub(r"`(.+?)`", r"\\texttt{\1}", seg)
        out.append(seg)
    return "".join(out)


def load_qcm_doc(matiere: str, doc: str, target: dict | None = None) -> dict:
    """Document PDF : {titre, chapitres:[{id,titre,questions:[…]}], total}.
    Options de la cible (build/config.yaml) : nb_questions, melanger (graine fixe),
    moments: [...], difficultes: [...], inclure_neutre: bool."""
    import random
    target = target or {}
    files = qcm_doc_files(matiere, doc)
    if not files:
        raise FileNotFoundError(f"Aucun QCM pour {matiere}/{doc} (data/matieres/{matiere}/qcm/{doc}.yaml)")
    groups = []
    for p in files:
        items = load_file(p, matiere)
        if target.get("moments"):
            items = [q for q in items if q["moment"] in target["moments"]]
        if target.get("difficultes"):
            items = [q for q in items if q.get("difficulte") in target["difficultes"]]
        if target.get("melanger"):
            random.Random(target.get("graine", 1)).shuffle(items)
        if items:
            groups.append({"id": items[0]["chapitre"], "titre": items[0].get("chapitre_titre") or items[0]["chapitre"],
                           "questions": items})
    n = target.get("nb_questions")
    if n:
        left = int(n)
        for g in groups:
            g["questions"] = g["questions"][:left]
            left -= len(g["questions"])
        groups = [g for g in groups if g["questions"]]
    inclure_neutre = bool(target.get("inclure_neutre", False))
    num = 0
    for g in groups:
        for q in g["questions"]:
            num += 1
            q["numero"] = num
            q["media_pdf"] = media_for_pdf(q)
            q["choix_pdf"] = [c for c in q["choix"] if inclure_neutre or not c.get("neutre")]
    return {"chapitres": groups, "total": num, "matiere": matiere, "doc": doc}


# ----------------------------------------------------------------------
# Figures et animations (web, Quartz, PDF) -- même convention que les TD :
#   figure:    {ref: ma_figure, legende: "…"}      -> web/public/figures/ma_figure.svg   (/figures/ma_figure.svg)
#              {src: /figures/mon_image.png}        -> image « libre » déposée dans web/public/figures/
#              (une liste de figures est acceptée)
#   animation: {ref: anim_corde, formats: [gif]}    -> animations/outputs/anim_corde/animation.gif
# ----------------------------------------------------------------------

FIG_DIR = ROOT / "web" / "public" / "figures"
ANIM_DIR = ROOT / "animations" / "outputs"
MEDIA_CACHE = ROOT / "build" / "generated" / "qcm_media"


def _fig_items(fig) -> list[dict]:
    if not fig:
        return []
    out = []
    for f in (fig if isinstance(fig, list) else [fig]):
        if isinstance(f, str):
            f = {"src": f} if f.startswith(("/", "http")) else {"ref": f}
        if not isinstance(f, dict):
            continue
        ref, src = f.get("ref"), f.get("src")
        if ref and "?" not in str(ref):              # « ??? » = gabarit non rempli : ignoré
            src = f"/figures/{str(ref).lower()}.svg"
        if src:
            out.append({"src": src, "legende": f.get("legende", ""), "ref": ref})
    return out


def media_for_web(q: dict) -> dict:
    """{'figures': [{src, legende}], 'animation': {src, ref, formats} | None} -- chemins web."""
    anim = q.get("animation")
    a = None
    if isinstance(anim, dict) and anim.get("ref") and "?" not in str(anim["ref"]):
        ref = str(anim["ref"]).lower()
        a = {"ref": anim["ref"], "formats": anim.get("formats", ["gif"]), "src": f"/animations/{ref}/animation.gif"}
    return {"figures": [{"src": f["src"], "legende": f["legende"]} for f in _fig_items(q.get("figure"))],
            "animation": a}


_warned = set()


def _warn_once(msg: str):
    if msg not in _warned:
        _warned.add(msg)
        print(f"   ⚠️  {msg}")


def _svg_to_pdf(svg: Path, out: Path) -> bool:
    import shutil
    import subprocess
    try:
        import cairosvg
        cairosvg.svg2pdf(url=str(svg), write_to=str(out))
        return True
    except ImportError:
        pass
    except Exception as exc:
        _warn_once(f"cairosvg a échoué sur {svg.name} : {exc}")
    for cmd in (["rsvg-convert", "-f", "pdf", "-o", str(out), str(svg)],
                ["inkscape", str(svg), "--export-type=pdf", f"--export-filename={out}"]):
        if shutil.which(cmd[0]):
            if subprocess.run(cmd, capture_output=True).returncode == 0 and out.exists():
                return True
    _warn_once("conversion SVG -> PDF impossible : installe cairosvg (pip install cairosvg) ou rsvg-convert/inkscape")
    return False


def _local_figure(src: str) -> Path | None:
    if src.startswith("/figures/"):
        return FIG_DIR / src[len("/figures/"):]
    return None


def _gif_frames(gif: Path, ref: str, max_frames: int = 60) -> dict:
    """GIF -> frames PNG numérotées (frame_00001.png …) pour le paquet LaTeX `animate`
    (lecture dans Adobe Acrobat/Reader ; les autres lecteurs affichent la 1re image).
    Sous-échantillonné à max_frames images et réduit à 700 px de large pour garder un PDF léger."""
    from PIL import Image, ImageSequence
    d = MEDIA_CACHE / f"{ref}_frames"
    d.mkdir(parents=True, exist_ok=True)
    meta = d / "meta.txt"
    if meta.exists() and meta.stat().st_mtime >= gif.stat().st_mtime:
        n, fps = meta.read_text().split()
        n, fps = int(n), float(fps)
    else:
        for old in d.glob("frame_*.png"):
            old.unlink()
        with Image.open(gif) as im:
            frames = [(f.copy().convert("RGB"), f.info.get("duration", 100)) for f in ImageSequence.Iterator(im)]
        total = len(frames)
        step = max(1, -(-total // max_frames))
        kept = frames[::step]
        dur = sum(x[1] for x in frames) / max(total, 1) * step          # ms par image gardée
        fps = round(1000 / max(dur, 20), 2)
        for k, (fr, _) in enumerate(kept, 1):
            if fr.width > 700:
                fr = fr.resize((700, round(fr.height * 700 / fr.width)))
            fr.save(d / f"frame_{k:05d}.png")
        n = len(kept)
        meta.write_text(f"{n} {fps}")
    return {"prefix": (d / "frame_").relative_to(ROOT).as_posix(), "first": "00001",
            "last": f"{n:05d}", "fps": fps, "path": (d / "frame_00001.png").relative_to(ROOT).as_posix()}


def media_for_pdf(q: dict) -> dict:
    """Fichiers utilisables par pdflatex (chemins RELATIFS à la racine du projet : build.py lance
    pdflatex depuis la racine). SVG -> PDF (cairosvg / rsvg-convert / inkscape), cache dans
    build/generated/qcm_media/. Animation GIF -> 1re image en PNG (Pillow). Absent = ignoré, avec avertissement."""
    MEDIA_CACHE.mkdir(parents=True, exist_ok=True)
    figs = []
    for f in _fig_items(q.get("figure")):
        src = _local_figure(f["src"])
        if not src or not src.exists():
            _warn_once(f"figure introuvable pour le PDF : {f['src']}")
            continue
        path = src
        if src.suffix.lower() == ".svg":
            for alt in (src.with_suffix(".pdf"), src.with_suffix(".png")):     # version déjà rendue ? on la préfère
                if alt.exists():
                    path = alt
                    break
            else:
                out = MEDIA_CACHE / (src.stem + ".pdf")
                if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
                    if not _svg_to_pdf(src, out):
                        continue
                path = out
        figs.append({"path": path.relative_to(ROOT).as_posix(), "legende": f["legende"]})
    anim = None
    a = media_for_web(q)["animation"]
    if a:
        ref = str(a["ref"]).lower()
        gif = ANIM_DIR / ref / "animation.gif"
        if gif.exists():
            try:
                anim = _gif_frames(gif, ref, max_frames=int((q.get("animation") or {}).get("pdf_max_images", 60)))
            except Exception as exc:
                _warn_once(f"images de {gif.name} impossibles (pip install pillow ?) : {exc}")
        else:
            _warn_once(f"animation introuvable pour le PDF : {gif.relative_to(ROOT)}")
    return {"figures": figs, "animation": anim}


# ----------------------------------------------------------------------
# Liens + QR code pour les pages Quartz (export_markdown.py)
# ----------------------------------------------------------------------

def qcm_url(matiere: str, chapitre: str | None = None, absolute: bool = True) -> str:
    """URL de l'appli QCM d'une matière (entraînement libre d'un chapitre si `chapitre`).
    `qcm.base_url` (build/config.yaml) donne le site public, ex. https://cours.exemple.fr"""
    path = f"/qcm/{matiere}/" + (f"?c={chapitre}" if chapitre else "")
    base = (load_qcm_config().get("base_url") or "").rstrip("/")
    return (base + path) if (base and absolute) else path


def qr_data_uri(url: str, scale: int = 4) -> str | None:
    """QR code SVG (data URI, aucun fichier à publier) -- None si `segno` n'est pas installé
    ou si l'URL n'est pas absolue (un QR vers un chemin relatif ne scanne rien)."""
    if not url.startswith("http"):
        return None
    try:
        import base64
        import io
        import segno
    except ImportError:
        return None
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=scale, border=2, dark="#16323F", xmldecl=False, svgns=True)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


def qcm_link_html(matiere: str, chapitre: str | None, label: str, qr_px: int = 110) -> str:
    """Lien (nouvel onglet, adresse RELATIVE : marche aussi sur le site local) + QR code
    (adresse ABSOLUE, qcm.base_url) en HTML brut accepté par Quartz."""
    href = qcm_url(matiere, chapitre, absolute=False)
    html = f'<a href="{href}" target="_blank" rel="noopener">{label}</a>'
    qr = qr_data_uri(qcm_url(matiere, chapitre))
    if qr:
        html += (f'<br><a href="{href}" target="_blank" rel="noopener"><img src="{qr}" width="{qr_px}" '
                 f'height="{qr_px}" alt="QR code : {label}" style="image-rendering:pixelated"></a>')
    return html
