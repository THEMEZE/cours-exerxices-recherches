# Guide — types de documents, rubriques, fichiers rattachés, QCM

Tout se règle dans **`build/config.yaml`** (chaque bloc est commenté) et **`web/visibility_profiles.yaml`**.
Publier : `./web/publish_profile.sh auto` (contrôle automatique des réglages en étape 0).

## 1. Une matière peut contenir autre chose que TD / TP / cours
Un **type de document** = un sous-dossier de `data/matieres/<matiere>/` + une section de la page Quartz de la matière.
Déclarés dans `config.yaml > types_documents` : `td`, `tp`, **`projet`** (nouveau, « Mini-Projet »), `cours`.

- Le mini-projet Tsiolkovski a été déplacé : `td/projet1_Tsiolkovski/` → **`projet/projet1_Tsiolkovski/`**
  (cibles PDF et `publication:` mis à jour). Sur Quartz : `…/Mini-Projet/…`, section `## Mini-Projet` dans `index.md`.
- **Ajouter un type** (labo, devoir…) : 1 ligne dans `types_documents` (`labo: {label: "Labo", forme: exercices}`) + le dossier
  `data/matieres/<m>/labo/<doc>/` (mêmes `_meta.yaml` + `ex*.yaml` qu'un TD). `forme: sections` = un fichier YAML comme un cours.
  Testé : un `labo/` de test apparaît dans l'index, les pages et le profil de publication.
- `tools/check_evolutions.py` signale les dossiers non déclarés : `physique-ondes-ipsa/documentation/` et
  `physique-ondes-ipsa/outils_verification/` existent mais **ne sont pas publiés** (aucun type ne les déclare).

## 2. Fichiers rattachés à un dossier ou à un exercice (`config.yaml > fichiers`)
```yaml
fichiers:
  mecanique-de-point-ipsa:
    projet:
      projet1_Tsiolkovski:
        document:                                   # page du projet + liste de la matière
          - {label: "Fichier Excel – Falcon 9", fichier: "fichiers/Phv111_MP_Falcon9_Launch.xlsx"}
        exercices:
          s2_falcon9:                               # page d'UN exercice
            - {label: "Fichier Excel – Falcon 9", fichier: "fichiers/Phv111_MP_Falcon9_Launch.xlsx"}
            - {label: "Fiche prof", cible: projet1_PhV111_fiche, public: prof}
```
- `fichier:` = fichier statique rangé dans `data/matieres/<matiere>/` (dossier conseillé `fichiers/`) → hébergé sur `/pdfs/<nom>`.
  **À faire : copie ton `Phv111_MP_Falcon9_Launch.xlsx` dans `data/matieres/mecanique-de-point-ipsa/fichiers/`** (il n'était pas dans le zip).
- `cible:` = un PDF **construit par l'appli** (nom d'une entrée de `targets:`), publié seulement s'il existe et si le profil le permet.
- Plusieurs entrées par dossier / par exercice possibles. `public: prof` = invisible dans un profil élève.
- **Pour quels profils** (facultatif ; si plusieurs clés, toutes doivent être vraies) :
  - `profils: [corrige_complet, all_eleve]` : visible seulement avec ces profils (un état comme `termine` est accepté) ;
  - `sauf: [avant_seance]` : visible partout sauf avec ceux-là ;
  - `si: show_correction` : visible seulement si ce réglage du profil est vrai (suit tout seul les profils que tu ajoutes).
  Les `.md` **et** l'hébergement suivent : hors des profils choisis, le fichier n'a ni lien ni copie sur `/pdfs/`
  (revenir à un profil plus restrictif retire la copie). Exemple dans `config.yaml` : `…_avecCorrection.xlsx` visible
  uniquement avec les profils qui montrent la correction ; testé avec 6 profils.

## 3. Rubriques (prérequis, objectifs, point de cours, bilan…) dans les .md
Rendues en encadrés Quartz à 3 niveaux : `_meta.yaml` (page du document), fichier d'exercice, question.
Défauts : `organisation`, `accroche_point_cours_essentiel`, `prerequis`, `objectifs_pedagogiques_etudiants`,
`objectifs_pedagogiques_enseignants`, `point_cours`, `outils_mathematiques`, `materiel`, `securite`, `manipulation`, `attention`,
`remarques_pedagogiques_ecueils_classiques`, `remarques_pedagogiques_conseils_animation`, `liens_autres_disciplines`, `lien_aviation`, `bilan`.
Le site affiche aussi maintenant le `coup_de_pouce` et l'`aller_plus_loin` écrits au niveau exercice/document (avant : ignorés).

**Ajouter une rubrique = 1 bloc dans `config.yaml > rubriques`** + la clé dans un YAML. Aucun code :
```yaml
rubriques:
  erreurs_frequentes: {titre: "Erreurs fréquentes", icone: "🚧", callout: warning, public: eleve, position: fin, ordre: 82, repli: "-"}
```
Contenu accepté : texte, liste de textes, liste de `{titre, texte}` ou `{discipline, texte}`. `public: eleve|prof`, `position: debut|fin`.
Les PDF restent pilotés par les `show_*` des cibles (templates LaTeX inchangés).

## 4. Profils et états de chapitre
| profil | contenu | PDF | usage |
|---|---|---|---|
| `all_eleve` | coup de pouce + correction + solution + aller plus loin + toutes les rubriques **élève** | énoncé, aides, corrigé, autres | **site public** |
| `all_fast` | **juste** énoncé + coup de pouce + correction + solution — aucune rubrique (ni accroche 🎣, ni prérequis, ni cours), pas d'« aller plus loin » | idem | version « légère » |
| `all_prof` | tout : + rubriques **enseignant** (objectifs enseignant, écueils, conseils, bilan) | + fiches enseignant, fichiers `public: prof` | site **privé / local** |
| `all` | ancien nom = `all_prof` | | |

Chaque profil a `public: [eleve]` ou `[eleve, prof]` et `rubriques:` (`cle`, `@public`, `@tous`, `-cle`).
`all_fast` = `rubriques: []` ; pour lui rendre une chose : `rubriques: [prerequis]` ou `aller_plus_loin_niveaux: [licence]`.
⚠️ Ton `publication:` utilisait `all` partout (= site public) : je l'ai remplacé par **`all_eleve`**, sinon les notes enseignant seraient devenues publiques.
Un avertissement s'affiche si un profil « prof » sert le site.

**Interrupteurs `show_*` (comme dans `targets:`)** : chaque profil de `web/visibility_profiles.yaml` liste maintenant un `show_xxx: true|false`
par élément : `show_metadonnees`, `show_figure`, `show_animation_note`, `show_coup_de_pouce`, `show_correction`, `show_solution`, et **un `show_<rubrique>`
par rubrique** (`show_prerequis`, `show_point_cours`, `show_bilan`…), plus `aller_plus_loin_niveaux`. `rubriques:` ne sert plus que de politique pour les
rubriques sans `show_<nom>` (par exemple une rubrique que tu viens d'ajouter). Résultat identique à avant (vérifié profil par profil).
- **`show_metadonnees`** (nouveau sur le site) : ligne de repères sous le titre de l'exercice — `⭐ Indispensable · Difficulté ●●●○○ · ⏱ 2 h 30 · Type : …`
  (mêmes données que les badges des PDF). Vrai partout sauf `all_fast`.
- **Les PDF peuvent hériter d'un profil** : une cible `visibilite: all_fast` (ou `visibilite: termine`) reprend tous les `show_*` du profil ;
  ce que la cible écrit elle-même l'emporte. Une seule définition pour le site et le PDF. Un changement de profil rend le PDF « périmé » (empreinte).
  Les gabarits LaTeX sont fixes : les rubriques que tu inventes n'existent qu'en site, pas en PDF ; `show_plan_seance` ne concerne que les PDF.
- ⚠️ Un profil `public: [eleve]` qui passe un `show_<rubrique enseignant>` à `true` est signalé par `check_evolutions.py`.

**États d'un chapitre** (`config.yaml > publication > etats`) : un nom parlant pour un profil, à écrire à la place du profil :
```yaml
publication:
  etats:
    a_venir:  avant_seance                  # pas encore abordé : énoncés seulement
    en_cours: pendant_seance_avec_indices   # en cours : énoncés + aides
    termine:  corrige_complet               # terminé : corrections et solutions
    revision: all_fast                      # <- un état AJOUTÉ par toi
  matieres:
    mecanique-de-point-ipsa:
      td:
        td4_loi_de_newton: termine
        td5_nrj: {etat: en_cours, exercices: {ex2_travail: termine}}     # un exercice déjà corrigé
```
Changer ce que veut dire « termine » se fait à un seul endroit. Un état marche aussi en ligne de commande : `./web/publish_profile.sh termine`.
Tes entrées `pendant_seance_avec_indices` sont devenues `en_cours` (même effet).

## 5. QCM : où tu en es, et ce qui est nouveau
**Déjà en place (ton code existant)** : appli par matière `/qcm/<matiere>/` (Flask + SQLite sur le Pi), séances en classe (direct / série,
QR au tableau), entraînement libre (`?c=<chapitre>`), identifiant élève anonyme, vue enseignant avec taux de réussite par question, export CSV.
**État des données** : `physique-ondes-ipsa/qcm/td1_qcm.yaml` (3 questions) et `agregation-mathematiques/qcm/dev1_qcm.yaml` (1 question) sont
exploitables ; **`mecanique-de-point-ipsa/qcm/td1_qcm.yaml` est vide (0 octet)** → aucun QCM pour la mécanique tant qu'il n'est pas rempli
(`python3 tools/qcm.py new mecanique-de-point-ipsa chap1 "Titre"`).

**Nouveau**
- **Lien + QR sur n'importe quelle page** : `config.yaml > qcm > liens` rattache un chapitre à un TD / TP / projet / cours / **exercice**.
  (Automatique aussi pour les questions avec `td:` ou `lie_a:`.) Le QR renvoie à `qcm.base_url` : scanné, l'élève s'entraîne.
- **Maison, configurable** : `acces_libre` accepte maintenant une fenêtre de dates par chapitre/matière :
  `chapitres: {td1_qcm: {libre: true, du: 2026-12-01, au: 2027-01-15}}`. Hors fenêtre : fermé (serveur : 403, Quartz : pas de lien).
- **`python3 tools/qcm_stats.py`** (sur le Pi) : élèves, réponses, % juste par chapitre et par question ; `--libre` (maison) / `--classe`,
  `--csv`. Testé sur une base au schéma réel (données fictives).

## 6. Déploiement (Pi)
```bash
git pull
python3 tools/check_evolutions.py          # contrôle des nouveaux réglages
sudo systemctl restart gunicorn-cours      # OBLIGATOIRE cette fois : qcm_data.py a changé (fenêtres de dates)
./web/publish_profile.sh auto
```
Puis git : le déplacement du dossier du projet doit être commité (`git add -A`).

## 7. Limites / ce que je n'ai pas pu vérifier
- Pas de `pdflatex` ni de Quartz ici : j'ai testé l'export Markdown, le build `.tex` du projet (`--no-pdf`), l'hébergement et `check_quartz_links.py`
  avec de faux PDF. À valider chez toi : une compilation PDF réelle et un `npx quartz build`.
- `check_quartz_links.py` signale 2 liens `[[mathematiques/bethe-ansatz]]` cassés : sans rapport avec ces changements (page absente).
- Clé mal orthographiée dans tes données : `rremarques_pedagogiques_ecueils_classiques` (ex5 du TD1 de la piscine) — non affichée.
- `web/server/common_data.py` (ancienne copie) n'est pas mis à jour ; elle peut être supprimée comme indiqué dans DEPLOY_QCM_PI.md.

## 8. Tester les QCM en local (sans Raspberry)
```bash
python3 -m pip install -r requirements.txt   # une fois (toujours « python3 -m pip », pas « pip » seul : voir ci-dessous)
./tools/qcm_local.sh                         # contrôle + construit les pages + lance le serveur
```
- Élève : `http://127.0.0.1:5000/qcm/<matiere>/` (ex. `physique-ondes-ipsa`). Enseignant : bouton de mode dans la page, jeton = `test`
  (`TOKEN=autre ./tools/qcm_local.sh` pour changer). `HOST=0.0.0.0 ./tools/qcm_local.sh` : testable depuis un téléphone du même Wi-Fi.
- Si le script dit « No module named … » alors que tu as fait `pip install` : `pip` et `python3` ne sont pas le même Python (Anaconda + `.venv`).
  Le script affiche le Python utilisé et propose d'installer lui-même avec `python3 -m pip`. `segno` (QR codes) est optionnel pour ce test.
- Modifier un `qcm/*.yaml` est pris en compte en rechargeant la page ; un changement de thème / gabarit demande de relancer le script.
- Les réponses vont dans `web/server/qcm_data.sqlite3` (ignoré par git) : `python3 tools/qcm_stats.py --matiere physique-ondes-ipsa`.
- Testé ici de bout en bout : page élève (200), figure servie, séance libre, 3 réponses d'élèves, rapport enseignant, `qcm_stats`.
- `mecanique-de-point-ipsa` n'a aucune question (fichier vide) : sa page s'ouvre mais reste vide. Pour tester : `ondes` ou `agregation-mathematiques`.

## 9. Figures et animations dans un QCM
Se mettent sur **la question** (pas sur les choix de réponse), au même format que dans les TD :
```yaml
- id: q_onde_1
  question: "Quelle est la longueur d'onde sur la figure ?"
  figure: {ref: td1_ex0_onde_x_minus_ct, legende: "Onde progressive"}     # ou une liste de figures
  animation: {ref: anim_corde_onde, formats: [gif]}                          # + params: {...} comme dans un TD
  choix: [...]
```
- **`figure: {ref: nom}`** → `web/public/figures/nom.svg`, produit depuis `figures/tikz/nom.tex` (le même TikZ que dans les PDF) par
  `python3 figures/render_web.py` (demande LaTeX + dvisvgm).
- **`figure: {src: /figures/mon_image.png}`** → image libre posée dans `web/public/figures/` (aucun LaTeX ; testé avec un SVG).
- **`animation: {ref: anim_xxx}`** → script `animations/src/anim_xxx.py`, sortie `animations/outputs/anim_xxx/animation.gif`, produite par
  `python3 animations/generate_all.py`. **Correction apportée** : ce script ignorait les animations citées dans un QCM ; il les prend maintenant en compte
  (même `ref`, `params`, `formats` que dans un TD).
- ⚠️ `web/public/figures/` et `animations/outputs/` sont dans `.gitignore` (fichiers générés) : sur le Pi, il faut les générer ou les copier, comme pour les TD ;
  une image libre se versionne avec `git add -f web/public/figures/mon_image.png`. nginx les sert déjà (`/figures/`, `/animations/` dans `deploy/nginx-cours.conf`).
- Sans le fichier, la question s'affiche quand même (l'image est simplement retirée). Je n'ai pas pu générer de vraie figure TikZ ni de GIF ici (pas de LaTeX).
