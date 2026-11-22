# CoursOndes — moteur de cours multi-matières

À partir d'**une seule source de vérité** (des fichiers YAML dans `data/`), ce
projet génère :

| Sortie | Outil | Où ça atterrit |
|---|---|---|
| **PDF** (LaTeX) : énoncés, aides, corrigés, fiches enseignant | `build/build.py` | `build/output/*.pdf` |
| **Pages Markdown** pour le site **Quartz 5** (avec liens → graphe) | `web/export_markdown.py` | `../Quartz5/content/` |
| **QCM en direct** (HTML + QR code, réponses stockées par Flask) | `web/build_qcm_artifact.py` | `build/output/qcm_app_<matiere>.html` |
| **Figures** TikZ → SVG | `figures/render_web.py` | `web/public/figures/` |
| **Animations** matplotlib → GIF/MP4 | `animations/generate_all.py` | `animations/outputs/` |
| **Notebooks** Jupyter | `notebooks/build_notebooks.py` | `notebooks/generated/` |
| **JSON** (site interactif) | `web/export_json.py` | `web/public/data/<profil>/` |
| **Hébergement** (ce que nginx sert vraiment) | `web/publish_hosting.py` | `build/public/` |

Ce README est fait pour être **relu dans six mois** (ou donné à une IA) : il
explique le *pourquoi* autant que le *comment*. Les documents voisins :

- `data/SCHEMA.md` — format exact de chaque fichier YAML (champs d'un exercice, d'un cours, d'un QCM…)
- `DEPLOY_RASPBERRY.md` — installation et déploiement sur le Raspberry Pi
- `web/README.md` — l'appli QCM (attention : le fichier s'appelle maintenant `qcm_app_<matiere>.html`)
- `CHANGES.md` — journal des grosses évolutions (hébergement, fait/défait, profils par document, couleur de l'anglais)

---

## Sommaire

1. [En bref : les commandes à connaître](#1-en-bref--les-commandes-à-connaître)
2. [Vocabulaire](#2-vocabulaire)
3. [Carte du dépôt](#3-carte-du-dépôt)
4. [Installation](#4-installation)
5. [Aide-mémoire des commandes (et lesquelles sont sûres à relancer)](#5-aide-mémoire-des-commandes)
6. [Ajouter du contenu](#6-ajouter-du-contenu)
7. [`build/config.yaml` en détail](#7-buildconfigyaml-en-détail)
8. [Profils de visibilité : qui voit quoi, quand](#8-profils-de-visibilité--qui-voit-quoi-quand)
9. [Le graphe des sujets (`data/graph/sujets.yaml`)](#9-le-graphe-des-sujets-datagraphsujetsyaml)
10. [« Fait / défait » : l'état des PDF](#10-fait--défait--létat-des-pdf)
11. [Hébergement et URL](#11-hébergement-et-url)
12. [Ce qui arrive dans Quartz (règles de génération)](#12-ce-qui-arrive-dans-quartz-règles-de-génération)
13. [L'anglais en couleur (`colorEN`)](#13-langlais-en-couleur-coloren)
14. [Pièges des données YAML](#14-pièges-des-données-yaml)
15. [Déploiement sur le Raspberry Pi](#15-déploiement-sur-le-raspberry-pi)
16. [Dépannage](#16-dépannage)
17. [Faire évoluer le projet (pour toi ou pour une IA)](#17-faire-évoluer-le-projet)

---

## 1. En bref : les commandes à connaître

```bash
source .venv/bin/activate

python3 tools/check_data.py                     # 1. la base YAML est-elle saine ?
python3 build/pdf_status.py                     # 2. quels PDF sont faits / périmés / à faire ?
python3 build/build.py --stale                  # 3. (re)compile seulement ce qui manque ou a changé
./web/publish_profile.sh auto                   # 4. publie tout selon build/config.yaml (publication:)
python3 web/serve_local.py                      # 5. voir le site en local : http://127.0.0.1:8091
```

```bash
python3 build/build.py --log
```

> Les commentaires `# …` ci-dessus sont à **ne pas** copier sur la ligne d'une
> commande dans zsh : zsh les passerait comme arguments. Copie les commandes seules.

Le cycle de travail normal :

```
éditer data/**/*.yaml   →   check_data   →   build --stale   →   publish_profile auto   →   serve_local (relire)   →   git push (tools/Mac/push.sh)
```

---

## 2. Vocabulaire

| Mot | Sens |
|---|---|
| **matière** | un dossier de `data/matieres/` (ex. `physique-ondes-ipsa`). Décrite par `_matiere.yaml`. |
| **document** | un cours (fichier `cours/xxx.yaml`), un TD (dossier `td/xxx/`) ou un TP (dossier `tp/xxx/`). |
| **exercice** | un fichier `exN_xxx.yaml` dans un dossier de TD/TP. Son numéro = sa **position dans `exercices_ordre`** (pas son nom). |
| **cible** | une entrée de `targets:` dans `build/config.yaml` = **un PDF** à produire (un document + des options d'affichage). Un même TD a plusieurs cibles : `_enonce`, `_aides`, `_corrige`, `_fiche`. |
| **type de PDF** (« kind ») | déduit du **suffixe du nom de la cible** : `_enonce`/`_enonces` → énoncé ; `_aide`/`_aides` → aides ; `_corrige` → corrigé ; `_fiche` → fiche enseignant ; tout autre nom → « autre ». |
| **profil de visibilité** | un niveau de dévoilement : `avant_seance`, `pendant_seance_avec_indices`, `corrige_resultats_seuls`, `corrige_complet`, `all` (voir §8). |
| **sujet** | un concept qui a sa propre page Quartz et un nœud dans le graphe (§9). |
| **namespace Quartz** | `quartz_namespace` dans `_matiere.yaml` : le sous-dossier de `Quartz5/content/` où atterrit la matière. Un namespace = une seule matière. |
| **fait / défait** | état d'un PDF : fait (à jour), périmé, à faire… (§10). |
| **`colorEN`** | la couleur nommée de l'anglais (§13). Dans les YAML on écrit toujours `{\color{blue} …}`. |
| **publier** | pour un PDF : le mettre en ligne. Décidé par le profil du document, ou forcé par `publier: true/false` dans la cible. |

---

## 3. Carte du dépôt

```
cours-exerxices-recherches/
├── data/                         ← LA source de vérité (tu n'écris QUE ici + config.yaml)
│   ├── SCHEMA.md                    format des YAML
│   ├── graph/sujets.yaml            graphe des sujets (§9)
│   └── matieres/<matiere>/
│       ├── _matiere.yaml            nom, namespace Quartz, sujets, thème du QCM
│       ├── td/<doc>/_meta.yaml + exN_xxx.yaml
│       ├── tp/<doc>/…               (même forme que td)
│       ├── cours/<doc>.yaml         (un seul fichier, sections de prose)
│       └── qcm/*.yaml               QCM de réveil
├── build/
│   ├── config.yaml                  ← LE fichier de pilotage : auteurs, couleurs, publication, cibles PDF
│   ├── build.py                     génère .tex puis PDF
│   ├── pdf_status.py                « fait / défait » (état des PDF, manifest.json)
│   ├── generated/                   (.tex/.log intermédiaires — jetable)
│   ├── output/                      PDF + manifest.json + status.json + qcm_app_*.html (dossier de travail, JAMAIS servi tel quel)
│   └── public/                      ce que nginx sert : pdfs/, qcm/, graph.json (généré par publish_hosting)
├── templates/                    LaTeX (Jinja2 avec \VAR{} et \BLOCK{})
│   ├── td.tex.j2, cours.tex.j2, exercice*.tex.j2, section.tex.j2, preamble.tex.j2
│   └── styles/                      theme_academique.tex (couleurs colorOne..Six), monstyletikz.tex (style TikZ), packages.tex …
├── common_data.py                ← cœur partagé : chargement des YAML, profils, nettoyage web, titres FR/EN, couleurs
├── web/
│   ├── visibility_profiles.yaml     les profils (§8)
│   ├── publish_profile.sh           LA commande de publication (enchaîne tout)
│   ├── export_markdown.py           → pages Quartz
│   ├── export_json.py               → JSON
│   ├── build_subject_links.py       injecte les « Sujets liés » dans les pages Quartz
│   ├── build_qcm_artifact.py        génère qcm_app_<matiere>.html depuis qcm_app_template.html
│   ├── publish_hosting.py           synchronise build/public/ (PDF faits+autorisés, QCM, graph.json)
│   ├── sync_quartz_assets.py        copie figures/animations/PDF publiés dans Quartz5/content/
│   ├── serve_local.py               serveur local qui imite nginx
│   ├── server/app.py                API Flask des QCM (SQLite)
│   └── public/                      figures/ (SVG rendus), data/ (JSON) — générés
├── figures/                      tikz/<ref>.tex (sources) + render_web.py (→ SVG)
├── animations/                   src/<ref>.py (sources matplotlib) + generate_all.py (→ outputs/)
├── notebooks/                    build_notebooks.py (→ generated/)
├── tools/
│   ├── check_data.py                contrôle d'intégrité des YAML
│   ├── add_config_blocks.py         ajoute couleurs:/publication: à config.yaml (une fois)
│   ├── check_quartz_links.py        wikilinks cassés, PDF/QCM absents, pages orphelines
│   ├── Mac/push.sh                  git add/commit/pull --rebase/push
│   └── Raspberry/setup.sh, update_code.sh
├── deploy/                       nginx-cours.conf, gunicorn-cours.{service,socket}
├── manage.py                     liste / état disque / ménage
├── run.sh, start_tunnel.sh, stop_tunnel.sh
└── requirements.txt
```

Un **dossier frère** est attendu : `../Quartz5/` (le dépôt Quartz 5, séparé).
Si le tien porte un autre nom, passe `QUARTZ_CONTENT=/chemin/vers/content` (§5).

---

## 4. Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt     # Jinja2, PyYAML, nbformat, flask, gunicorn, numpy, matplotlib
```

Outils système (hors Python) :

| Besoin | Pour quoi |
|---|---|
| **TeX Live complet** (`pdflatex`, avec `babel` français, `tikz`, `hobby`, `standalone`, `ifsym`, `anyfontsize`, `bm`…) | PDF et figures |
| **`pdftocairo`** (poppler) | conversion PDF → SVG des figures |
| **Node.js** récent (≥ 22 recommandé pour Quartz) + `npm install` dans `../Quartz5/` | build du site Quartz (`npx quartz build`) |
| `ffmpeg` (optionnel) | MP4 des animations (sinon GIF seulement) |
| `qpdf` (optionnel) | chiffrer une fiche enseignant (voir §8.6) |

Première fois pour Quartz : `cd ../Quartz5 && npm install`.

---

## 5. Aide-mémoire des commandes

La colonne **« Sûr à relancer ? »** répond à : *« est-ce que ça peut écraser ce que j'ai fait à la main ? »*

| Commande | Quand | Sûr à relancer ? |
|---|---|---|
| `python3 tools/check_data.py` | Après toute modif de `data/` ou `config.yaml`. Syntaxe de **tous** les YAML d'abord (fichier + ligne), puis ids, namespaces, ordre des exercices, noms NFD, liens du graphe, QCM, cibles, `publication:`. Code retour 1 si erreur. | ✅ ne modifie rien |
| `python3 tools/add_config_blocks.py` | **Une seule fois**, pour créer `couleurs:` et `publication:` dans `config.yaml`. | ✅ voir encadré ci-dessous |
| `python3 build/pdf_status.py` | Voir ce qui est fait / périmé / à faire (`--write` réécrit manifest+status, `--todo` liste les noms à refaire, `--json`). | ✅ lecture seule (sauf `--write`) |
| `python3 build/build.py` | Compile **toutes** les cibles. | ✅ (long) |
| `python3 build/build.py --stale` | Compile seulement les PDF manquants ou périmés. **L'usage courant.** | ✅ |
| `python3 build/build.py --missing` | Seulement les manquants. | ✅ |
| `python3 build/build.py td1_PhV212_enonce td1_PhV212_corrige` | Des cibles précises. `--no-pdf` : .tex seulement ; `--log` / `--full-log` : afficher les erreurs LaTeX. | ✅ |
| `./web/publish_profile.sh auto` | **La** commande de publication : profil de chaque document d'après `publication:`. | ✅ (ne touche pas tes notes Quartz manuscrites) |
| `./web/publish_profile.sh corrige_complet` | **Force** ce profil pour tous les documents (ignore `publication:`). Idem `all`, etc. | ✅ |
| `./web/publish_profile.sh auto --matiere physique-ondes-ipsa` | Limite JSON / Markdown / notebooks à une matière. | ✅ |
| `QUARTZ_CONTENT=/autre/chemin/content ./web/publish_profile.sh auto` | Quartz ailleurs que `../Quartz5`. | ✅ |
| `CREATE_MISSING=1 ./web/publish_profile.sh auto` | Crée aussi les pages-sujets absentes de Quartz (`*Page à compléter.*`). | ✅ ne réécrit jamais une page existante |
| `python3 web/serve_local.py` | Voir le site en local (Quartz + `/pdfs/` + `/qcm/` + API). `--port`, `--quartz-public`. | ✅ |
| `python3 tools/check_quartz_links.py` | Vérifie les liens. Défaut : `../Quartz5/content`. | ✅ lecture seule |
| `python3 figures/render_web.py [--force]` | Recompile les SVG (aussi appelé par publish). | ✅ |
| `python3 animations/generate_all.py [--force] [--no-latex]` | Régénère les GIF. | ✅ |
| `python3 web/export_markdown.py --profile auto --out /tmp/q/content` | **Tester l'export sans toucher à Quartz** (sortie dans un dossier jetable). | ✅ |
| `python3 manage.py list \| status \| disk-usage \| clean …` | Vue d'ensemble disque et ménage (`clean pdf`, `clean frames`, `clean md`, `clean all --yes`). Ne touche jamais à `data/`. | ⚠️ `clean` supprime des fichiers générés |
| `tools/Mac/push.sh "message"` | `git add . && commit && pull --rebase && push`. | ✅ |

> **`add_config_blocks.py` si tu as déjà configuré à la main ?** Oui, tu peux le
> lancer : le fichier est lu comme du YAML ; si la clé `couleurs:` existe déjà,
> elle n'est pas touchée ; si `publication:` existe déjà, idem. Si les deux
> existent, il répond « Rien à ajouter » et **n'écrit rien**. Il n'ajoute que
> ce qui manque, par simple insertion de texte juste avant `targets:` (tes
> commentaires et tes cibles ne bougent pas). `--dry-run` montre ce qu'il ferait.
> Il ne **complète pas** `publication:` quand tu crées de nouveaux documents :
> `--complete` se contente de les **lister**.

---

## 6. Ajouter du contenu

### 6.1 Un TD ou un TP dans une matière existante

```bash
mkdir -p data/matieres/physique-ondes-ipsa/td/td4_mon_td
```

`_meta.yaml` :

```yaml
id: td4
titre: "Mon TD {\\color{blue}My tutorial}"     # l'anglais est optionnel (§13) ; ATTENTION aux guillemets (§14)
chapitre_cours: "Chap. 4 — …"
seance: 5
niveau_public: [cpge, licence]
exercices_ordre: [ex1_premier, ex2_second]      # SEULS ceux listés sont publiés ; l'ordre donne les numéros
```

Un fichier par exercice (`ex1_premier.yaml`, …) : tous les champs dans `data/SCHEMA.md`.
Pour un **TP**, même chose dans `tp/`.

Puis, **trois endroits** à renseigner :

1. **Cible(s) PDF** dans `build/config.yaml` → `targets:` (copie une cible existante, change `name`, `titre`, `doc`). Respecte les suffixes `_enonce / _aides / _corrige / _fiche` (§2).
2. **Profil de publication** dans `build/config.yaml` → `publication:` → `matieres: <matiere>: td:` → `td4_mon_td: avant_seance` (sinon : profil par défaut de la matière).
3. (Optionnel) **sujets** : `sujets: [ondes-mecaniques]` dans `_meta.yaml`, sinon le TD hérite des sujets de la matière (§9).

```bash
python3 tools/check_data.py
python3 build/build.py --stale
./web/publish_profile.sh auto
```

### 6.2 Un cours (prose de lecture)

Un seul fichier : `data/matieres/<m>/cours/chap2_mon_chapitre.yaml` (champs `titre`, `sous_titre`, `sections:` avec `titre/contenu/figure/animation/remarque/aller_plus_loin` — voir SCHEMA.md). Cible avec `type_doc: cours` et `doc: chap2_mon_chapitre`. Profil dans `publication: … cours:`.

### 6.3 Une nouvelle matière

```bash
mkdir -p data/matieres/ma-matiere/{td,cours,qcm}
```

`_matiere.yaml` :

```yaml
id: ma-matiere                          # DOIT être égal au nom du dossier (check_data le vérifie)
nom: "Nom affiché"
niveau: [licence]
description: "Une phrase."
quartz_namespace: physique/ma-matiere   # UNIQUE : deux matières ne peuvent pas partager un namespace
sujets: [mon-sujet]                     # ids de data/graph/sujets.yaml (optionnel)
theme:                                  # optionnel : habillage du QCM
  titre_app: "Réveil de …"
  sous_titre_app: "…"
  logo: onde
```

Rien à coder : `list_matieres()` découvre toute matière qui a un `_matiere.yaml` (ou, à défaut, un sous-dossier `td/tp/cours/qcm` — des valeurs par défaut sont alors utilisées).
Ajoute ensuite la matière dans `publication:` et, si tu veux un nœud dans le graphe, un sujet (§9).

### 6.4 Un QCM

`data/matieres/<m>/qcm/xxx.yaml` : liste de questions.

```yaml
- id: td1_qcm_debut1            # unique dans la matière
  td: td1                       # id (champ `id`) du TD concerné
  moment: debut                 # debut | milieu | fin
  lie_a: td1_ex4                # (ou null) « <id du td>_ex<numéro> » ; numéro = position dans exercices_ordre !
  question: "…"
  animation: {ref: anim_corde_onde, formats: [gif]}   # optionnel
  choix:
    - {id: a, texte: "…", correct: true}
    - {id: b, texte: "…", correct: false}
    - {id: c, texte: "Je ne sais pas encore", correct: false, neutre: true}
  feedback: {correct: "…", incorrect: "…", neutre: "…"}
```

L'appli est `/qcm/<matiere>/`. Les réponses sont stockées par Flask dans SQLite, avec des **clés préfixées par la matière** (`<matiere>::…`) : deux matières peuvent avoir des QCM aux mêmes ids sans se mélanger. ⚠️ Si tu **réordonnes** les exercices, les `lie_a` (`td1_ex4`…) changent de sens.

### 6.5 Une figure TikZ

1. Écris `figures/tikz/<ref>.tex` (utilise les couleurs `colorOne…colorSix` et les macros de `templates/styles/monstyletikz.tex`).
2. Dans le YAML : `figure: {ref: <ref>, legende: "…"}` (ou une **liste** de figures).
3. `python3 figures/render_web.py` → `web/public/figures/<ref en minuscules>.svg`.

Pièges : sur Linux la casse du nom de fichier compte (`<ref>` = nom du `.tex` à l'identique ; l'URL web est mise en minuscules automatiquement). Un `ref` vide ou contenant `???` est ignoré (pas d'image cassée). Une figure n'est recompilée que si son `.tex`, `monstyletikz.tex` ou `render_web.py` a changé (`--force` pour tout refaire).

### 6.6 Une animation

`animations/src/<ref>.py` (script matplotlib) + dans le YAML `animation: {ref: <ref>, formats: [gif], params: {…}}`. `python3 animations/generate_all.py` appelle le bon script avec les `params`. Cache : sortie déjà présente → sauté (`--force`). `--no-latex` : rendu plus rapide.

---

## 7. `build/config.yaml` en détail

Le fichier a **quatre blocs de premier niveau** :

```yaml
profils:        # auteurs possibles (nom, email, statut, bureau) pour l'en-tête des PDF
couleurs:       # couleur de l'anglais (§13)
publication:    # quel profil de visibilité pour chaque cours/TP/TD (§8)
targets:        # la liste des PDF à produire
```

### 7.1 Une cible (`targets:`)

```yaml
- name: td1_PhV212_corrige                 # nom du PDF (build/output/<name>.pdf) ; le SUFFIXE donne le type (enonce/aides/corrige/fiche)
  titre: "TD 1 — Propagation sur une corde"
  matiere: physique-ondes-ipsa
  type_doc: td                             # td | tp | cours (défaut td)
  doc: td1_corde                           # nom du dossier (td/tp) ou du fichier sans .yaml (cours)
  exercices: [ex5_melde, ex6_stationaire]  # (optionnel) sous-ensemble d'exercices pour CE PDF
  etablissement: IPSA                      # (optionnel) promo: A2 · annee: "2026-2027" · auteur: "…"
  publier: false                           # (optionnel) force : true = toujours publié, false = jamais (ignore le profil)
  # --- ce que CE PDF affiche (indépendant des profils du site) ---
  show_figure: true
  show_coup_de_pouce: true
  show_correction: true
  show_solution: true
  show_prerequis: true
  show_point_cours: true
  show_bilan: true
  show_attention: true                             # … et d'autres show_* (voir les cibles existantes)
  show_objectifs_pedagogiques_enseignants: true     # typiquement : seulement dans les *_fiche
  aller_plus_loin_niveaux: [lycee, prepa, licence, master, doctorat]
```

**Deux couches indépendantes — à ne pas confondre :**

1. **Le contenu d'un PDF** est fixé par les `show_*` de **sa cible**. Un `_enonce` doit avoir `show_correction/show_solution: false` ; un `_corrige` les met à `true`. Le profil n'y change rien.
2. **Le profil du document** décide (a) du contenu des **pages Quartz/JSON/notebooks** et (b) **quels PDF sont mis en ligne** (selon leur type).

> ⚠️ Un `*_enonce` avec `show_solution: true` publie des solutions (c'était le cas de `td1_PhV110_enonce` et `td2_PhV110_enonce`). `check_data.py` et `publish_hosting.py` l'affichent en avertissement.

### 7.2 `couleurs:`

```yaml
couleurs:
  anglais: "#1565C0"        # hex ou nom de couleur ("blue", "teal") : PDF ET site
  # anglais_web: "#4A90E2"  # optionnel : autre teinte pour le site seulement (thème sombre)
```

### 7.3 `publication:` (voir aussi §8.3)

C'est ici que tu dis, **pour chaque cours, TP, TD — et au besoin chaque exercice** —, jusqu'où tu dévoiles. Détail et ordre de résolution au §8.3.

### 7.4 Si tu édites `config.yaml` à la main

- L'indentation est en **espaces** (jamais de tabulation).
- Après toute modif : `python3 tools/check_data.py` (profils inconnus, documents/exercices inexistants, noms de cibles en double, sources introuvables).
- Changer `couleurs:` ou un modèle LaTeX rend les PDF « périmés » (§10) : `build.py --stale` les refait.

---

## 8. Profils de visibilité : qui voit quoi, quand

### 8.1 Les cinq profils (`web/visibility_profiles.yaml`)

| Profil | Coups de pouce | Corrections (résultats) | Solutions détaillées | « Aller plus loin » | PDF mis en ligne |
|---|:---:|:---:|:---:|---|---|
| `avant_seance` | ❌ | ❌ | ❌ | aucun | énoncés |
| `pendant_seance_avec_indices` | ✅ | ❌ | ❌ | niveau `lycee` | énoncés, aides |
| `corrige_resultats_seuls` | ✅ | ✅ | ❌ | `lycee`, `cpge` | énoncés, aides, corrigés |
| `corrige_complet` | ✅ | ✅ | ✅ | tous niveaux | + « autre » (hors fiches) |
| `all` | ✅ | ✅ | ✅ | tous niveaux | + **fiches enseignant** |

Dans tous les profils : figures et notes d'animation affichées. « Corrections » = champ `correction` ; « solutions détaillées » = champ `solution`. Les **remarques pour l'enseignant** n'existent que dans les PDF `*_fiche` (jamais sur le site).

Champs d'un profil : `show_figure`, `show_animation_note`, `show_coup_de_pouce`, `show_correction`, `show_solution`, `aller_plus_loin_niveaux`, `pdf_publies` (liste de types), `pdf_suffix`. Le filtrage **retire réellement** les champs des fichiers générés — jamais un simple masquage CSS (`common_data.apply_visibility*`).

### 8.2 Deux façons de publier

```bash
./web/publish_profile.sh auto            # chaque document selon publication: de config.yaml
./web/publish_profile.sh corrige_complet # UN profil forcé partout (ignore publication:)
```

Sans argument = `auto`. Le dernier profil utilisé est mémorisé dans `web/.current_profile` (fichier local, non versionné) ; `update_code.sh` le relit après chaque `git pull` sur le Pi pour ne jamais exposer un corrigé par erreur.

### 8.3 `publication:` — le défaut, le document, l'exercice

```yaml
publication:
  defaut: avant_seance                          # 1. défaut GLOBAL
  matieres:
    physique-ondes-ipsa:
      defaut: pendant_seance_avec_indices       # 2. défaut de la MATIÈRE
      cours:
        chap1_intro: corrige_complet            # 3. un cours (fichier sans .yaml)
      td:
        td1_corde:                              # 3. un TD en forme DÉTAILLÉE
          profil: corrige_complet
          exercices:
            ex3_equation_ondes: avant_seance    # 4. un EXERCICE précis (nom du fichier sans .yaml)
        td2_ondes_sonores: pendant_seance_avec_indices   # 3. un TD en forme COURTE
        # td3 non listé → prend le défaut de la matière
      tp:
        tp1_corde_ressort: avant_seance         # 3. un TP
```

**Ordre de résolution** (`common_data.resolve_profile`) : profil forcé en ligne de commande → exercice → document → défaut de la matière → défaut global → `avant_seance`. Pour un **cours**, on précise le chapitre (le fichier), pas ses sections.

**Scénario de classe** : chapitre terminé → `corrige_complet` ; chapitre en cours → `pendant_seance_avec_indices` ; pas abordé → `avant_seance`. Un exercice déjà corrigé dans un TD en cours → une ligne dans `exercices:`.

Le profil d'un document règle **en même temps** : les pages Quartz, les JSON, les notebooks **et** les PDF en ligne de ce document.

### 8.4 Quels PDF sont mis en ligne

Pour chaque PDF présent sur le disque : profil du document → liste `pdf_publies` du profil → le **type** du PDF (suffixe du nom) doit y figurer. `publier: true/false` dans la cible l'emporte. Les PDF absents du disque ou dont la cible a disparu ne sont **jamais** publiés (§10). L'ordre d'affichage des liens est fixe : **Énoncé · Aides · Corrigé · (autres) · Fiche enseignant**, chacun dans un nouvel onglet.

### 8.5 Créer un nouveau profil

Ajoute une entrée dans `web/visibility_profiles.yaml` (copie-en une, change les `show_*` et `pdf_publies`). Il devient immédiatement utilisable en ligne de commande **et** dans `publication:`. `check_data.py` vérifie que les noms cités existent.

### 8.6 Fiches enseignant et confidentialité

Les `*_fiche` ne sont publiées **que** par le profil `all` (ou `publier: true`). Sur le Pi, tout ce qui est publié est téléchargeable par quiconque connaît l'URL : garde `all` pour un usage local. Chiffrer un PDF à la main : `qpdf --encrypt "<user>" "<owner>" 256 --print=none --extract=n -- in.pdf out.pdf` (c'est le `TP_IPSA_Generale_fiche_pro.pdf` à la racine) — l'hébergement, lui, copie les PDF tels quels.

---

## 9. Le graphe des sujets (`data/graph/sujets.yaml`)

### 9.1 À quoi ça sert

Dans Quartz, le **graphe** est construit à partir des **wikilinks** (`[[page]]`) présents dans les pages. Ce fichier déclare des **concepts (sujets)** et les **relations pondérées** entre eux ; le script transforme ça en wikilinks, donc en arêtes du graphe, et en sections « 🔗 Sujets liés » lisibles.

### 9.2 Format

```yaml
sujets:
  - id: ondes-mecaniques            # identifiant (minuscules, tirets) : celui qu'on cite partout ailleurs
    nom: "Ondes mécaniques"         # nom affiché dans les liens
    quartz_path: physique/ipsa-ondes   # la page Quartz qui porte ce sujet (relatif à content/)

liens:
  - de: theorie-m                   # sujet source
    a: supergravite                 # sujet cible
    poids: 0.9                      # entre -1 et 1 (voir ci-dessous)
    type: parent                    # parent | associe
    note: "La supergravité D=11 est la limite basse énergie de la théorie M."   # affichée dans « Voir aussi »
```

- **`poids`** : force de la relation. Positif = « s'éclairent mutuellement » (0,9 très lié, 0,2 lointain). Négatif = « à distinguer, à ne pas confondre ». Valeur attendue dans `[-1, 1]` (`check_data` vérifie).
- **`type: parent`** : hiérarchie, **`de` est le parent de `a`** → affiché « Sujet parent » / « Sous-sujets ». **`associe`** : lien libre non hiérarchique → « Voir aussi », trié par |poids| décroissant, avec une jauge ●●●●○.
- **`quartz_path`** : page existante (écrite à la main, ex. `physique/theorie-m`) **ou** page générée (ex. `physique/ipsa-ondes` = l'index d'une matière). Plusieurs sujets peuvent pointer vers la **même** page : leurs liens sont **fusionnés** en une seule section.

### 9.3 Comment un sujet est relié au reste

| Où | Effet |
|---|---|
| `_matiere.yaml` → `sujets: [id, …]` | l'index de la matière et ses TD/cours (qui n'ont pas leurs propres `sujets`) pointent vers ces sujets |
| `_meta.yaml` d'un TD/TP ou YAML d'un cours → `sujets: […]` | ce document pointe vers ces sujets (remplace ceux de la matière) |
| `liens:` dans `sujets.yaml` | relations entre sujets → section « Sujets liés » injectée dans les pages |

Un sujet dont la page est la matière elle-même n'est pas re-lié dans la page de la matière (le fil d'Ariane suffit). Un id de sujet inconnu est **ignoré avec un avertissement** (et `check_data` le signale en erreur).

### 9.4 Ce que fait `build_subject_links.py`

```bash
python3 web/build_subject_links.py --quartz-content ../Quartz5/content   # appelé par publish_profile (étape 4bis)
```

- Injecte, dans chaque page concernée, un bloc entre `<!-- SUJETS-LIES:BEGIN -->` et `<!-- SUJETS-LIES:END -->`. **Idempotent** : relancé, il ne duplique rien ; ton texte autour du bloc n'est jamais touché.
- `--seuil 0.3` : ne garde que les liens dont la valeur **absolue** du poids est ≥ 0,3 (un lien fortement négatif « à distinguer » est donc conservé).
- `--create-missing` : crée une page minimale pour tout sujet dont la page n'existe pas (sans quoi le sujet n'est pas un nœud du graphe).
- Valide la base : lien vers un sujet inconnu, `type` invalide, `poids` hors `[-1, 1]`.

### 9.5 Limite à connaître

Le graphe **natif** de Quartz ne voit **pas** les poids ni les types : une arête vaut une arête. Le poids sert à trier les « Voir aussi » (par |poids|), à filtrer avec `--seuil`, et il est exporté dans **`/graph.json`** (nœuds + arêtes pondérées, par `publish_hosting.py`) si un jour tu veux une vue D3 avec épaisseur proportionnelle.

### 9.6 Ajouter un sujet : les 3 gestes

1. `sujets.yaml` → ajouter `{id, nom, quartz_path}` sous `sujets:`.
2. `sujets.yaml` → ajouter au moins un lien sous `liens:` (sinon nœud isolé — `check_data` avertit).
3. L'attacher à une matière ou un document via `sujets: [id]`. Puis `publish_profile.sh`.

---

## 10. « Fait / défait » : l'état des PDF

`build/pdf_status.py` compare **trois choses** : ce que **demande** `config.yaml` (les cibles), ce que contiennent les **sources** (YAML du document + modèles LaTeX), et ce qui **existe** dans `build/output/`.

| État | Signification | Que faire |
|---|---|---|
| ✅ `ok` | PDF présent, fait avec les sources actuelles | rien |
| 🟠 `perime` | PDF présent, mais les sources ont changé depuis | `build.py --stale` |
| 🔵 `present_sans_empreinte` | PDF présent, fait avant ce système (inconnu) | rien (ou le refaire une fois) |
| ⬜ `manquant` | aucun PDF : « à faire » | `build.py --missing` |
| ❌ `cible_cassee` | la source (matière/document) n'existe pas | corriger `config.yaml` ou `data/` |
| (liste) PDF **orphelins** | un PDF dans `build/output/` qu'aucune cible ne produit | non publié ; supprime-le ou ajoute la cible |

**L'empreinte** (hash court dans `manifest.json`) couvre : la définition de la cible, les blocs `profils:` et `couleurs:` de `config.yaml`, `_matiere.yaml`, tous les YAML du document, et **tous les fichiers de `templates/`**. Donc toucher un modèle LaTeX rend **tous** les PDF périmés (normal : ils dépendent tous du modèle).

> ⚠️ **Ne sont pas dans l'empreinte** : les figures `figures/tikz/*.tex`. Si tu modifies une figure, force le PDF : `python3 build/build.py <name>`.

**`manifest.json` et `status.json`** sont **reconstruits d'après le disque** à chaque passage (jamais d'entrée fantôme pour un PDF disparu ou une cible retirée). Ils ne sont **pas versionnés** (`.gitignore`) : le Mac ne doit pas écraser l'état du Pi à chaque `git pull`. `status.json` liste aussi les corrigés non publiés : **ne le sers jamais**.

**Effet sur l'hébergement** : `web/publish_hosting.py` synchronise `build/public/pdfs/` : un PDF supprimé du disque, ou dont la cible a disparu, ou dont le type n'est plus autorisé par le profil, **disparaît** de l'hébergement. Les PDF autorisés mais pas encore faits apparaissent « ⬜ à venir » dans `/pdfs/`.

---

## 11. Hébergement et URL

`build/output/` est un **dossier de travail**. Ce que nginx sert, c'est `build/public/` (préparé par `publish_hosting.py`, avec des liens en dur vers les PDF : pas de doublon de fichiers).

| URL | Source | Rôle |
|---|---|---|
| `/` | `../Quartz5/public/` | le site Quartz |
| `/pdfs/` , `/pdfs/<nom>.pdf` | `build/public/pdfs/` | PDF **publiés** (+ `index.html` : fait / périmé / à venir, par matière) |
| `/qcm/` , `/qcm/<matiere>/` | `build/public/qcm/` | sommaire des QCM, appli d'une matière |
| `/figures/…`, `/animations/…` | `web/public/figures/`, `animations/outputs/` | médias |
| `/graph.json` | `build/public/graph.json` | graphe des sujets pondéré |
| `/api/…` | Flask (`web/server/app.py`, gunicorn) | stockage des réponses QCM (SQLite) |

Configuration : `deploy/nginx-cours.conf` (copié par `update_code.sh`), port interne **8091**.

**Médias dans Quartz.** Les pages Markdown référencent `/figures/…`, `/pdfs/…`, `/animations/…` (chemins absolus depuis la racine du site). Pour qu'elles marchent **aussi avec `npx quartz build --serve`** (qui ne connaît pas nginx), `web/sync_quartz_assets.py` **copie** ces trois dossiers dans `Quartz5/content/figures|animations|pdfs/` (miroir : un média disparu de la source disparaît de `content/`). Ajoute ces trois dossiers au `.gitignore` du dépôt Quartz (fichiers générés, parfois lourds).

**Voir en local** : `python3 web/serve_local.py` imite nginx (écoute sur `127.0.0.1:8091` uniquement). Il faut avoir construit Quartz (`npx quartz build` dans `../Quartz5`, fait par l'étape 7 de `publish_profile.sh`).

### Ce que fait `publish_profile.sh`, dans l'ordre

| Étape | Action |
|---|---|
| 1 | figures SVG (`figures/render_web.py`) |
| 2 | animations (`animations/generate_all.py --no-latex`) |
| 3 | JSON (`web/export_json.py --profile …`) |
| 4 | Markdown → `Quartz5/content/` (`web/export_markdown.py`) |
| 4bis | liens de sujets (`web/build_subject_links.py`) |
| 5 | notebooks (`notebooks/build_notebooks.py`) |
| 6 | QCM (`web/build_qcm_artifact.py`) |
| 6bis | hébergement : PDF faits/autorisés, pages QCM, `graph.json` (`web/publish_hosting.py`) |
| 6ter | copie des médias dans `Quartz5/content/` (`web/sync_quartz_assets.py`) |
| 7 | build Quartz (`npx quartz build`) — sauté si `package.json` introuvable |
| 8 | vérification des liens (`tools/check_quartz_links.py`, non bloquante) |

Le script s'arrête à la **première erreur** (`set -e`) : si une étape échoue (YAML invalide, `npm install` manquant…), les suivantes ne tournent pas.

---

## 12. Ce qui arrive dans Quartz (règles de génération)

Structure (`quartz_namespace` = dossier de la matière) :

```
Quartz5/content/<quartz_namespace>/
    index.md                                  sommaire de la matière
    TD/<chapitre>/<titre-du-doc>/index.md     sommaire du TD (liens PDF, sujets, QCM)
    TD/<chapitre>/<titre-du-doc>/exN-<titre>.md   un fichier par exercice
    TP/…                                      idem pour les TP
    Cours/<doc>.md                            un seul fichier (sections en ##)
```

Règles importantes :

- **Ne modifie jamais ces pages à la main** : elles sont réécrites à chaque publication. Tes notes manuscrites, ailleurs dans `content/`, ne sont **jamais** touchées.
- **Nettoyage des pages « défaites »** : le script note les fichiers qu'il a écrits dans `../Quartz5/.coursondes-generated.json` (à côté de `content/`, ajoute-le au `.gitignore` de Quartz). À la publication suivante, une page qu'il ne génère plus (exercice retiré/renommé, document passé en `publier: false`) est **supprimée**. Seuls ses propres fichiers sont concernés.
- **URL = français seul** : le slug vient du titre sans la partie anglaise. ⚠️ Renommer un titre change l'URL (l'ancienne page est supprimée, les liens externes cassent).
- **Chapitre vide** (`chapitre_cours` absent) → dossier `general`.
- **Collision** de deux documents de même titre dans le même chapitre : le second reçoit `-<id>` ajouté (avertissement).
- **Wikilinks avec chemin complet** depuis la racine de `content/` (namespace inclus) : les liens entre matières et le graphe sont fiables. Un `lie_a` de QCM ne pointe **que** dans sa propre matière.
- **Callouts** Obsidian/Quartz : les **corrections et solutions sont repliées** par défaut (`[!success]-`) — l'étudiant clique pour les voir. Réglage : `COLLAPSE` dans `export_markdown.py` (`+` = ouvert, `-` = replié).
- **Liens PDF** : seulement les PDF présents ET autorisés par le profil du document ; ordre fixe Énoncé · Aides · Corrigé · Fiche enseignant ; ouverture dans un **nouvel onglet** (HTML `<a target="_blank">`, Markdown ne sait pas faire).
- **Figures** : centrées, sur une **carte blanche** (les SVG ont des traits foncés sur fond transparent, invisibles en thème sombre), cliquables (grand format, nouvel onglet).
- **LaTeX de texte → Markdown** (`common_data.clean_text_for_web`), **hors formules** (qui sont protégées) : `{\bf …}`/`\textbf` → gras, `{\it …}`/`\emph` → italique, `enumerate`/`itemize` → listes (`(a)(b)` pour `\alph`), `{\color{…}…}` / `\textcolor` → `<span style="color:…">`, `\colorOne…` → valeur hex du thème. Les formules `$…$`/`$$…$$` restent du LaTeX pour KaTeX.
- **Ignorés** : dossiers/fichiers dont le nom contient ` copie`, commence par `_` ou `.`, ou documents avec `publier: false` dans leur `_meta.yaml` / YAML de cours.

---

## 13. L'anglais en couleur (`colorEN`)

**Convention** : dans les YAML, la partie anglaise (titres, textes) s'écrit `{\color{blue} English…}`. En interne, `common_data.normalize_en_color` redirige `blue` vers une couleur **nommée** `colorEN`, réglée **une seule fois** dans `config.yaml` → `couleurs.anglais`.

| Où | Comment |
|---|---|
| **PDF** | `preamble.tex.j2` définit `\definecolor{colorEN}{HTML}{…}` (ou `\colorlet{colorEN}{nom}`) depuis la config |
| **Site** | `colorEN` → hex (`couleurs.anglais_web` s'il existe, sinon `anglais`) → `<span style="color:#…">` |

Sur le site, un titre bilingue s'affiche **en français** (titre de page, URL, listes) avec **l'anglais en couleur sur une ligne dessous** (le titre de page de Quartz ne peut pas contenir de couleur). Le découpage est fait par `common_data.title_parts()` / `split_en_text()` : tout ce qui est dans un groupe `{\color{colorEN} …}` (ou `\textcolor`) devient la partie anglaise.

⚠️ Comme « blue » veut dire « anglais » partout, n'utilise pas `\color{blue}` pour un vrai bleu : prends `\colorFour` (indigo du thème) ou un hex `\color{#2255AA}`.

---

## 14. Pièges des données YAML

| Piège | Symptôme | Règle |
|---|---|---|
| **Deux-points dans un texte** (`… du fond :` en fin de ligne, ou `: ` au milieu) | `mapping values are not allowed here` | entre guillemets `"…"`, `'…'`, ou en bloc `>` / `|` |
| **Antislash dans un texte entre guillemets doubles** (`"\color"`) | `found unknown escape character` | guillemets **simples** `'…\color…'`, ou bloc `>` ; en `"…"`, doubler : `"\\color"` |
| **Apostrophe dans un texte entre guillemets simples** | texte coupé | la doubler : `'l''eau'` |
| **Accents dans les noms de fichiers** (macOS stocke « é » en NFD, Linux ne retrouve pas le fichier) | fichier introuvable sur le Pi | noms de fichiers/dossiers **ASCII** ; `check_data` signale les NFD ; `resolve_child` est tolérant mais ne remplace pas la règle |
| **Exercice absent de `exercices_ordre`** | exercice non publié | l'ajouter (avertissement de `check_data`) ; l'ordre donne les numéros |
| **`lie_a`/`td` de QCM** | lien vers un mauvais exercice | `<id du td>_ex<numéro>` ; le numéro = position dans `exercices_ordre` |
| **Dossier ` copie`** (copie Finder) | ignoré (pas de doublon) | supprime-le quand tu n'en as plus besoin |
| **`id:` de `_matiere.yaml` ≠ dossier** (copier-coller) | erreur `check_data` | `id` = nom du dossier |
| **Deux matières, même `quartz_namespace`** | leurs `index.md` s'écrasent | un namespace par matière (le script refuse de tourner) |
| **`figure.ref` vide ou `???`** | figure ignorée | normal (gabarit non rempli) ; `check_data` avertit |
| **Champs-texte** (`coup_de_pouce`, `correction`, `solution`, `aller_plus_loin`) | — | acceptent une **chaîne** OU une **liste de blocs** `{titre, texte, figure?}` ; `aller_plus_loin` : liste de `{niveau, titre, texte}` |

---

## 15. Déploiement sur le Raspberry Pi

Détail complet : `DEPLOY_RASPBERRY.md`. L'essentiel :

- **Deux dépôts Git** : `CoursOndes` (ce projet : code + `data/`, **sans** fichiers générés) et `Quartz5` (le site + tes notes).
- Les PDF, SVG, GIF, JSON, `build/public/`, manifest… ne sont **pas** versionnés : ils sont **régénérés sur le Pi**.
- `tools/Raspberry/update_code.sh` (après un `git pull` sur le Pi) : `git reset --hard origin/main` → `pdf_status` → `build.py --stale` (un échec LaTeX n'arrête plus le script) → `publish_profile.sh <profil de web/.current_profile>` → redémarre gunicorn → recharge nginx.
- Services : `gunicorn-cours.socket/.service` (API QCM), nginx sur le port interne 8091, tunnel (`start_tunnel.sh` / `stop_tunnel.sh`).
- Basculer de « avant séance » à « corrigé » en cours de journée : `./web/publish_profile.sh corrige_complet` (ou modifie `publication:` puis `auto`).

Workflow quotidien : modifier sur le Mac → `tools/Mac/push.sh "message"` → sur le Pi `tools/Raspberry/update_code.sh`.

---

## 16. Dépannage

| Symptôme | Cause probable | Remède |
|---|---|---|
| `zsh: parse error near '\n'` en tapant `./web/publish_profile.sh <profil>` | `<profil>` est un emplacement à remplacer | `./web/publish_profile.sh auto` |
| `permission denied` sur un `.sh`/`.py` | bit exécutable perdu (zip) | `chmod +x web/publish_profile.sh tools/*.py` ou `bash web/publish_profile.sh` |
| `unrecognized arguments: # …` | commentaire collé sur la ligne de commande (zsh) | copier la commande **sans** le commentaire |
| `ImportError: cannot import name 'resolve_child'` | `common_data.py` ancien (un zip n'a pas écrasé) | `unzip -o …` depuis la racine ; vérifier `grep -c "def resolve_child" common_data.py` = 1 |
| `YAML invalide : <fichier>, ligne N` | texte avec `:` non quoté, ou `\` dans un `"…"` | §14 ; `python3 tools/check_data.py` liste tous les fichiers fautifs |
| `Cannot find package 'yargs'` à l'étape 7 | `npm install` jamais fait dans Quartz | `cd ../Quartz5 && npm install` |
| `Quartz5 introuvable` (étapes 4/4bis sautées) | dossier voisin nommé autrement | renommer en `Quartz5` ou `QUARTZ_CONTENT=…/content` |
| Figure absente / image cassée | SVG non compilé | `tail -30 figures/.render_tmp/<nom>_standalone.log` ; `render_web.py --force` |
| Figures en noir, sans couleur | ancien gabarit `standalone` | `python3 figures/render_web.py --force` (le gabarit charge maintenant `monstyletikz.tex`) |
| Figures invisibles en thème sombre | traits foncés sur fond transparent | elles sont posées sur une carte blanche ; vérifier que les pages ont été régénérées |
| `'td' is undefined` en compilant un cours | modèle qui référençait `td` hors TD | corrigé dans `preamble.tex.j2` (`td is defined`) |
| Babel / `ifsym.sty` introuvable | TeX Live incomplet | installer les paquets TeX manquants |
| Tous les PDF « périmés » d'un coup | un fichier de `templates/` ou `couleurs:` a changé | normal : `build.py --stale` |
| Un corrigé est en ligne alors qu'il ne devrait pas | profil du document, ou cible `*_enonce` avec `show_solution: true`, ou `publier: true` | `./web/publish_profile.sh avant_seance`, vérifier `publication:` ; `check_data` avertit |
| Les corrections s'ouvrent seules dans Quartz | version ancienne de `export_markdown.py` (callout `+`) | utiliser la version actuelle (`COLLAPSE` → `-`) |
| Slug d'URL contenant `-color-blue-` | titre bilingue d'une version ancienne | version actuelle : slug = français seul |
| `pdf non publié / absent` dans `check_quartz_links` | export Markdown fait avec un profil plus large que l'hébergement | republier avec `publish_profile.sh` (même profil partout) |
| Notebooks : `'list' object has no attribute 'strip'` | ancienne version (champs-liste) | version actuelle (`blocks_to_markdown`) |

---

## 17. Faire évoluer le projet

### 17.1 Principes de conception (à ne pas casser)

1. **Une seule source de vérité** : `data/` + `build/config.yaml`. Tout le reste est **généré** et jetable.
2. **Le filtrage retire vraiment** les champs (profil) ; il ne les masque jamais en CSS.
3. **L'état se lit sur le disque**, pas dans un fichier qui peut mentir (manifest reconstruit).
4. **On ne supprime que ce qu'on a généré** (registre `.coursondes-generated.json`) ; tes notes manuscrites sont intouchables.
5. **Tout est idempotent** : relancer n'ajoute rien, ne duplique rien.
6. **Pas de secret par obscurité** : tout ce qui est dans `build/public/` ou dans Quartz est public ; la confidentialité passe par les profils et `publier:`.
7. **Un point d'entrée par concept** : les profils se résolvent via `common_data.resolve_profile`, les titres via `title_parts`, la couleur via `en_color_css`/`en_color_latex_definition`, la lecture YAML via `read_yaml` (erreurs avec fichier + ligne).

### 17.2 `common_data.py` : le cœur

| Groupe | Fonctions |
|---|---|
| Config | `load_build_config`, `en_color_css`, `en_color_latex_definition`, `publication_config`, `resolve_profile`, `load_visibility_profiles` |
| Lecture | `read_yaml`, `list_matieres`, `load_matiere_meta`, `list_docs_td_like`, `list_docs_cours`, `load_td`, `load_cours`, `load_all_qcm`, `load_sujets_graph`, `resolve_child` (tolérant NFC/NFD), `is_ignored_name` |
| Visibilité | `apply_visibility`, `apply_visibility_to_exercice`, `apply_visibility_to_cours` |
| Nettoyage web | `clean_text_for_web` (+ `_convert_color_groups`, `_latex_text_to_md`, `_replace_theme_colors`), `clean_exercice_for_web`, `clean_cours_for_web`, `blocks_to_markdown` |
| Titres | `title_parts` / `split_en_text` (FR, EN), `en_span` |
| Médias | `enrich_media_paths`, `enrich_cours_media`, `figure_web_path`, `animation_web_path` |
| Couleurs | `normalize_en_color` (appelé dans `load_td`/`load_cours`) |

### 17.3 « Je veux… » → où toucher

| Je veux… | Fichiers à modifier |
|---|---|
| ajouter un **champ** à un exercice (ex. `piege:`) | `data/SCHEMA.md` (documenter) · `templates/exercice.tex.j2` (PDF) · `web/export_markdown.py` → `render_question_md` (Quartz) · `common_data.apply_visibility*` si masquable · notebooks/JSON si besoin |
| un **nouveau profil** | `web/visibility_profiles.yaml` seulement |
| un **nouveau type de PDF** (ex. `_resume`) | `build/pdf_status.py` (`KIND_RE`, `KIND_ORDER`, `kind_of`) · `web/export_markdown.py` (`KIND_LABEL`) · `web/publish_hosting.py` (`KIND_LABEL`, `KIND_ORDER`) · ajouter le type aux `pdf_publies` voulus |
| changer l'**aspect des PDF** | `templates/styles/theme_academique.tex` (couleurs `colorOne…Six`, boîtes) · `templates/*.tex.j2` · `monstyletikz.tex` (figures) |
| changer l'**aspect des callouts / liens / figures** sur le site | `web/export_markdown.py` (`callout`, `COLLAPSE`, `a_blank`, `clickable_image`) |
| changer la **structure des URL** | `web/export_markdown.py` (`td_base`, `ex_slug_of`, `chapitre_slug_of`, `export_matiere`) — mettre à jour `exercice_paths` dans `main()` |
| un **nouveau type de document** (ex. `fiche`) | `common_data` (`_type_dir`, `list_docs_*`), `export_markdown.TYPE_LABELS`, un template, `config.yaml` (`type_doc`) |
| un **nouvel export** (ex. epub) | s'inspirer de `web/export_json.py` : parcourir `list_matieres()`/`list_docs_*()`, `resolve_profile(…, forced=…)` par document et par exercice, `title_parts` pour les titres |
| un autre **mode d'hébergement** | `web/publish_hosting.py` + `deploy/nginx-cours.conf` |
| une **nouvelle règle de contrôle** | `tools/check_data.py` (ajouter un `err(...)` ou `warn(...)`) |

### 17.3 bis. Vérifier qu'une modification n'a rien cassé

```bash
python3 -m py_compile common_data.py build/*.py web/*.py tools/*.py notebooks/*.py figures/*.py
python3 tools/check_data.py
python3 build/build.py --no-pdf --stale                          # les .tex se génèrent-ils ?
python3 web/export_markdown.py --profile auto --out /tmp/q/content
python3 tools/check_quartz_links.py --quartz-content /tmp/q/content
python3 web/export_json.py --profile auto
```

Aucun de ces tests ne touche à Quartz ni au Pi.

### 17.4 Pour une IA qui reprend le projet

1. Lire ce README, puis `data/SCHEMA.md`, puis `common_data.py`, puis `build/config.yaml`.
2. Les scripts se lancent depuis la **racine** ; chacun fait `sys.path.insert(0, ROOT)` puis `import common_data` ; `web/` n'a pas de `__init__.py` (paquet-espace de noms : `from web.xxx import …` fonctionne depuis la racine).
3. Ne jamais éditer `build/output/`, `build/public/`, `web/public/`, ni les pages générées dans Quartz : tout est écrasé.
4. Avant de proposer un correctif : **reproduire** avec les commandes du §17.3 bis, sur un dossier de sortie jetable (`--out /tmp/…`).
5. **Ne pas écraser `build/config.yaml`** de l'utilisateur (il contient ses cibles et ses choix de publication) : fournir des blocs à insérer ou un script idempotent comme `tools/add_config_blocks.py`.
6. Respecter les invariants du §17.1, en particulier : un profil se résout **par document** (et par exercice) via `resolve_profile`, jamais en dur.

### 17.5 Idées non faites / limites connues

- Le graphe natif de Quartz ne montre pas les poids (§9.5) : `graph.json` est prêt pour une vue D3.
- Les figures TikZ ne sont pas dans l'empreinte « périmé » des PDF (§10).
- Les remarques pour l'enseignant (`show_remarques_pedagogiques_*`, objectifs enseignants) n'existent que dans les PDF `*_fiche`, pas dans les pages Quartz.
- `publication:` ne se complète pas automatiquement quand on crée un document (il prend le défaut) : `add_config_blocks.py --complete` liste les manquants.
- Les points d'un `_meta.yaml` comme `point_cours`, `prerequis`, `bilan` ne sont rendus que dans les PDF (pas encore dans les pages Quartz).

### 17.6 Ménage

Fichiers parasites que `pdflatex` laisse parfois à la racine (`td1_ONIP1_fiche.aux/.log/.out`, `texput.log`) : supprimables. `TP_IPSA_Generale_fiche_pro.pdf` est une copie chiffrée faite à la main avec `qpdf` : à garder si tu en as besoin. `python3 manage.py status` montre le poids des fichiers générés ; `manage.py clean …` les supprime sans jamais toucher à `data/`.
