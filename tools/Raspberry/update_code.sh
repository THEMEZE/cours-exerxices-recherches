#!/bin/bash
set -e

# ── Couleurs ──────────────────────────────────────────────
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
BLUE='\033[94m'
RESET='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "${GREEN}  ✅  $1${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠️   $1${RESET}"; }
err()  { echo -e "${RED}  ❌  $1${RESET}"; exit 1; }
info() { echo -e "${BLUE}  ℹ️   $1${RESET}"; }


PROJECT="/mnt/mariage_data/CoursOndes"
BACKUP_DIR="/mnt/mariage_data/backups_CoursOndes"


echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗"
echo    "║       🌊 Cours d'Ondes — Update          ║"
echo -e "╚══════════════════════════════════════════╝${RESET}"
echo ""


cd "$PROJECT" || err "Projet introuvable : $PROJECT"


# ─────────────────────────────────────────────
# Git
# ─────────────────────────────────────────────

info "Récupération des changements GitHub..."

git fetch origin

ok "Git synchronisé"


info "Vérification du dépôt distant..."

# Comme RodTrip protège db.sqlite3/media/, on vérifie qu'aucun fichier
# généré (PDF, animation, figure, base QCM) n'a été commité par erreur
# -- ces fichiers doivent TOUJOURS être régénérés localement, jamais
# transportés par Git (cf. .gitignore).
if git ls-tree -r origin/main --name-only | grep -qE '^(build/output/.*\.pdf|animations/outputs/|web/public/figures/|web/server/qcm_data\.sqlite3)'
then
    err "Un fichier généré (PDF/animation/figure/base QCM) a été trouvé dans Git -- vérifie le .gitignore côté Mac."
fi

ok "Dépôt propre (pas de fichier généré versionné)"


# ─────────────────────────────────────────────
# Backup SQLite (base QCM du Raspberry)
# ─────────────────────────────────────────────

info "Sauvegarde de la base QCM..."

mkdir -p "$BACKUP_DIR"

if [ -f web/server/qcm_data.sqlite3 ]
then
    cp web/server/qcm_data.sqlite3 \
    "$BACKUP_DIR/qcm_$(date +%Y%m%d_%H%M%S).sqlite3"

    ok "Base QCM sauvegardée"
else
    warn "Aucune base QCM trouvée (première installation)"
fi


# ─────────────────────────────────────────────
# Mise à jour code
# ─────────────────────────────────────────────

info "Mise à jour du code..."

git reset --hard origin/main

ok "Code mis à jour"


# ─────────────────────────────────────────────
# Python
# ─────────────────────────────────────────────

if [ -d venv ]
then
    source venv/bin/activate

    info "Mise à jour dépendances Python..."

    pip install -r requirements.txt -q

    ok "Dépendances installées"
else
    warn "Pas de venv trouvé -- lance d'abord tools/Raspberry/setup.sh"
fi


# ─────────────────────────────────────────────
# Régénération du contenu (PDF, animations, figures, site)
# ─────────────────────────────────────────────

info "Régénération des PDF (build/build.py)..."
python3 build/build.py
ok "PDF régénérés"

PROFILE="avant_seance"
if [ -f web/.current_profile ]; then
    PROFILE="$(cat web/.current_profile)"
fi
info "Régénération du site avec le profil actif : '$PROFILE'..."
./web/publish_profile.sh "$PROFILE"
ok "Site régénéré (profil '$PROFILE')"


# ─────────────────────────────────────────────
# Systemd Gunicorn (backend QCM)
# ─────────────────────────────────────────────

info "Vérification du service Gunicorn (QCM)..."

if [ -f deploy/gunicorn-cours.socket ]
then
    sudo cp deploy/gunicorn-cours.socket \
    /etc/systemd/system/

    ok "Socket Gunicorn installé"
fi

if [ -f deploy/gunicorn-cours.service ]
then
    sudo cp deploy/gunicorn-cours.service \
    /etc/systemd/system/

    ok "Service Gunicorn installé"
fi

sudo systemctl daemon-reload

if systemctl list-unit-files | grep -q gunicorn-cours.socket
then
    sudo systemctl enable gunicorn-cours.socket
    sudo systemctl restart gunicorn-cours.socket
fi

if systemctl list-unit-files | grep -q gunicorn-cours.service
then
    sudo systemctl enable gunicorn-cours.service
    sudo systemctl restart gunicorn-cours.service

    ok "Gunicorn redémarré"
else
    warn "Service Gunicorn absent"
fi


# ─────────────────────────────────────────────
# nginx (statique -- pas de redémarrage nécessaire sauf
# changement de la conf elle-même)
# ─────────────────────────────────────────────

if [ -f deploy/nginx-cours.conf ]
then
    sudo cp deploy/nginx-cours.conf /etc/nginx/sites-available/cours
    sudo ln -sf /etc/nginx/sites-available/cours /etc/nginx/sites-enabled/cours
    sudo nginx -t && sudo systemctl reload nginx
    ok "nginx rechargé"
fi


# ─────────────────────────────────────────────
# Fin
# ─────────────────────────────────────────────

ok "Cours d'Ondes opérationnel 🌊"

echo ""
