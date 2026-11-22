# QCM en direct — Quartz + Flask + SQLite (Raspberry Pi)

Fusion du prototype « qcm-quartz » (séances, correction serveur, SQLite) avec ton moteur YAML.
Les questions restent dans `data/matieres/<matiere>/qcm/` ; **autant que tu veux par matière et par chapitre**.

## 1. Ajouter des questions

Un fichier = un chapitre : `data/matieres/<matiere>/qcm/<chapitre>.yaml`.

```bash
python3 tools/qcm.py new physique-ondes-ipsa chap3_interferences "Chap. 3 — Interférences"
# -> édite le fichier créé (modèle commenté : data/qcm_modele.yaml)
python3 tools/qcm.py check      # 1 seule bonne réponse, ids uniques, énoncés non vides
python3 tools/qcm.py stats      # nombre de questions par matière / chapitre
```

Forme courte (une question = 4 lignes) :

```yaml
questions:
  - q: "Un son de 440 Hz à c = 340 m/s a une longueur d'onde proche de…"
    choix: ["0,77 m", "1,3 m", "7,7 m"]
    bonne: 1                      # numéro (1 = première) ou lettre
    explication: "λ = c/f ≈ 0,77 m."
```

- `$maths$` (KaTeX sur le site, LaTeX dans les PDF), `**gras**`, `*italique*`, Unicode (λ, √, ≈, x²) accepté.
- « Je ne sais pas encore » est ajouté tout seul (`qcm:` dans `build/config.yaml`).
- Sans `id:`, l'identifiant est `<chapitre>_q001, _q002…` : **garde l'ordre** ou fixe des `id:` si tu réordonnes
  (les statistiques sont rattachées à l'id).
- L'ancien format (liste de questions complètes, ex. `td1_qcm_debut1`) fonctionne sans modification.
- Fichiers commençant par `_` : ignorés (brouillons).
- **Aucune régénération nécessaire** : le serveur relit les YAML quand ils changent.
  Une question invalide est ignorée (message dans les logs gunicorn) jusqu'à correction.

## 2. Trois modes

| Mode | Usage | Déroulé |
|---|---|---|
| **Libre** | hors cours, sans enseignant | l'étudiant choisit un chapitre (ou toute la matière) sur `/qcm/<matiere>/` ou via `?c=<chapitre>` (lien/QR de Quartz) ; dans l'ordre, au hasard ou seulement les non-réussies ; il peut refaire les ratées ; progression par chapitre ; tes questions ajoutées apparaissent aussitôt |
| **Direct** | amphi / TD | tu lances une question à la fois depuis ta vue enseignant ; les téléphones passent à la question |
| **Série** | entraînement, révision | tout un chapitre (ou toute la matière, N questions max, ordre aléatoire possible) ; chacun avance à son rythme, bilan final avec « à revoir » |

Vue enseignant : bouton « Vue enseignant » → jeton → *Nouvelle séance* → QR code `…/qcm/<matiere>/?s=CODE`.
Sans `?s=`, la page d'accueil de la matière propose les séances en cours et l'entraînement libre.
Boutons : arrêter la question, clôturer (résultats publics), rouvrir, effacer les réponses, export CSV.

## 3. Ce qui change par rapport à l'ancienne appli (sécurité)

- Les bonnes réponses ne quittent jamais le serveur avant la réponse de l'élève (plus de `QCM_DATA` dans la page).
- Le pilotage exige `QCM_TEACHER_TOKEN` (la vue enseignant n'est plus ouverte à tous).
- Une réponse par élève / séance / question, rejouable sans doublon après une coupure réseau.
- Statistiques de classe : agrégées, et visibles d'un élève seulement après sa réponse (ou séance close).
- `/api/kv` (stockage ouvert) est **désactivé** ; `QCM_LEGACY_KV=1` le réactive le temps d'une migration.
- Les anciennes réponses stockées en KV ne sont pas migrées (nouvelles tables `qcm_sessions`, `qcm_responses`).

## 4. Déploiement sur le Pi  (guide pas à pas : `DEPLOY_QCM_PI.md`)

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(24))"     # -> ton jeton enseignant
```
Dans `deploy/gunicorn-cours.service` (section `[Service]`) :
```
Environment=QCM_TEACHER_TOKEN=<le jeton>
```
puis `sudo systemctl daemon-reload && sudo systemctl restart gunicorn-cours`.
Le module reste `web.server.app:app` ; `serve_local.py` fonctionne tel quel.
Ensuite `./web/publish_profile.sh <profil>` régénère les pages `/qcm/<matiere>/` (étape 6, inchangée).
Garde **un seul worker gunicorn par défaut ou 2** : SQLite en mode WAL suffit pour une classe.
Rappel RGPD : l'identifiant est un UUID pseudonyme (pas d'IP) ; préviens les étudiants du suivi de progression.

Hors ligne (Pi sans Internet) : QRCode.js, KaTeX et les polices viennent d'un CDN ; sans lui le QR s'efface
(le code à 6 caractères reste affiché) et les maths s'affichent en `$…$`. Héberge-les en local si besoin.

## 5. PDF de QCM (`build/build.py`)

Cibles `type_doc: qcm` dans `build/config.yaml` (exemples commentés en bas) :
`doc: <chapitre>` ou `all`; options `show_solution`, `nb_questions`, `melanger` (+`graine`), `moments`,
`difficultes`, `inclure_neutre`. Suffixes `_enonce` / `_corrige` comme pour les TD ; `pdf_status.py` suit
l'état fait/périmé (les YAML du chapitre et le bloc `qcm:` entrent dans l'empreinte).
`python3 build/build.py --qcm` ne compile que ces cibles.

## 6. API

Publique : `GET /api/qcm/<m>/chapitres`, `GET /api/sessions?matiere=`, `GET /api/sessions/<code>`,
`POST /api/responses`, `GET /api/statistics/sessions/<code>[?qcm_id=]`, `GET /api/students/me/progress?matiere=`
(en-tête `X-Student-ID`). Enseignant (`Authorization: Bearer <jeton>`) : `/api/teacher/…`
(créer, `launch`, `stop`, `close`, `reopen`, `reset`, `report`, `DELETE`).

## Images et animations dans les QCM

Même convention que les TD. Dans le YAML d'une question :

```yaml
figure: {ref: fig_corde_noeud, legende: "Corde en mode N=2"}   # -> web/public/figures/fig_corde_noeud.svg
figure: {src: /figures/mon_image.png}                           # image libre (fichier dans web/public/figures/)
figure: [{ref: fig_a}, {ref: fig_b}]                            # plusieurs figures
animation: {ref: anim_corde_onde, formats: [gif]}               # -> animations/outputs/anim_corde_onde/animation.gif
```

| Support | Rendu |
|---|---|
| **QCM web** | `<img>` pour la figure (`/figures/…`) et le GIF (`/animations/<ref>/animation.gif`), servis par nginx. |
| **Quartz** | Dans les callouts « QCM de réveil » (moments debut/milieu/fin), images cliquables comme dans les TD. |
| **PDF** | Figure : SVG converti en PDF (cairosvg, sinon rsvg-convert/inkscape), cache `build/generated/qcm_media/`. Animation : le GIF est découpé en frames PNG (≤ 60, 700 px) et inséré avec `\animategraphics` (paquet `animate`) : elle joue dans **Adobe Reader/Acrobat**, les autres lecteurs affichent la 1re image. Sans `animate.sty`, repli sur la 1re image. Option : `animation: {ref: …, pdf_max_images: 100}`. |

Dépendances PDF : `pip install cairosvg pillow` (sur la machine où tu lances `build.py`).
Une figure ou animation introuvable n'empêche rien : avertissement au build, image masquée côté web.
Attention : si `figures/render_web.py` vide `web/public/figures/` avant de régénérer, les images « libres » (`src:`) y seraient effacées ; utilise plutôt des `ref:` générés.

## Accès libre réglé dans build/config.yaml

`qcm: acces_libre:` choisit les chapitres ouverts à l'entraînement hors cours (priorité chapitre > matière > défaut ;
sans bloc, tout est libre). Un chapitre non libre reste utilisable en classe (séances direct / série) et en PDF, mais n'a
ni entrée dans l'appli en libre, ni lien/QR Quartz. Exemples complets : `build/config_qcm_exemple.yaml`.
Lancer en local : `FLASK_DEBUG=1 QCM_TEACHER_TOKEN=test python3 -m web.server.app` (http://127.0.0.1:5000/qcm/<matiere>/).
