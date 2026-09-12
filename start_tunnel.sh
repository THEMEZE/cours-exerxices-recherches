#!/bin/bash
# ============================================================
# start_tunnel.sh — Cours d'Ondes (IPSA)
#
# Calqué sur RodTrip/start_tunnel.sh. Lance le tunnel Cloudflare et
# met à jour la page de redirection publiée sur GitHub Pages.
#
# ── Pourquoi un dépôt GitHub séparé pour la redirection ? ──────
# Même raison que pour RodTrip : ce dépôt (cours-ondes-ipsa) peut
# rester privé, alors que "redirect-pages" est public et partagé
# entre TOUS les projets du Raspberry (RodTrip, BibiUnion, et
# maintenant Cours d'Ondes) -- un sous-dossier par projet.
#
# ── Différence avec RodTrip : pas de settings.py à modifier ────
# RodTrip est du Django, qui refuse les requêtes dont le Host HTTP
# n'est pas dans ALLOWED_HOSTS -- il faut donc injecter l'hôte du
# tunnel dans settings.py à chaque redémarrage. Ici le site est du
# nginx statique (Quartz) + Flask derrière un socket Unix : aucun des
# deux ne fait de vérification de Host, donc RIEN à modifier avant de
# relancer le tunnel. Seul le lien affiché change.
#
# Un seul clone LOCAL partagé de RedirectPages, comme pour RodTrip :
# /mnt/mariage_data/RedirectPages (dossier FRÈRE de celui-ci).
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDIRECT_DIR="$SCRIPT_DIR/../RedirectPages"

# Copie unique et partagée entre tous les projets (RodTrip, BibiUnion, Cours...)
# shellcheck source=../RedirectPages/tools/lib_redirect.sh
source "$REDIRECT_DIR/tools/lib_redirect.sh"

# ── Configuration du projet (à adapter si besoin) ─────────────
GITHUB_REDIRECT_REPO_SSH="git@github.com:THEMEZE/redirect-pages.git"
REDIRECT_PROJECT="cours"
GIT_NAME="SunsetEvasion"
GIT_EMAIL="contact@sunset-evasion.fr"

TITLE="Cours d'Ondes — IPSA"
FAVICON_TAG="<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌊</text></svg>\">"
LOGO="🌊📡"
LABEL="Cours d'Ondes"
REDIRECT_PATH="/"          # racine du site Quartz (nginx, port 8091)

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    Démarrage du tunnel Cloudflare ...    ║"
echo "╚══════════════════════════════════════════╝"

LOG="/tmp/cours_tunnel.log"
rm -f "$LOG"

cloudflared tunnel --url http://localhost:8091 >"$LOG" 2>&1 &
TUNNEL_PID=$!

# Restaure automatiquement la page "hors ligne" si le tunnel s'arrête
# (Ctrl+C, kill, arrêt propre du service, plantage...).
trap '"$SCRIPT_DIR/stop_tunnel.sh"; kill $TUNNEL_PID 2>/dev/null' EXIT INT TERM

URL=""
echo "⏳ En attente de l'URL du tunnel..."
RETRIES=0
while [ -z "$URL" ] && [ $RETRIES -lt 30 ]; do
    sleep 3
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1)
    RETRIES=$((RETRIES + 1))
done

if [ -z "$URL" ]; then
    echo "❌ Impossible d'obtenir l'URL du tunnel après 90s. Vérifiez cloudflared."
    exit 1
fi

echo "✅ URL détectée : $URL"

echo "🔲 QR code (terminal) :"
if command -v qrencode >/dev/null 2>&1; then
    qrencode -t ANSIUTF8 "${URL}${REDIRECT_PATH}"
else
    echo "   (installe 'qrencode' pour afficher un QR ici : sudo apt install qrencode)"
fi

# ══════════════════════════════════════════════════════════
# Publication de la redirection sur GitHub Pages (clone unique partagé)
# ══════════════════════════════════════════════════════════
echo ""
echo "📤 Publication de la redirection sur GitHub Pages..."

if [ ! -d "$REDIRECT_DIR/.git" ]; then
    echo "❌ $REDIRECT_DIR n'est pas un dépôt git. Clone-le une fois manuellement :"
    echo "   git clone $GITHUB_REDIRECT_REPO_SSH $REDIRECT_DIR"
    echo "   Le site reste accessible via l'URL du tunnel : $URL"
    wait $TUNNEL_PID
    exit 0
fi

mkdir -p "$REDIRECT_DIR/$REDIRECT_PROJECT"
redirect_write_online \
    "$REDIRECT_DIR/$REDIRECT_PROJECT/index.html" \
    "$TITLE" "$FAVICON_TAG" "$LOGO" "${URL}${REDIRECT_PATH}" "$LABEL"

redirect_publish "$GITHUB_REDIRECT_REPO_SSH" "$REDIRECT_DIR" "$REDIRECT_PROJECT" \
    "$GIT_NAME" "$GIT_EMAIL" "Mise à jour automatique de la redirection $(date '+%Y-%m-%d %H:%M:%S')"

cd "$SCRIPT_DIR"

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  ✅ Site en ligne !                                     ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  Site (Quartz)   : ${URL}/"
echo "║  QCM en direct    : ${URL}/qcm/"
echo "║  Lien fixe (public): https://themeze.github.io/redirect-pages/cours/"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

wait $TUNNEL_PID
