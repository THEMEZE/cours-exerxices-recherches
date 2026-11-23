#!/usr/bin/env python3
"""
Rubriques pédagogiques -> callouts Markdown (Quartz).

Une RUBRIQUE est une clé YAML (prerequis, objectifs_pedagogiques_etudiants, point_cours,
outils_mathematiques, remarques_pedagogiques_*, bilan, liens_autres_disciplines, ...) présente :
  - dans le _meta.yaml d'un document   (niveau « document »  -> page index du TD/TP/projet),
  - dans un fichier d'exercice          (niveau « exercice » -> page de l'exercice),
  - dans une question                   (niveau « question » -> dans l'exercice, sous la question).

Quelles rubriques existent, leur titre, icône, couleur de callout, public (élève / prof),
position (avant ou après les questions) et état de repli : build/config.yaml > rubriques
(défauts dans common_data.DEFAULT_RUBRIQUES).
Quelles rubriques un PROFIL affiche : web/visibility_profiles.yaml > <profil> > rubriques.

Le contenu d'une rubrique peut être :
    "du texte"
    ["texte 1", "texte 2"]
    [{titre: "...", texte: "..."}, ...]
    [{discipline: "Chimie", texte: "..."}, ...]
    [{titre, question_d_accroche, duree_introduction, texte}]     (accroche)
=> ajouter une nouvelle rubrique ne demande AUCUN code : seulement un bloc dans config.yaml.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common_data import (  # noqa: E402
    clean_text_for_web, rubriques_registry, visible_rubriques,
)


def callout_raw(kind: str, title: str, body_md: str, collapse: str = "") -> str:
    """Callout Obsidian/Quartz : `collapse` = '' fixe, '+' ouvert-repliable, '-' fermé-repliable."""
    lines = (body_md or "").strip("\n").split("\n")
    quoted = "\n".join(((">" + (" " + l if l.strip() else "")) for l in lines))
    return f"> [!{kind}]{collapse} {title}\n{quoted}\n"


def _item_md(item) -> str:
    """Un élément de rubrique (chaîne ou dict) -> Markdown."""
    if item is None:
        return ""
    if isinstance(item, str):
        return clean_text_for_web(item).strip()
    if isinstance(item, (int, float)):
        return str(item)
    if not isinstance(item, dict):
        return clean_text_for_web(str(item)).strip()
    parts = []
    head = item.get("titre") or item.get("discipline")
    if head:
        parts.append(f"**{clean_text_for_web(str(head)).strip()}**")
    if item.get("duree_introduction"):
        parts.append(f"*Durée de l'introduction : {item['duree_introduction']}*")
    if item.get("question_d_accroche"):
        parts.append(f"*{clean_text_for_web(str(item['question_d_accroche'])).strip()}*")
    if item.get("texte") is not None:
        parts.append(clean_text_for_web(str(item["texte"])).strip())
    # clés inconnues (nouvelles rubriques structurées) : affichées « clé : valeur » plutôt que perdues
    known = {"titre", "discipline", "duree_introduction", "question_d_accroche", "texte"}
    for k, v in item.items():
        if k not in known and isinstance(v, (str, int, float)):
            parts.append(f"*{k.replace('_', ' ')}* : {clean_text_for_web(str(v)).strip()}")
    return "\n\n".join(p for p in parts if p)


def rubrique_body(val) -> str:
    if val is None or val == "" or val == []:
        return ""
    if isinstance(val, (str, int, float, dict)):
        return _item_md(val)
    return "\n\n".join(x for x in (_item_md(i) for i in val) if x)


def render_rubriques(obj: dict, opts: dict, position: str) -> list:
    """Callouts des rubriques de `obj` pour la position `debut` | `fin`, selon le profil `opts`.
    Ne rend que les rubriques (1) déclarées, (2) autorisées par le profil, (3) non vides."""
    if not obj:
        return []
    visibles = visible_rubriques(opts)
    out = []
    for key, spec in rubriques_registry().items():
        if key not in visibles or spec.get("position", "fin") != position:
            continue
        body = rubrique_body(obj.get(key))
        if not body:
            continue
        titre = f"{spec.get('icone', '')} {spec.get('titre', key)}".strip()
        out.append(callout_raw(spec.get("callout", "note"), titre, body, spec.get("repli", "")))
    return out


def unknown_rubrique_keys(obj: dict) -> list:
    """Clés qui RESSEMBLENT à une rubrique (remarques_*, objectifs_*...) mais ne sont pas déclarées :
    typos probables (ex. `rremarques_pedagogiques_ecueils_classiques`). Sert à tools/check_evolutions.py."""
    reg = rubriques_registry()
    bad = []
    for k in obj or {}:
        if k in reg:
            continue
        for known in reg:
            if k != known and len(known) > 6 and known in k:
                bad.append((k, known))
                break
    return bad


# ----------------------------------------------------------------------
# aller_plus_loin (filtré par niveau selon le profil) à tous les niveaux
# ----------------------------------------------------------------------

def filter_apl(apl, niveaux):
    """aller_plus_loin : dict {niveau: texte} (ancien) ou liste {niveau, titre, texte} (actuel),
    gardé seulement pour les niveaux du profil ; texte nettoyé LaTeX -> Markdown. None si rien."""
    niveaux = set(niveaux or [])
    if not apl or not niveaux:
        return None
    if isinstance(apl, dict):
        res = {k: clean_text_for_web(v) for k, v in apl.items() if k in niveaux}
    else:
        res = []
        for it in apl:
            if isinstance(it, dict) and it.get("niveau") in niveaux:
                it = dict(it)
                for k in ("texte", "titre"):
                    if isinstance(it.get(k), str):
                        it[k] = clean_text_for_web(it[k])
                res.append(it)
    return res or None
