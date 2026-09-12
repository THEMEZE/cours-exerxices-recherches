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


echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗"
echo    "║     🌊 Cours d'Ondes — Installation      ║"
echo -e "╚══════════════════════════════════════════╝${RESET}"
echo ""


PROJECT="/mnt/mariage_data/CoursOndes"

info "Paquets système (Python, Node/Quartz, LaTeX de secours, nginx)..."

sudo apt update
sudo apt install -y \
    git python3 python3-venv python3-pip \
    nginx \
    nodejs npm \
    poppler-utils \
    qrencode

ok "Paquets système installés"

# ── LaTeX ────────────────────────────────────────────────
# Deux options, comme documenté dans DEPLOY_RASPBERRY.md :
#   1) tectonic (léger, déjà utilisé par RodTrip -- voir
#      tools/Raspberry/install_tectonic.sh de RodTrip, réutilisable
#      tel quel ici, un Raspberry n'a besoin que d'UNE install)
#   2) texlive complet (plus lourd, mais 100% testé avec ce projet :
#      tcolorbox + tikzmark + animate + babel french)
# Par défaut on installe texlive ici, car c'est la config testée.
# Si tectonic est déjà installé sur ce Pi pour RodTrip, tu peux
# commenter les 2 lignes suivantes.
info "LaTeX (texlive, peut prendre plusieurs minutes sur un Pi)..."
sudo apt install -y texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-lang-french
ok "LaTeX installé"

cd "$PROJECT" || err "Projet introuvable : $PROJECT (clone-le d'abord, voir DEPLOY_RASPBERRY.md)"

info "Environnement virtuel Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install gunicorn -q
ok "Dépendances Python installées"

mkdir -p logs

echo ""
echo -e "${BOLD}Prochaine étape :${RESET} ./run.sh"
echo -e "${YELLOW}Rappel :${RESET} Quartz5 est un dépôt SÉPARÉ (sibling), voir DEPLOY_RASPBERRY.md"
echo "  pour le cloner/configurer si ce n'est pas déjà fait :"
echo "  cd /mnt/mariage_data && git clone <ton-repo-quartz5> Quartz5"
echo ""
