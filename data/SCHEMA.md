# Schéma des données — `data/`

Voir aussi le `README.md` à la racine pour le guide pratique "comment créer
un nouveau document en local". Ce fichier-ci documente le **format exact**
des fichiers YAML.

## Structure générale

```
data/
├── matieres/
│   └── <matiere_slug>/
│       ├── _matiere.yaml
│       ├── td/<doc_slug>/{_meta.yaml, ex1_....yaml, ...}
│       ├── tp/<doc_slug>/{...}          (même format que td/)
│       ├── cours/<doc_slug>.yaml         (un seul fichier par document)
│       └── qcm/*.yaml
└── graph/
    └── sujets.yaml                        (transverse à toutes les matières)
```

Une **matière** = un cours/sujet d'enseignement ou de recherche (ex :
`physique-ondes-ipsa`, `agregation-physique`, `recherche-integrabilite-quantique`).
Elle peut contenir des documents de trois types : `td`, `tp` (même format,
question/correction) et `cours` (prose de lecture, pas de questions).

## `_matiere.yaml`

```yaml
id: physique-ondes-ipsa
nom: "Physique des ondes — IPSA"
niveau: [cpge, licence]
description: >
  Une phrase ou deux, réutilisée en tête de la page Quartz de la matière.
quartz_namespace: physique/ipsa-ondes   # chemin dans Quartz5/content/
sujets: [ondes-mecaniques, ondes-acoustiques, reflexion-transmission]
  # ids de data/graph/sujets.yaml traités par cette matière (informatif)
```

## Documents `td` / `tp` (dossier de fichiers)

### `_meta.yaml` (un par document)

```yaml
id: td1
titre: "Propagation des ondes mécaniques sur une corde"
chapitre_cours: "Chap. 1 — Ondes mécaniques 1D"
seance: 1
niveau_public: [cpge, licence]
exercices_ordre: [ex1_corde_nylon, ex2_celerite, ...]
```

### `exN_xxx.yaml` (un par exercice)

```yaml
id: td1_ex1
intitule: "Corde de nylon"
td: td1
facultatif: false
seance: 1
cours_rattache: [chap1.equation_ondes, chap1.celerite_corde]
  # tags libres, utilisés pour le "voir aussi" automatique ENTRE exercices
  # (même matière ou non) qui partagent au moins un tag.
enonce_intro: "..."               # LaTeX/texte, commun à toutes les questions
figure: {ref: ..., legende: "..."}
animation: {ref: ..., params: {...}, formats: [gif, mp4, frames_pdf]}

questions:
  - id: q1
    enonce: "..."
    coup_de_pouce: "..."
    aller_plus_loin: {lycee: "...", licence: "...", master: "...", doctorat: "..."}
    correction: "..."              # résultat final, concis
    solution: "..."                # rédaction complète, pas à pas
    figure: {ref: ..., legende: "..."}    # optionnel, propre à la question
    animation: {ref: ..., ...}             # optionnel, propre à la question
    overlay_tikz: |                # optionnel, PDF uniquement -- voir plus bas
      \draw[->] (monrepere) -- (autrerepere);
    encadre:                        # optionnel, voir "Encadré générique" plus bas
      type: "Formalisme"
      titre: "Lieb-Liniger (LL)"
      couleur: "woodChene"
      contenu: "..."

  - id: q2a
    parent: "2"                     # regroupe q2a..q2f sous l'énoncé "2." commun
    enonce: "..."
```

### `\tikzmark`, `\ptFleche`, flèches et `overlay_tikz` -- où les placer

`\begin{eqnarray}`, `\tikzmark{...}`, `\ptFleche{nom}{contenu}`, ou toute
macro LaTeX personnalisée passent telles quelles dans le PDF. Attention :
KaTeX (Quartz) ne supporte pas `eqnarray` — utiliser `$$\begin{aligned}...\end{aligned}$$`
si le même contenu doit aussi s'afficher correctement sur le site.

**`overlay_tikz` existe à deux niveaux : `questions[].overlay_tikz` (une
question précise) et au niveau de l'exercice tout entier.** Toujours
préférer le niveau QUESTION : un `overlay_tikz` placé au niveau exercice
n'est rendu qu'une fois, tout à la fin (après toutes les questions) — si
l'exercice est un peu long, les `\tikzmark`/`\ptFleche` référencés peuvent
se retrouver sur une PAGE DIFFÉRENTE de celle où ce bloc est dessiné, ce
qui casse complètement le calcul de position (bug réel rencontré et
corrigé pendant le développement — l'exercice `td1_ex1_corde_nylon`
utilisait initialement ce niveau et la flèche pointait dans le vide sur
la page suivante). Toujours mettre `overlay_tikz` juste après le champ
`solution`/`correction` DE LA QUESTION dont il dessine les flèches.

Deux façons de marquer un point :
- `\tikzmark{nom}` : repère invisible, à placer AUTOUR d'un texte déjà
  présent (`...est de \tikzmark{a}950 kg/m$^3$\tikzmark{aend}...`).
- `\ptFleche{nom}{contenu}` : ENVELOPPE le contenu lui-même, pratique
  DANS une équation (`\ptFleche{LL}{$\hat H$}`) -- pas besoin de note de
  fin, le "contenu" s'affiche normalement en plus d'être repérable.

Style de flèche "à la Dossier scientifique" (courbée, étiquette
colorée) :

```latex
\draw[opacity=1]
  (LL) edge[line width=0.4ex, color=colorOne,
    arrows={Computer Modern Rightarrow[sharp,length=0.2cm]-},
    out=180, in=0] node[pos=1, left]{\color{colorOne}\bfseries Hamiltonien}
  ($(LL) + (-2.5cm,0.0cm)$);
```

Paramètres à ajuster à la main : `line width` (épaisseur), `color`
(`colorOne`..`colorSix`, `Prune`, `woodChene`, `greenSapin`... voir
`templates/styles/theme_academique.tex`), `out`/`in` (angles de départ/
arrivée de la courbe, en degrés), la position finale `($(nom) + (Xcm,Ycm)$)`
(décalage libre depuis le repère), et le texte du `node[...]{...}`. Pas de
version data-driven de ceci : ces flèches sont trop variées pour un
schéma YAML générique — écrire le TikZ directement dans `overlay_tikz`,
comme montré dans `data/matieres/recherche-integrabilite-quantique/cours/intro_bethe.yaml`
(section "Modèle de Lieb-Liniger").

### Encadré générique (`encadre`) -- style `\EncadreDeux`

Reprend le style du Dossier scientifique (bande colorée + titre pivoté) :

```yaml
encadre:
  type: "Formalisme"          # gros label blanc, au centre de la bande (ex: "Correction", "Rappel"...)
  titre: "Lieb-Liniger (LL)"   # petit label coloré, en bas de la bande
  couleur: "woodChene"          # n'importe quelle couleur définie dans theme_academique.tex
  contenu: "..."                 # texte affiché dans l'encadré
```

Disponible sous `questions[].encadre` (td/tp) et `sections[].encadre`
(cours). Rendu en PDF via `\EncadreDeux` (macro disponible telle quelle
dans `templates/styles/theme_academique.tex` pour tout usage libre en
LaTeX brut) et en callout Obsidian sur le site Quartz. ⚠️ `\EncadreDeux`
pivote son texte SUR TOUTE LA HAUTEUR de la boîte : un `contenu` très
court peut rendre le texte pivoté cramponné/peu lisible -- fonctionne
mieux avec quelques lignes de contenu.

## Documents `cours` (fichier unique, prose de lecture)

```yaml
id: physique-ondes-ipsa_cours_chap1
matiere: physique-ondes-ipsa
type_doc: cours
titre: "Chapitre 1 — Ondes mécaniques : introduction"
sous_titre: "Cours"              # ou "Leçon", "Notes"...
seance: 1
niveau: [cpge, licence]
sujets: [ondes-mecaniques]        # ids de data/graph/sujets.yaml traités ici

sections:
  - titre: "Qu'est-ce qu'une onde ?"
    contenu: "..."                # LaTeX/texte libre
    figure: {ref: ..., legende: "..."}
    animation: {ref: ..., ...}
    remarque: "..."                # callout toujours visible (jamais masqué par un profil)
    aller_plus_loin: {master: "..."}
    overlay_tikz: "..."            # idem td/tp : au niveau SECTION, jamais document entier
    encadre: {type: "...", titre: "...", couleur: "...", contenu: "..."}
```

Pas de `coup_de_pouce`/`correction`/`solution` pour un `cours` (ce n'est pas
un TD) — seul `aller_plus_loin` est filtré par niveau selon le profil.

## QCM (`qcm/*.yaml`)

```yaml
- id: td1_qcm_debut1
  td: td1                          # id du document td/tp concerné (pas le matiere id)
  moment: debut                    # debut | milieu | fin
  lie_a: td1_ex1                   # optionnel, "<meta.id>_ex<numero>" -- lie le QCM
                                     # à un exercice précis (lien cliquable généré)
  question: "..."
  animation: {ref: ..., formats: [gif]}
  choix:
    - {id: a, texte: "...", correct: true}
    - {id: b, texte: "...", correct: false}
    - {id: c, texte: "Je ne sais pas encore", correct: false, neutre: true}
  feedback: {correct: "...", incorrect: "...", neutre: "..."}
```

## `data/graph/sujets.yaml` — graphe des sujets

Voir le fichier lui-même (abondamment commenté) et `README.md` section
"Graphe des sujets" pour l'usage et les limites (notamment : le graphe
natif de Quartz ne visualise PAS les poids, seulement présence/absence de
lien — voir la discussion complète dans le README).

## Profils de visibilité (`web/visibility_profiles.yaml`)

Contrôlent ce qui est montré/caché à la génération (PDF, JSON, Markdown
Quartz, notebooks) — jamais dans les données elles-mêmes :

```yaml
profiles:
  avant_seance:
    show_figure: true
    show_animation_note: true
    show_coup_de_pouce: true
    show_correction: false
    show_solution: false
    aller_plus_loin_niveaux: []
    pdf_suffix: enonce            # -> /pdfs/<id>_enonce.pdf
```
