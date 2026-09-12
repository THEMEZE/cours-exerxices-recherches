#!/bin/bash
# ============================================================
# stop_tunnel.sh — Cours d'Ondes (IPSA)
#
# Remet la page GitHub Pages de redirection (cours/index.html) en
# mode "hors ligne". Appelé automatiquement par start_tunnel.sh (trap
# EXIT/INT/TERM), et peut aussi être invoqué manuellement ou via
# ExecStop= d'un service systemd.
#
# Idempotent : peut être lancé plusieurs fois sans risque.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDIRECT_DIR="$SCRIPT_DIR/../RedirectPages"

source "$REDIRECT_DIR/tools/lib_redirect.sh"

GITHUB_REDIRECT_REPO_SSH="git@github.com:THEMEZE/redirect-pages.git"
REDIRECT_PROJECT="cours"
GIT_NAME="SunsetEvasion"
GIT_EMAIL="contact@sunset-evasion.fr"

TITLE="Cours d'Ondes — IPSA"
FAVICON_TAG="<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌊</text></svg>\">"
LOGO="🌊📡"
OFFLINE_MESSAGE="Le site du cours d'ondes n'est pas en ligne pour le moment.<br>Le Raspberry Pi est peut-être arrêté."

echo ""
echo "🛑 Cours d'Ondes — restauration de la page hors ligne..."

if [ ! -d "$REDIRECT_DIR/.git" ]; then
    echo "❌ $REDIRECT_DIR n'est pas un dépôt git — abandon."
    exit 0
fi

mkdir -p "$REDIRECT_DIR/$REDIRECT_PROJECT"
redirect_write_offline \
    "$REDIRECT_DIR/$REDIRECT_PROJECT/index.html" \
    "$TITLE" "$FAVICON_TAG" "$LOGO" "$OFFLINE_MESSAGE"

redirect_publish "$GITHUB_REDIRECT_REPO_SSH" "$REDIRECT_DIR" "$REDIRECT_PROJECT" \
    "$GIT_NAME" "$GIT_EMAIL" "Passage hors ligne $(date '+%Y-%m-%d %H:%M:%S')"

echo "✅ Page hors ligne restaurée pour le cours d'ondes."
