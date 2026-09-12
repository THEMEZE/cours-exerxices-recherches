# CoursOndes — moteur de cours multi-matières

Ce projet génère des PDF (LaTeX), des animations (Python/matplotlib), des
notebooks Jupyter, un site interactif (Quartz 5) et des QCM en direct, à
partir d'une seule source de vérité par document : des fichiers YAML dans
`data/`.

À l'origine construit pour un seul cours (ondes mécaniques, IPSA), il gère
maintenant **plusieurs matières** (physique, mathématiques, agrégation,
recherche personnelle...) et **deux types de documents** (`td`/`tp`
question-réponse, et `cours` en prose de lecture) — voir `data/SCHEMA.md`
pour le format exact des fichiers.

Documentation associée :
- `data/SCHEMA.md` — format exact des fichiers YAML
- `DEPLOY_RASPBERRY.md` — déploiement sur le Raspberry Pi, architecture Git
- `web/README.md` — l'appli QCM (QR code, stats, backend Flask)

---

## 1. Comment créer un nouveau document, en local

### 1.0 Environnement

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 1.a Ajouter un TD (ou TP) à une matière existante

```bash
mkdir -p data/matieres/physique-ondes-ipsa/td/td4_mon_nouveau_td
```

Créer `_meta.yaml` :

```yaml
id: td4
titre: "Mon nouveau TD"
chapitre_cours: "Chap. 4 — ..."
seance: 5
niveau_public: [cpge, licence]
exercices_ordre: [ex1_premier_exercice]
```

Créer `ex1_premier_exercice.yaml` (voir `data/SCHEMA.md` pour tous les
champs disponibles — `coup_de_pouce`, `correction`, `solution`,
`aller_plus_loin`, `figure`, `animation`...).

Ajouter une cible dans `build/config.yaml` (copier/coller une cible
existante et changer `doc: td4_mon_nouveau_td`), puis :

```bash
python3 build/build.py td4_enonce      # génère le PDF
./web/publish_profile.sh avant_seance   # régénère aussi le site Quartz
```

### 1.b Ajouter un cours/leçon (prose, pas d'exercices)

```bash
# un seul fichier, pas de dossier
touch data/matieres/physique-ondes-ipsa/cours/chap2_mon_chapitre.yaml
```

Voir `data/SCHEMA.md` section "Documents cours" pour le format (`sections:`
avec `titre`/`contenu`/`figure`/`animation`/`remarque`/`aller_plus_loin`).
Ajouter une cible `type_doc: cours` dans `build/config.yaml`, puis même
commandes que ci-dessus.

### 1.c Créer une TOUTE NOUVELLE matière

```bash
mkdir -p data/matieres/ma-nouvelle-matiere/{td,cours,qcm}
```

Créer `_matiere.yaml` :

```yaml
id: ma-nouvelle-matiere
nom: "Nom affiché"
niveau: [licence]
description: "Une phrase de présentation."
quartz_namespace: physique/ma-nouvelle-matiere   # où ça atterrit dans Quartz5/content/
sujets: []                                        # ids de data/graph/sujets.yaml (optionnel)
```

Puis ajouter des documents `td/` ou `cours/` comme ci-dessus. **Rien
d'autre à modifier** : `common_data.py`, `build.py`, `export_json.py`,
`export_markdown.py` et `notebooks/build_notebooks.py` découvrent
automatiquement toute nouvelle matière (fonction `list_matieres()`).

### 1.d Regénérer tout d'un coup

```bash
python3 build/build.py                       # tous les PDF de build/config.yaml
./web/publish_profile.sh avant_seance          # figures + animations + JSON + Quartz + notebooks + QCM
```

---

## 2. Où atterrit chaque document (PDF ↔ Quartz)

La structure Quartz **mirroite** la structure des PDF, matière par matière,
type de document par type de document :

```
Quartz5/content/<quartz_namespace>/
    index.md                          <- sommaire de la matière (TD/Cours/TP)
    TD/<chapitre_slug>/<doc_slug>/
        index.md                       <- sommaire du document (+ lien PDF)
        ex1-....md, ex2-....md, ...     <- un fichier par exercice
    Cours/<doc_slug>.md                <- un seul fichier (sections en ## )
```

Un même `data/matieres/<m>/td/td1_corde/` donne à la fois
`build/output/td1_enonce.pdf` (ou `_corrige.pdf`) ET
`Quartz5/content/physique/ipsa-ondes/TD/.../` — générés depuis les MÊMES
données, avec le PDF en plus (lien cliquable en tête de chaque page Quartz),
et le Quartz en plus interactif (callouts repliables, figures/animations
cliquables, liens croisés — voir section 4).

---

## 3. Profils de visibilité — ne jamais exposer un corrigé trop tôt

Un seul mécanisme (`web/visibility_profiles.yaml`) contrôle PDF, JSON,
Markdown Quartz et notebooks à la fois :

```bash
./web/publish_profile.sh avant_seance      # avant le cours : énoncé nu
./web/publish_profile.sh corrige_complet   # après : tout, y compris solutions détaillées
```

Le filtrage retire VRAIMENT les champs des fichiers générés (jamais un
simple masquage CSS) — voir `common_data.apply_visibility*`.

---

## 4. Le graphe des sujets (`data/graph/sujets.yaml`)

### Le principe

Un **sujet** = un concept qui a sa propre page Quartz (`quartz_path`),
qu'elle soit générée (ex: `physique/ipsa-ondes`) ou écrite à la main (ex:
`physique/theorie-m`). Un **lien** entre deux sujets a :

- un **poids** entre -1 et 1 (force de la relation ; négatif = "à
  distinguer", positif = "s'éclairent mutuellement")
- un **type** : `parent` (hiérarchie, `de` est le parent de `a`) ou
  `associe` (lien libre, non hiérarchique)

```yaml
sujets:
  - id: theorie-m
    nom: "Théorie M"
    quartz_path: physique/theorie-m

liens:
  - de: theorie-m
    a: supergravite
    poids: 0.9
    type: parent
    note: "La supergravité D=11 est la limite basse énergie de la théorie M."
```

### Ce que ça génère

```bash
python3 web/build_subject_links.py --quartz-content ~/Quartz5/content
```

Injecte automatiquement, dans chaque page concernée, une section :

```markdown
## 🔗 Sujets liés

**Sujet parent :** [[physique/theorie-du-tout|Théorie du tout]]

**Sous-sujets :**
- [[physique/supergravite|Supergravité]]

**Voir aussi :**
- ●●●●○ [[physique/agregation-physique|Agrégation de physique]] — *Les ondes sont un classique de leçon.*
```

L'injection est **idempotente** (relancer le script ne duplique jamais
rien) et se fait dans un bloc délimité
(`<!-- SUJETS-LIES:BEGIN -->...<!-- SUJETS-LIES:END -->`) : ton contenu
écrit à la main autour n'est jamais touché. Testé : deux exécutions
consécutives, la deuxième ne modifie aucun fichier.

Si plusieurs sujets pointent vers la même page (ex: un TD qui couvre 3
sujets du programme), leurs liens sont **fusionnés** en une seule section
(pas de doublon, pas d'écrasement mutuel — un vrai bug de ce genre a été
trouvé et corrigé pendant les tests, voir le code de
`build_subject_links.py`).

### Limite honnête : le graphe visuel natif de Quartz ne voit pas les poids

Quartz a un graphe de liens intégré (panneau "Graph View"), construit
automatiquement à partir des wikilinks réels dans le contenu — donc les
liens générés par `build_subject_links.py` s'y affichent **tous**, mais
**sans distinction de poids ni de type** (une arête pèse pareil qu'une
autre, un lien "parent" a la même apparence qu'un lien "associé" à 0.1).
Le champ `poids` sert aujourd'hui à :
1. Trier les "Voir aussi" par pertinence décroissante.
2. Filtrer les liens faibles avec `--seuil` (ex: `--seuil 0.3` pour ne
   garder que les liens vraiment significatifs).
3. Être prêt pour une visualisation personnalisée plus tard (D3.js avec
   épaisseur d'arête proportionnelle au poids) si tu veux aller plus loin
   — non construite dans cette session, mais les données sont là.

---

## 5. Tester en local avant de pousser sur le Raspberry

```bash
python3 build/build.py                              # PDF
python3 figures/render_web.py                        # SVG des figures
python3 animations/generate_all.py --no-latex          # GIF/MP4
python3 web/export_markdown.py --profile avant_seance --out ../Quartz5/content
python3 web/build_subject_links.py --quartz-content ../Quartz5/content
cd ../Quartz5 && npx quartz build --serve               # prévisualisation locale, http://localhost:8080
```

## 6. Ce qui a été réellement testé dans cette session

- Migration physique de `data/td*` vers `data/matieres/physique-ondes-ipsa/td/*`
  sans casser aucune des 12 cibles PDF de `build/config.yaml` (recompilées
  avec succès, callouts + figures + eqnarray + flèches tikzmark inclus).
- Nouveau type de document `cours` : template LaTeX dédié (`cours.tex.j2`,
  `section.tex.j2`) compilé avec succès (nouvelle boîte "Remarque").
- Deux nouvelles matières d'exemple (agrégation physique, agrégation
  mathématiques) et une matière de recherche personnelle
  (intégrabilité quantique), chacune avec un document gabarit, exportées
  en PDF ET en Quartz sans code supplémentaire.
- Export Markdown généralisé : 37 fichiers Markdown générés sur 4 matières
  mélangeant `td` et `cours`, buildés par le vrai Quartz v5 (209 fichiers
  émis, 0 erreur).
- Graphe de sujets : bug de fusion de pages trouvé et corrigé (3 sujets
  pointant vers la même page s'écrasaient mutuellement au lieu de
  fusionner), idempotence vérifiée sur deux exécutions consécutives, lien
  "Sujets liés" confirmé visible dans le HTML final avec les bons hrefs.
# cours-exerxices-recherches
