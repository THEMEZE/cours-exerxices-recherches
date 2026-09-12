# Déploiement sur le Raspberry Pi — calqué sur RodTrip

Ce document explique exactement ce qu'il faut faire côté Git, et où
Quartz 5 s'intègre. Tout ce qui est décrit ici a été **testé** (clone
réel de Quartz v5, build réel avec du contenu généré + des notes
perso, callouts Obsidian et KaTeX vérifiés dans le HTML produit) —
pas seulement écrit par analogie avec RodTrip.

## 1. Deux dépôts Git, pas un seul

C'est le point important qui a changé par rapport à la première
version de ce document. Toi : *"c'est un peu les documents finis faits
par moi personnellement"* — ça veut dire que tes notes de gravitation
quantique, Bethe ansatz, agrégation, etc. n'ont **aucune autre source
de vérité** que ce que tu écris directement dans Quartz. Contrairement
au cours d'ondes (dont la source de vérité est `data/*.yaml` dans
`CoursOndes`), ces notes-là doivent être versionnées **elles-mêmes**.

D'où deux dépôts GitHub séparés, tous les deux privés :

| Dépôt          | Contient                                        | Qui écrit dedans |
|-----------------|--------------------------------------------------|-------------------|
| `CoursOndes`    | `data/*.yaml`, scripts de génération PDF/site/QCM | Toi, en éditant le YAML |
| `Quartz5`       | Tes notes perso (`content/mathematiques/`, `content/physique/gravitation-quantique/`, etc.) + le moteur Quartz lui-même | Toi, en éditant les `.md` directement (Obsidian ou autre éditeur) |

`CoursOndes` **écrit dans** `Quartz5/content/physique/ipsa-ondes/` à
chaque régénération (voir plus bas), mais ce sous-dossier est exclu du
`.gitignore` de `Quartz5` : ce n'est pas à `Quartz5` de le versionner,
il est déjà versionné (sous forme de données sources) dans
`CoursOndes`.

Sur le Raspberry, les deux vivent en **siblings**, comme RodTrip et
RedirectPages :

```
/mnt/mariage_data/
├── RedirectPages/     (partagé par tous les projets)
├── RodTrip/
├── CoursOndes/         (génère PDF/animations/QCM + écrit dans Quartz5/content/physique/ipsa-ondes/)
└── Quartz5/             (le jardin numérique lui-même -- CE QUI EST SERVI par nginx)
```

**Un seul serveur, un seul tunnel, une seule page de redirection** :
c'est `CoursOndes` qui possède `run.sh` / `start_tunnel.sh` /
`nginx-cours.conf` / le service Gunicorn. `Quartz5` n'a pas son propre
tunnel ni son propre nginx — il n'a qu'un script `update_content.sh`
qui met à jour ses notes puis reconstruit le site que `CoursOndes`
sert déjà.

## 2. Vue d'ensemble du flux

```
Mac (toi)                                          Raspberry Pi
--------------------------                         --------------------------------
edite data/*.yaml (ondes)   --push.sh-->  GitHub    CoursOndes/update_code.sh
                                                       -> regenere PDF/site
                                                       -> ecrit dans ../Quartz5/
                                                          content/physique/ipsa-ondes/

edite les .md (notes perso) --push.sh-->  GitHub    Quartz5/update_content.sh
                                                       -> git pull tes notes
                                                       -> npx quartz build

                                                     nginx (port 8091, cote CoursOndes)
                                                       -> cloudflared tunnel
                                                       -> URL changeante (trycloudflare.com)
                                                       -> start_tunnel.sh republie le lien fixe
                                                          sur redirect-pages/cours/index.html
                                                          (https://themeze.github.io/redirect-pages/cours/)
```

## 3. Ce que tu dois faire, dans l'ordre

### Une seule fois : les deux dépôts GitHub

```bash
# CoursOndes (déjà fait si tu as suivi la version précédente de ce doc)
cd CoursOndes
git init && git add . && git commit -m "Premier commit"
git remote add origin git@github.com:THEMEZE/cours-ondes-ipsa.git
git push -u origin main
```

```bash
# Quartz5 -- NOUVEAU
cd Quartz5
git init && git add . && git commit -m "Premier commit"
# Crée un dépôt privé "quartz5-notes" sur GitHub, puis :
git remote add origin git@github.com:THEMEZE/quartz5-notes.git
git push -u origin main
```

### Une seule fois : cloner les deux sur le Raspberry

```bash
cd /mnt/mariage_data
git clone git@github.com:THEMEZE/quartz5-notes.git Quartz5
git clone git@github.com:THEMEZE/cours-ondes-ipsa.git CoursOndes

cd Quartz5 && npm install && cd ..
cd CoursOndes && ./run.sh
```

`run.sh` (dans `CoursOndes`) installe les paquets système, crée le
venv Python, génère une première fois le contenu du cours DANS
`../Quartz5/content/physique/ipsa-ondes/`, construit Quartz
(`npx quartz build` à l'intérieur de `../Quartz5`), installe les
services (Gunicorn + nginx), puis lance le tunnel.

### À chaque fois que tu écris une nouvelle note perso

```bash
# Sur ton Mac, dans Quartz5/
./tools/Mac/push.sh "Notes sur l'ansatz de Bethe algebrique"
```

```bash
# Sur le Raspberry
cd /mnt/mariage_data/Quartz5
./tools/Raspberry/update_content.sh
```

Ce script fait `git pull` de tes notes, régénère par-dessus la section
`physique/ipsa-ondes/` (en appelant `CoursOndes/web/publish_profile.sh`
avec le profil actuellement actif), puis reconstruit Quartz. Comme
`CoursOndes` sert déjà `Quartz5/public/` en statique, **rien à
redémarrer côté serveur** — la prochaine visite du site voit la
nouvelle version.

### À chaque fois que tu modifies le cours d'ondes (data/*.yaml, TD...)

Inchangé par rapport à avant :

```bash
# Mac
cd CoursOndes && ./tools/Mac/push.sh "TD2 corrige ajoute"
# Raspberry
cd /mnt/mariage_data/CoursOndes && ./tools/Raspberry/update_code.sh
```

`update_code.sh` régénère les PDF, la section `physique/ipsa-ondes/`
dans `Quartz5`, ET reconstruit Quartz lui-même (via
`web/publish_profile.sh`) — donc un simple push côté cours suffit, tu
n'as pas besoin de lancer les deux scripts à chaque fois.

### Basculer entre "avant séance" et "corrigé"

```bash
cd /mnt/mariage_data/CoursOndes
./web/publish_profile.sh avant_seance      # avant le TD
./web/publish_profile.sh corrige_complet   # juste après le TD
```

### Démarrer / arrêter la mise en ligne

```bash
cd /mnt/mariage_data/CoursOndes
./run.sh            # tout, la première fois
./start_tunnel.sh    # relance juste le tunnel + republie le lien fixe
./stop_tunnel.sh      # remet la page GitHub Pages en "hors ligne"
```

## 4. Comment ajouter tes prochains sujets (maths, physique, recherche...)

La structure est déjà en place dans `Quartz5/content/` :

```
content/
├── index.md                          <- page d'accueil du jardin
├── physique/
│   ├── index.md
│   ├── ipsa-ondes/                    <- regenere automatiquement, NE PAS EDITER
│   ├── agregation-physique/index.md
│   ├── gravitation-quantique/index.md
│   ├── supergravite/index.md
│   ├── theorie-m/index.md
│   └── theorie-du-tout/index.md
├── mathematiques/
│   ├── index.md
│   ├── agregation-mathematiques/index.md
│   ├── integrabilite-quantique/index.md
│   └── bethe-ansatz/index.md
├── chimie/index.md
├── recherche/index.md
├── etudes/index.md
└── outils/
    ├── index.md
    ├── latex/index.md
    └── programmation/index.md
```

Chaque `index.md` de sujet est un stub avec juste le frontmatter
(`title`, `tags`) — ajoute simplement d'autres fichiers `.md` dans le
même dossier (ex: `content/mathematiques/bethe-ansatz/xxz-chain.md`)
et Quartz les indexera automatiquement (recherche plein texte, graphe
de liens, backlinks — tout ça est déjà activé dans
`quartz.config.yaml`, ce sont des plugins du template par défaut).
Utilise des wikilinks `[[mathematiques/bethe-ansatz/xxz-chain]]` pour
relier tes pages entre elles, comme dans Obsidian.

## 5. Différence importante avec RodTrip (Django)

RodTrip doit modifier `settings.py` (ALLOWED_HOSTS) à chaque
redémarrage du tunnel, parce que Django refuse les requêtes dont le
Host HTTP n'est pas reconnu. Ici, nginx statique + Flask derrière un
socket Unix ne font aucune vérification de ce genre : **rien à
modifier** avant de relancer le tunnel, seul le lien affiché change.

## 6. Ports utilisés sur le Raspberry

| Projet        | Port nginx interne | Service Gunicorn   |
|----------------|---------------------|----------------------|
| RodTrip        | 8090                 | gunicorn-rodtrip      |
| Cours d'Ondes + Quartz5 (même nginx) | 8091 | gunicorn-cours |

## 7. Une incohérence repérée dans RodTrip (à corriger si tu veux)

`RodTrip/deploy/gunicorn-rodtrip.service` a
`WorkingDirectory=/mnt/projects/RodTrip`, alors que
`tools/Raspberry/update_code.sh` et `nginx-rodtrip.conf` utilisent
tous les deux `/mnt/mariage_data/RodTrip`. Je l'ai gardé cohérent
partout dans `deploy/gunicorn-cours.service`
(`/mnt/mariage_data/CoursOndes`).

## 8. Ce qui a été réellement testé (pas juste écrit par analogie)

- Clone réel de `jackyzha0/quartz` branche `v5`, `npm install` (372
  paquets), `npx quartz create` en mode non-interactif.
- Build réel avec le contenu généré par `export_markdown.py` (14
  fichiers) : callouts Obsidian (`class="callout tip"`), KaTeX présent
  dans le HTML, 98 fichiers émis sans erreur.
- Build réel combinant contenu généré (cours) + notes perso écrites à
  la main (17 fichiers) : 31 fichiers en entrée, 167 fichiers émis,
  wikilinks entre les deux (`physique/index.md` -> `physique/ipsa-ondes/`,
  `mathematiques/index.md` -> `bethe-ansatz/`) résolus correctement.
- **Un vrai bug trouvé et corrigé** : Quartz normalise les chemins
  d'image en minuscules dans son résolveur de liens. Un fichier généré
  `td1_ex1_corde_t_T8.svg` (majuscule) était référencé en minuscules
  dans le HTML produit -> image cassée (404 confirmé par curl). Corrigé
  en forçant `.lower()` sur tous les noms de fichiers générés
  (figures et animations) dans `common_data.py` et
  `figures/render_web.py` — vérifié à nouveau après correction.
