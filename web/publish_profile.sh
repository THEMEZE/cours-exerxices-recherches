#!/bin/bash
# ============================================================
# web/publish_profile.sh — Cours d'Ondes (IPSA)
#
# Change le PROFIL DE VISIBILITÉ actuellement publié sur le site
# (voir web/visibility_profiles.yaml) et régénère tout ce qui en
# dépend : Markdown Quartz, JSON, notebooks, puis reconstruit Quartz.
#
# C'est LA commande à lancer sur le Raspberry Pi :
#   - avant une séance :  ./web/publish_profile.sh avant_seance
#   - juste après        :  ./web/publish_profile.sh corrige_complet
#
# Le profil actif est mémorisé dans web/.current_profile (fichier
# local, non versionné -- cf. .gitignore) : tools/Raspberry/
# update_code.sh le relit à chaque `git pull` pour régénérer le site
# avec le MÊME profil que celui laissé actif, sans jamais exposer les
# corrections par erreur après une mise à jour de code.
#
# Usage :
#   ./web/publish_profile.sh <profil> [--matiere <matiere_slug>]
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PROFILE="$1"
shift || true

if [ -z "$PROFILE" ]; then
    echo "Usage: $0 <profil> [--matiere <matiere_slug>]"
    echo "Profils disponibles :"
    python3 - <<'EOF'
import yaml
p = yaml.safe_load(open("web/visibility_profiles.yaml"))["profiles"]
for name in p:
    print(f"  - {name}")
EOF
    exit 1
fi

QUARTZ_CONTENT="${QUARTZ_CONTENT:-$ROOT/../Quartz5/content}"
QUARTZ_DIR="$(dirname "$QUARTZ_CONTENT")"

echo "🔄 Profil actif -> $PROFILE"
echo "$PROFILE" > "$ROOT/web/.current_profile"

echo "1) Figures (SVG) ..."
python3 figures/render_web.py

echo "2) Animations (GIF) ..."
python3 animations/generate_all.py --no-latex

echo "3) Export JSON (site interactif / carrousel) ..."
python3 web/export_json.py --profile "$PROFILE" "$@"

echo "4) Export Markdown (Quartz) -> $QUARTZ_CONTENT ..."
if [ -d "$QUARTZ_DIR" ]; then
    python3 web/export_markdown.py --profile "$PROFILE" --out "$QUARTZ_CONTENT" "$@"
else
    echo "   ⚠️  $QUARTZ_DIR introuvable -- Quartz 5 n'est pas encore cloné/configuré (sibling attendu : $QUARTZ_DIR)."
    echo "      Voir DEPLOY_RASPBERRY.md. Export sauté."
fi

echo "4bis) Injection des liens de sujets (data/graph/sujets.yaml) ..."
if [ -d "$QUARTZ_CONTENT" ]; then
    python3 web/build_subject_links.py --quartz-content "$QUARTZ_CONTENT"
else
    echo "   ⚠️  $QUARTZ_CONTENT introuvable -- injection sautée."
fi

echo "5) Notebooks interactifs ..."
python3 notebooks/build_notebooks.py --profile "$PROFILE" "$@"

echo "6) QCM (QR code) ..."
python3 web/build_qcm_artifact.py

if [ -f "$QUARTZ_DIR/package.json" ]; then
    echo "7) Build Quartz ..."
    (cd "$QUARTZ_DIR" && npx quartz build)
else
    echo "7) Quartz 5 introuvable dans $QUARTZ_DIR -- build sauté (voir DEPLOY_RASPBERRY.md)."
fi

echo "✅ Profil '$PROFILE' publié."
