#!/usr/bin/env python3
"""
Contrôle des réglages de build/config.yaml ajoutés avec les évolutions « types / rubriques / fichiers / QCM » :

  - fichiers:           matière/type/document/exercice existants ; fichier statique présent ; `cible:` connue
                        dans `targets:` ; deux fichiers de même nom (un seul serait hébergé)
  - qcm.liens:          chapitre existant ; document / exercice existants
  - rubriques:          clés YAML qui ressemblent à une rubrique sans en être une (typo : `rremarques_...`)
  - profils:            `rubriques:` d'un profil ne cite que des rubriques connues
  - types_documents:    sous-dossiers de data/matieres/<m>/ qui ne correspondent à aucun type déclaré
  - publication:        avertit si un profil « prof » (all_prof / all) sert le site

Code de sortie 1 s'il y a des ERREURS (les avertissements ne bloquent pas).
Usage : python3 tools/check_evolutions.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))
import common_data as cd  # noqa: E402
import qcm_data  # noqa: E402
from web import fichiers_joints  # noqa: E402
from web.rubriques_md import unknown_rubrique_keys  # noqa: E402

errors, warnings = [], []
err, warn = errors.append, warnings.append


def docs_of(m: str, ty: str) -> list:
    return cd.list_docs_cours(m, ty) if cd.doc_types()[ty]["forme"] == "sections" else cd.list_docs_td_like(m, ty)


def main() -> int:
    cfg = cd.load_build_config()
    matieres = cd.list_matieres()
    types = cd.doc_types()
    targets = {t["name"] for t in cfg.get("targets", [])}

    # --- fichiers rattachés -------------------------------------------------
    names = {}
    for m, tys in (cfg.get("fichiers") or {}).items():
        if m not in matieres:
            err(f"fichiers: matière « {m} » inexistante")
            continue
        for ty, docs in (tys or {}).items():
            if ty not in types:
                err(f"fichiers: {m}/{ty} : type inconnu (types : {', '.join(types)})")
                continue
            existing = docs_of(m, ty)
            for doc, node in (docs or {}).items():
                if doc not in existing:
                    err(f"fichiers: {m}/{ty}/{doc} n'existe pas")
                    continue
                exs = []
                if types[ty]["forme"] == "exercices":
                    _, exercices = cd.load_td(m, doc, type_doc=ty)
                    exs = [e["slug"] for e in exercices]
                for ex_slug in (list((node.get("exercices") or {}).keys()) if isinstance(node, dict) else []):
                    if ex_slug not in exs:
                        err(f"fichiers: {m}/{ty}/{doc} : exercice « {ex_slug} » inexistant")
                for ex in [None] + (list((node.get("exercices") or {}).keys()) if isinstance(node, dict) else []):
                    for e in fichiers_joints.entries(m, ty, doc, ex):
                        where = f"{m}/{ty}/{doc}" + (f"/{ex}" if ex else "")
                        if e.get("cible"):
                            if e["cible"] not in targets:
                                err(f"fichiers: {where} : cible « {e['cible']} » absente de targets:")
                        elif e.get("fichier"):
                            path = fichiers_joints.resolve_static(m, e["fichier"])
                            if not path:
                                warn(f"fichiers: {where} : data/matieres/{m}/{e['fichier']} introuvable "
                                     "(le lien n'apparaîtra pas tant que le fichier n'y est pas)")
                            else:
                                if names.setdefault(path.name, path) != path:
                                    err(f"fichiers: deux fichiers rattachés s'appellent « {path.name} » (renomme l'un)")
                        else:
                            err(f"fichiers: {where} : entrée sans `cible:` ni `fichier:` : {e}")
                        if e.get("public", "eleve") not in ("eleve", "prof"):
                            err(f"fichiers: {where} : public « {e.get('public')} » (attendu : eleve | prof)")
                        profs_known = cd.load_visibility_profiles()
                        for key in ("profils", "sauf"):
                            for pn in ([] if e.get(key) is None else ([e[key]] if isinstance(e[key], str) else e[key])):
                                if cd.expand_profile(pn) not in profs_known:
                                    err(f"fichiers: {where} : {key}: « {pn} » n'est ni un profil ni un état "
                                        f"(profils : {', '.join(profs_known)} ; états : {', '.join(cd.etats())})")
                        valid_flags = set(cd.SHARED_FLAGS) | {f"show_{k}" for k in cd.rubriques_registry()}
                        for fl in ([] if e.get("si") is None else ([e["si"]] if isinstance(e["si"], str) else e["si"])):
                            if fl not in valid_flags:
                                err(f"fichiers: {where} : si: « {fl} » inconnu (réglages : {', '.join(sorted(valid_flags))})")

    # --- liens QCM ------------------------------------------------------------
    for m, chaps in ((cfg.get("qcm") or {}).get("liens") or {}).items():
        if m not in matieres:
            err(f"qcm.liens: matière « {m} » inexistante")
            continue
        known = {c["id"] for c in qcm_data.chapitres(m)}
        for chap, targets_list in (chaps or {}).items():
            if chap not in known:
                err(f"qcm.liens: {m} : chapitre « {chap} » inconnu (chapitres avec questions : {', '.join(sorted(known)) or 'aucun'})")
            for t in targets_list or []:
                ty, doc, ex = t.get("type"), t.get("doc"), t.get("exercice")
                if ty not in types:
                    err(f"qcm.liens: {m}/{chap} : type « {ty} » inconnu")
                elif doc not in docs_of(m, ty):
                    err(f"qcm.liens: {m}/{chap} : {ty}/{doc} n'existe pas")
                elif ex:
                    _, exercices = cd.load_td(m, doc, type_doc=ty)
                    if ex not in [e["slug"] for e in exercices]:
                        err(f"qcm.liens: {m}/{chap} : exercice « {ex} » absent de {ty}/{doc}")

    # --- rubriques : clés qui ressemblent à une rubrique sans en être une ------
    for m in matieres:
        for ty in cd.exercise_types():
            for doc in cd.list_docs_td_like(m, ty):
                meta, exercices = cd.load_td(m, doc, type_doc=ty)
                for where, obj in [(f"{m}/{ty}/{doc}/_meta", meta)] + [(f"{m}/{ty}/{doc}/{e['slug']}", e) for e in exercices]:
                    for k, known in unknown_rubrique_keys(obj):
                        warn(f"rubriques: {where} : clé « {k} » ressemble à « {known} » (faute de frappe ? elle n'est pas affichée)")
                    for q in obj.get("questions", []) or []:
                        for k, known in unknown_rubrique_keys(q):
                            warn(f"rubriques: {where}/{q.get('id')} : clé « {k} » ressemble à « {known} »")

    # --- profils ---------------------------------------------------------------
    reg = cd.rubriques_registry()
    profiles = cd.load_visibility_profiles()
    for pname, opts in profiles.items():
        sel = opts.get("rubriques") or []
        for item in ([sel] if isinstance(sel, str) else sel):
            key = str(item).lstrip("-")
            if key not in reg and key not in ("@public", "@tous"):
                err(f"profil {pname} : rubrique « {item} » inconnue (déclarées : {', '.join(reg)})")
        for a in cd.profile_audiences(opts):
            if a not in ("eleve", "prof"):
                err(f"profil {pname} : public « {a} » (attendu : eleve | prof)")
    # profil élève qui active une rubrique enseignant via show_<nom> : voulu ? (fuite possible sur un site public)
    for pname, opts in profiles.items():
        if "prof" not in cd.profile_audiences(opts):
            leaked = [k for k in cd.visible_rubriques(opts) if reg[k].get("public") == "prof"]
            if leaked:
                warn(f"profil {pname} : public [eleve] mais affiche des rubriques ENSEIGNANT ({', '.join(leaked)}) "
                     f"via show_<nom>/rubriques -- visibles de tout visiteur si ce profil sert un site public")
    # cibles PDF : `visibilite:` doit désigner un profil ou un état
    for t in cfg.get("targets", []):
        if t.get("visibilite") and cd.expand_profile(t["visibilite"]) not in profiles:
            err(f"targets: « {t.get('name')} » : visibilite « {t['visibilite']} » inconnue (profils : {', '.join(profiles)} ; états : {', '.join(cd.etats())})")
    for k, v in reg.items():
        if v.get("public") not in ("eleve", "prof"):
            err(f"rubrique {k} : public « {v.get('public')} » (attendu : eleve | prof)")
        if v.get("position") not in ("debut", "fin"):
            err(f"rubrique {k} : position « {v.get('position')} » (attendu : debut | fin)")

    # --- types : dossiers non déclarés -----------------------------------------
    for m in matieres:
        for d in sorted((cd.DATA_DIR / m).iterdir()):
            if d.is_dir() and d.name not in types and d.name not in ("qcm", "fichiers") and not cd.is_ignored_name(d.name):
                warn(f"types_documents: data/matieres/{m}/{d.name}/ n'est pas un type déclaré -> ignoré "
                     f"(ajoute `{d.name}: {{label: ..., forme: exercices}}` dans config.yaml > types_documents)")

    # --- états de chapitre : chacun doit désigner un profil existant -------------
    for etat, prof in cd.etats().items():
        if prof not in profiles:
            err(f"publication.etats : « {etat} » -> profil « {prof} » inconnu (profils : {', '.join(profiles)})")
        if etat in profiles:
            warn(f"publication.etats : « {etat} » porte aussi le nom d'un profil ; c'est l'ÉTAT qui l'emporte (renomme l'un des deux)")

    # --- publication : profil « prof » sur le site ------------------------------
    pub = cfg.get("publication") or {}
    used = set()

    def collect(x):
        if isinstance(x, str):
            used.add(x)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k in ("profil", "etat", "defaut") or isinstance(v, (str, dict)):
                    collect(v)
    for m in (pub.get("matieres") or {}).values():
        for ty, docs in m.items():
            if ty == "defaut":
                collect(docs)
            elif isinstance(docs, dict):
                for entry in docs.values():
                    collect((entry.get("profil") or entry.get("etat")) if isinstance(entry, dict) else entry)
                    if isinstance(entry, dict):
                        for v in (entry.get("exercices") or {}).values():
                            collect(v)
    collect(pub.get("defaut"))
    used = {cd.expand_profile(n) for n in used}                  # un état compte pour son profil
    teacher = sorted(n for n in used if n in profiles and "prof" in cd.profile_audiences(profiles[n]))
    if teacher:
        warn(f"publication: profil(s) {', '.join(teacher)} -> le site affichera le contenu ENSEIGNANT et les fiches. "
             "Pour un site public, utilise all_eleve.")

    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")
    print(f"\n{len(errors)} erreur(s), {len(warnings)} avertissement(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
