# `web/qcm_app.html` — QCM en direct par QR code

## Ce que ça fait

Un seul fichier HTML autonome (pas de serveur à héberger) qui bascule entre
deux vues :

- **Vue élève** (par défaut — c'est celle que le QR code doit ouvrir) :
  attend qu'un QCM soit "lancé" par l'enseignant, l'affiche avec animation
  liée, propose les choix en gros boutons tactiles, et donne un feedback
  immédiat avec une mascotte (content / neutre / pas content) + une
  explication -- dans la direction artistique "road trip" que tu voulais :
  une petite route en pointillés en haut de l'écran sur laquelle la
  mascotte avance à mesure que l'élève répond aux QCM de la séance.

- **Vue enseignant** : bouton "Vue enseignant" en haut à droite. Génère un
  QR code (pointant vers l'URL de la page elle-même), un sélecteur pour
  choisir quel QCM diffuser (début / milieu / fin), et des statistiques en
  direct (barres bonnes / mauvaises / neutres réponses), mises à jour toutes
  les 3 secondes.

## Comment ça se recharge à chaque séance

Le contenu des QCM n'est **jamais** écrit à la main dans le HTML : il vient
de `data/qcm/*.yaml` (même logique que les PDF). Pour régénérer l'app après
avoir ajouté des QCM :

```bash
python3 web/build_qcm_artifact.py --td td1
# -> build/output/qcm_app.html
```

## Suivi des étudiants **sans compte** — pourquoi pas l'adresse IP

Tu proposais de suivre chaque étudiant par l'adresse IP de son téléphone.
Deux problèmes concrets t'empêcheraient d'avoir ce que tu veux :

1. **Techniquement** : une page web (même hébergée) ne voit l'IP que côté
   serveur, jamais en JavaScript côté navigateur — donc pas possible dans un
   artifact qui tourne entièrement dans le téléphone de l'élève, sans
   serveur à toi. Et même avec un serveur : en salle de classe, tous les
   téléphones connectés au même Wi-Fi IPSA **partagent la même IP publique**
   (NAT) — impossible de distinguer deux étudiants.
2. **Légalement (RGPD)** : une adresse IP est une donnée personnelle. La
   collecter suppose une base légale, une information des étudiants, une
   durée de conservation définie, etc. — une contrainte lourde pour un outil
   pédagogique informel.

**Solution retenue, qui fait ce que tu veux sans ces problèmes** :
au premier passage, le téléphone de l'élève génère lui-même un identifiant
aléatoire (UUID), stocké *sur cet appareil uniquement* (`window.storage`,
portée personnelle). Cet identifiant :

- n'est lié à aucun nom, e-mail ou compte ;
- permet d'empêcher de répondre deux fois au même QCM ;
- permet de reconstituer, uniquement *pour l'élève lui-même* sur son propre
  téléphone, l'historique de ses réponses au fil des séances (clé
  `historique`) ;
- **n'est pas visible par toi** en tant qu'enseignant au niveau individuel —
  tu vois uniquement les statistiques agrégées (combien de bonnes/mauvaises/
  neutres réponses par QCM), stockées séparément en portée "partagée"
  (`shared: true`).

Si tu veux vraiment un suivi nominatif par étudiant d'une séance à l'autre
(par ex. pour un carnet de progression individuel que *toi* tu peux
consulter), la solution propre est de demander un identifiant stable et
volontaire (prénom + numéro étudiant, ou un pseudo choisi une fois), plutôt
que l'IP — je peux l'ajouter facilement si tu le souhaites (un champ texte
au premier lancement, mémorisé ensuite sur l'appareil).

## Limites connues (honnêtes)

- Si un élève change de téléphone ou vide son cache, il repart avec un
  nouvel identifiant (nouvelle "table rase").
- Les statistiques par QCM font une requête par réponse au moment de
  l'affichage (acceptable pour une classe de 20-40 personnes ; à revoir si
  tu vises des amphis de plusieurs centaines).
- Le stockage `window.storage` n'existe que dans le contexte de l'artifact
  Claude — si tu veux à terme sortir cet outil de Claude.ai (site
  autonome), il faudra le brancher sur une vraie base de données (le code
  JS est écrit pour que ce soit un remplacement direct des fonctions
  `storageGet/storageSet/storageList`).

## Déploiement sur ton Raspberry Pi (hors Claude.ai) — déjà fait

`qcm_app_template.html` détecte tout seul s'il tourne dans un artifact
Claude (`window.storage` existe) ou pas, et dans ce dernier cas bascule
automatiquement sur des appels `fetch()` vers un petit serveur Flask fourni
dans `web/server/app.py` — aucune ligne à changer dans le HTML.

```bash
pip install flask --break-system-packages
python3 web/server/app.py        # écoute sur 0.0.0.0:5000, sert aussi qcm_app.html sur "/"
```

- Stockage : un seul fichier SQLite (`web/server/qcm_data.sqlite3`), zéro
  configuration — largement suffisant pour un Raspberry Pi et une classe.
  Testé de bout en bout (get/set/list/delete + cookie anonyme) avant livraison.
- L'identité anonyme "personnelle" (device_id, historique) est un cookie de
  session généré par le serveur au premier appel — toujours pas d'IP, pour
  les mêmes raisons que ci-dessus (NAT de classe + RGPD).
- En prod sur le Pi : lance-le dans un service `systemd` ou un `tmux`
  détaché (`app.run(debug=True)` est fait pour le développement seulement —
  passe `debug=False` et mets un vrai serveur WSGI, ex. `gunicorn`, avant un
  usage en classe réel).
- Le serveur sert aussi `qcm_app.html` lui-même sur `/` — pratique pour
  n'avoir qu'un seul processus à lancer sur le Pi (le QR code pointera alors
  vers `http://<ip-du-pi>:5000/`).

## Notebooks interactifs (JupyterLite plus tard)

`notebooks/build_notebooks.py` génère un `.ipynb` par exercice (mêmes
profils de visibilité que le site) avec une cellule de code qui rejoue
l'animation matplotlib inline (`HTML(anim.to_jshtml())`, testé et exécuté
avec succès via `jupyter nbconvert --execute`). Les cellules
correction/solution sont taguées `solution`, ce qui permet de les retirer
après coup même d'un notebook déjà généré :

```bash
jupyter nbconvert --to notebook --TagRemovePreprocessor.remove_cell_tags='["solution"]' \
    --output public_ex1.ipynb ex1_corde_nylon.ipynb
```

Objectif à terme : embarquer ces notebooks directement sur le site via
JupyterLite (exécution 100% dans le navigateur, sans serveur Python sur le
Pi) — pas encore configuré, mais les `.ipynb` générés sont déjà valides et
exécutables tels quels en attendant.
