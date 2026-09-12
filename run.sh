#!/bin/bash
set -e

GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'; RESET='\033[0m'; BOLD='\033[1m'
ok()   { echo -e "${GREEN}  ✅  $1${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠️   $1${RESET}"; }
err()  { echo -e "${RED}  ❌  $1${RESET}"; exit 1; }

echo -e "\n⏳ Installation système + Python + Quartz (tools/Raspberry/setup.sh)..."
./tools/Raspberry/setup.sh
ok "Installation terminée"

source venv/bin/activate

echo -e "\n⏳ Première génération du site (profil 'avant_seance' par défaut)..."
echo "avant_seance" > web/.current_profile
python3 build/build.py
./web/publish_profile.sh avant_seance
ok "Site généré"

echo -e "\n⏳ Installation des services systemd (Gunicorn pour le QCM)..."
sudo cp deploy/gunicorn-cours.socket  /etc/systemd/system/
sudo cp deploy/gunicorn-cours.service /etc/systemd/system/

sudo cp deploy/nginx-cours.conf /etc/nginx/sites-available/cours
sudo ln -sf /etc/nginx/sites-available/cours /etc/nginx/sites-enabled/cours

sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn-cours.socket
sudo systemctl enable --now gunicorn-cours.service
sudo nginx -t && sudo systemctl restart nginx

ok "Services démarrés"

echo -e "\n${BOLD}╔══════════════════════════════════════════╗"
echo    "║  ✅  Installation terminée !              ║"
echo    "║  🚀  Lancement du tunnel Cloudflare...   ║"
echo -e "╚══════════════════════════════════════════╝${RESET}\n"

chmod +x start_tunnel.sh stop_tunnel.sh
./start_tunnel.sh
