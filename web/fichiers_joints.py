#!/usr/bin/env python3
"""
Fichiers RATTACHÉS à un document (TD, TP, mini-projet, cours...) ou à un exercice.

Déclarés dans build/config.yaml > fichiers :

    fichiers:
      mecanique-de-point-ipsa:                 # matière
        projet:                                # type de document (td | tp | projet | cours | ...)
          projet1_Tsiolkovski:                 # document (nom du dossier / du fichier)
            document:                          # fichiers affichés sur la page du document ET dans la liste de la matière
              - {label: "Fichier Excel – Falcon 9", fichier: "fichiers/Phv111_MP_Falcon9_Launch.xlsx"}
              - {cible: projet1_PhV111_enonces}          # un PDF CONSTRUIT par l'appli (nom d'une cible de `targets:`)
            exercices:                         # fichiers affichés sur la page d'un exercice
              s2_falcon9:
                - {label: "Tableur Falcon 9", fichier: "fichiers/Phv111_MP_Falcon9_Launch.xlsx"}
                - {label: "Fiche prof", cible: projet1_PhV111_fiche, public: prof}

Deux sortes d'entrées :
  cible:   nom d'une cible PDF de `targets:`. Le fichier est construit par build/build.py ; il n'apparaît que
           s'il existe ET si le profil du document autorise son type (énoncé / aides / corrigé / fiche...).
  fichier: fichier statique (xlsx, csv, zip, ipynb, docx...) rangé dans data/matieres/<matiere>/ (dossier
           conseillé : fichiers/). Copié dans build/public/pdfs/ -> adresse /pdfs/<nom du fichier>.
Champs communs : label (texte du lien), public: eleve (défaut) | prof (visible seulement si le profil sert `prof`).
POUR QUELS PROFILS (optionnel, se combinent : il faut que TOUTES les conditions soient vraies) :
  profils: [corrige_complet, all_eleve]    visible SEULEMENT avec ces profils (un état comme `termine` est accepté)
  sauf:    [avant_seance]                  visible avec tous les profils SAUF ceux-là
  si:      show_correction                 visible seulement si ce réglage du profil est vrai (ou une liste de réglages) :
                                           suit automatiquement les profils que tu ajoutes. N'importe quel show_* de
                                           web/visibility_profiles.yaml : show_correction, show_solution, show_prerequis...
Sans aucune de ces trois clés : visible avec tous les profils (dans la limite de `public`).
Le site (.md) ET l'hébergement (/pdfs/) suivent : un fichier non visible pour le profil n'a ni lien ni copie publique.
Raccourci : une simple chaîne = {fichier: chaîne}. Une liste directement sous le document = `document:`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "build"))
import pdf_status  # noqa: E402
from common_data import (  # noqa: E402
    DATA_DIR, load_build_config, load_visibility_profiles, resolve_profile, profile_audiences,
    expand_profile, flag_value,
)

KIND_LABEL = {"enonce": "Énoncé", "aides": "Aides", "corrige": "Corrigé", "autre": "PDF", "fiche": "Fiche enseignant"}


def _config() -> dict:
    return load_build_config().get("fichiers") or {}


def _normalize(e) -> dict:
    if isinstance(e, str):
        return {"fichier": e}
    return dict(e or {})


def entries(matiere: str, type_doc: str, doc_slug: str, ex_slug: str = None) -> list:
    """Entrées déclarées pour un document (ex_slug=None) ou pour un de ses exercices."""
    node = ((_config().get(matiere) or {}).get(type_doc) or {}).get(doc_slug)
    if node is None:
        return []
    if isinstance(node, list):
        doc_e, ex_e = node, {}
    else:
        doc_e, ex_e = node.get("document") or [], node.get("exercices") or {}
    raw = (ex_e.get(ex_slug) or []) if ex_slug else doc_e
    return [_normalize(e) for e in raw]


def resolve_static(matiere: str, rel: str):
    """Chemin d'un fichier statique (relatif à data/matieres/<matiere>/), None s'il n'existe pas
    ou sort du dossier de la matière (pas de « .. »)."""
    base = (DATA_DIR / matiere).resolve()
    path = (base / rel).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path


def _as_list(v) -> list:
    return [] if v is None else ([v] if isinstance(v, str) else list(v))


def entry_visible(e: dict, pname: str, opts: dict) -> bool:
    """Une entrée de `fichiers:` est-elle visible avec le profil `pname` (de réglages `opts`) ?
    public (élève / prof) ET profils ET sauf ET si doivent tous être satisfaits."""
    if e.get("public", "eleve") not in profile_audiences(opts):
        return False
    if e.get("profils") is not None and pname not in {expand_profile(p) for p in _as_list(e["profils"])}:
        return False
    if pname in {expand_profile(p) for p in _as_list(e.get("sauf"))}:
        return False
    return all(flag_value(opts, f) for f in _as_list(e.get("si")))


def links_for(matiere, type_doc, doc_slug, ex_slug, opts, manifest, warn=None, pname=None) -> list:
    """[(label, url)] des fichiers rattachés VISIBLES avec le profil `pname` (réglages `opts`) : jamais un corrigé
    en avant_seance, jamais un fichier `public: prof` dans un profil élève, jamais un fichier dont
    `profils` / `sauf` / `si` excluent ce profil."""
    warn = warn or (lambda m: None)
    allowed = set(opts.get("pdf_publies", ["enonce"]))
    out, seen = [], set()
    for e in entries(matiere, type_doc, doc_slug, ex_slug):
        if not entry_visible(e, pname, opts):
            continue
        if e.get("cible"):
            m = manifest.get(e["cible"])
            if not m or not pdf_status.is_published(m, allowed):
                continue
            label, url = e.get("label") or KIND_LABEL.get(m.get("kind"), "PDF"), f"/pdfs/{m['pdf']}"
        elif e.get("fichier"):
            path = resolve_static(matiere, e["fichier"])
            if not path:
                warn(f"fichier introuvable : data/matieres/{matiere}/{e['fichier']} "
                     f"(rattaché à {type_doc}/{doc_slug}{'/' + ex_slug if ex_slug else ''})")
                continue
            label, url = e.get("label") or path.name, f"/pdfs/{path.name}"
        else:
            warn(f"entrée sans `cible:` ni `fichier:` ({type_doc}/{doc_slug}) : {e}")
            continue
        if url not in seen:
            seen.add(url)
            out.append((label, url))
    return out


def hosting_needs(forced=None, profiles=None) -> tuple:
    """Pour build/public/pdfs/ : (fichiers statiques {nom: chemin}, PDF rattachés [(cible, types_autorisés)],
    noms en conflit). Ne retient que ce qui est VISIBLE avec le profil de chaque document (même règle que
    links_for), pour que le site n'héberge jamais un fichier que plus aucune page ne montre ; les PDF
    rattachés sont ensuite filtrés par pdf_status.is_published avec ces types autorisés."""
    profiles = profiles or load_visibility_profiles()
    statics, pdf_targets, conflicts = {}, [], []
    for matiere, types in _config().items():
        for type_doc, docs in (types or {}).items():
            for doc_slug, node in (docs or {}).items():
                ex_keys = [None] + (list((node.get("exercices") or {}).keys()) if isinstance(node, dict) else [])
                for ex in ex_keys:
                    pname = resolve_profile(matiere, type_doc, doc_slug, ex_slug=ex, forced=forced)
                    opts = profiles[pname]
                    for e in entries(matiere, type_doc, doc_slug, ex):
                        if not entry_visible(e, pname, opts):
                            continue
                        if e.get("cible"):
                            pdf_targets.append((e["cible"], frozenset(opts.get("pdf_publies", ["enonce"]))))
                        elif e.get("fichier"):
                            path = resolve_static(matiere, e["fichier"])
                            if not path:
                                continue
                            if path.name in statics and statics[path.name] != path:
                                conflicts.append(path.name)
                            statics[path.name] = path
    return statics, pdf_targets, sorted(set(conflicts))
