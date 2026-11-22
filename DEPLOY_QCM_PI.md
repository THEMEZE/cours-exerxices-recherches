# Déployer les QCM sur ton Raspberry Pi (CoursOndes + Quartz + QR codes)

Constat d'après tes fichiers : nginx (port 8091, derrière le tunnel Cloudflare `cours.sunset-evasion.fr`)
sert déjà Quartz, `/qcm/<matiere>/` en statique et relaie `/api/` vers gunicorn (socket `/run/gunicorn-cours.sock`).
Les pages Quartz et l'appli QCM sont donc sur **le même site HTTPS** : pas de CORS, rien de nouveau à héberger.
Dépôt GitHub = source ; le Pi fait `git pull`.

Chemins ci-dessous : projet `/mnt/mariage_data/CoursOndes`, venv `/mnt/mariage_data/CoursOndes/venv`.

## 1. Code

Copie les fichiers de ce zip à la racine du projet (même chemins relatifs), commit, push, puis sur le Pi :
```bash
cd /mnt/mariage_data/CoursOndes && git pull
./venv/bin/pip install segno        # QR codes des pages Quartz
# si publish_profile.sh utilise le python3 système plutôt que le venv :  pip3 install --user segno
```
Fichiers **complets** fournis pour ce que tu m'as envoyé (aucun patch à appliquer) :
`common_data.py` (le doublon de `load_all_qcm` est supprimé), `web/export_markdown.py`, `build/build.py`,
`build/pdf_status.py`, `build/config.yaml`, `deploy/nginx-cours.conf`, `deploy/gunicorn-cours.service`.
Nouveaux : `qcm_data.py`, `templates/qcm.tex.j2`, `tools/qcm.py`, `data/qcm_modele.yaml`, `web/server/app.py` (remplacé),
`web/qcm_app_template.html` (remplacé), `web/build_qcm_artifact.py` (remplacé).
Optionnel : supprimer `web/server/common_data.py` (ancienne copie périmée, dans le dossier de travail de gunicorn).

## 2. Jeton enseignant (une fois)

```bash
sudo install -m 640 -o root -g pi /dev/null /etc/gunicorn-cours.env
echo "QCM_TEACHER_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" | sudo tee /etc/gunicorn-cours.env
sudo cat /etc/gunicorn-cours.env        # note le jeton : tu le saisis dans « Vue enseignant »
```
Le service fourni contient déjà `EnvironmentFile=/etc/gunicorn-cours.env`.

## 3. Installer service + nginx

```bash
sudo cp deploy/gunicorn-cours.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo cp deploy/nginx-cours.conf /etc/nginx/sites-available/cours && sudo nginx -t && sudo systemctl reload nginx
sudo systemctl restart gunicorn-cours
```
Seul ajout nginx : `location = /health` (le reste de ta conf est inchangé).
`web/server/qcm_data.sqlite3` est créé/complété automatiquement (tes anciennes tables `kv` restent ; l'API `/api/kv` est
désactivée). Si tu avais testé une version précédente de ce zip, supprime ce fichier avant le restart.

## 4. Publier

```bash
./web/publish_profile.sh auto
```
`build/config.yaml` contient déjà `qcm.base_url: "https://cours.sunset-evasion.fr"` (adresse encodée dans les QR).
Les liens des pages restent relatifs (`/qcm/<matiere>/?c=<chapitre>`) ; `check_quartz_links.py` les vérifie sans modification.

## 5. Vérifier

```bash
curl -s https://cours.sunset-evasion.fr/health                       # {"status":"ok","matieres":[…],"teacher_configured":true}
curl -s https://cours.sunset-evasion.fr/api/qcm/physique-ondes-ipsa/chapitres
python3 tools/qcm.py check
sudo journalctl -u gunicorn-cours -n 30 --no-pager                   # erreurs éventuelles
```
Puis sur un téléphone (hors Wi-Fi) : page Quartz de la matière → scanner un QR → s'entraîner.

## 6. Ensuite, au quotidien

- Ajouter des questions : éditer `data/matieres/<m>/qcm/<chapitre>.yaml` → `git push` → `git pull` sur le Pi : **immédiat**
  dans l'appli. Relancer `./web/publish_profile.sh auto` pour mettre à jour compteurs et QR des pages Quartz.
- En cours : « Vue enseignant » → jeton → *Nouvelle séance* (Direct ou Série) → QR au tableau.
- Sauvegarde (cron hebdo) : `sqlite3 /mnt/mariage_data/CoursOndes/web/server/qcm_data.sqlite3 ".backup '/chemin/qcm_$(date +%F).sqlite3'"`
- Titre des chapitres des anciens fichiers « liste » : ils s'affichent sous le nom du fichier (`td1`). Pour un titre lisible,
  passe le fichier au format compact (clé `titre:`), voir `data/qcm_modele.yaml`.

## 7. Limites connues

- Pas de limitation de débit : si le site devient très public, `limit_req` nginx sur `/api/responses`.
- L'identifiant élève est lié au navigateur : autre appareil = autre progression.
- Le tunnel Cloudflare fait passer les IP : ce serveur n'enregistre de toute façon aucune IP.
