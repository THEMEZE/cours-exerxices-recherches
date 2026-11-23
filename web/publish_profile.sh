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
#   ./web/publish_profile.sh auto                 # profil de chaque cours/TP/TD d'après build/config.yaml (publication:)
#   ./web/publish_profile.sh <profil> [--matiere <matiere_slug>]   # force UN profil partout
#       profils : avant_seance | pendant_seance_avec_indices | corrige_resultats_seuls | corrige_complet
#                 all_eleve (tout pour l'élève, SANS contenu enseignant) | all_fast (énoncé + coup de pouce + corrigé + solution, rien d'autre)
#                 all_prof (TOUT, fiches comprises : site privé !)
#       ou un ÉTAT de chapitre : a_venir | en_cours | termine (traduits en profil, voir config.yaml > publication > etats)
#   CREATE_MISSING=1 ./web/publish_profile.sh <profil>   # crée aussi les pages-sujets absentes de Quartz
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# Sans argument (ou si le 1er argument est une option --xxx) : mode « auto ».
if [ -z "$1" ] || [[ "$1" == --* ]]; then
    PROFILE="auto"
else
    PROFILE="$1"
    shift
fi

# « auto » = profil de CHAQUE document d'après publication: dans build/config.yaml ;
# tout autre nom = ce profil est forcé pour tous les documents.
if ! python3 - "$PROFILE" <<'PYCHECK'
import sys, yaml
sys.path.insert(0, ".")
import common_data as cd
p = yaml.safe_load(open("web/visibility_profiles.yaml"))["profiles"]
name = sys.argv[1]
if name != "auto" and cd.expand_profile(name) not in p:
    print(f"Profil inconnu : {name}")
    print("Usage: ./web/publish_profile.sh [auto | <profil> | <état>] [--matiere <matiere_slug>]")
    print("  - auto   (profil de chaque document, d'après build/config.yaml)")
    for n in p:
        print(f"  - {n}")
    for e, pr in cd.etats().items():
        print(f"  - {e}  (état de chapitre -> {pr})")
    sys.exit(1)
PYCHECK
then
    exit 1
fi

QUARTZ_CONTENT="${QUARTZ_CONTENT:-$ROOT/../Quartz5/content}"
QUARTZ_DIR="$(dirname "$QUARTZ_CONTENT")"

# Un ÉTAT de chapitre (a_venir / en_cours / termine...) est traduit en son profil (config.yaml > publication > etats).
PROFILE="$(python3 -c "import sys; sys.path.insert(0, '.'); import common_data as cd; print(cd.expand_profile(sys.argv[1]))" "$PROFILE")"
echo "🔄 Profil actif -> $PROFILE"
echo "$PROFILE" > "$ROOT/web/.current_profile"

echo "0) Contrôle des réglages (fichiers rattachés, liens QCM, rubriques, types, profils) ..."
python3 tools/check_evolutions.py || echo "   ⚠️  réglages à corriger (voir ci-dessus) -- la publication continue."

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
    python3 web/build_subject_links.py --quartz-content "$QUARTZ_CONTENT" ${CREATE_MISSING:+--create-missing}
else
    echo "   ⚠️  $QUARTZ_CONTENT introuvable -- injection sautée."
fi

echo "5) Notebooks interactifs ..."
python3 notebooks/build_notebooks.py --profile "$PROFILE" "$@"

echo "6) QCM (QR code) ..."
python3 web/build_qcm_artifact.py

echo "6bis) Hébergement : PDF faits/défaits (profil $PROFILE), pages QCM, graph.json ..."
python3 web/publish_hosting.py --profile "$PROFILE"

if [ -d "$QUARTZ_CONTENT" ]; then
    echo "6ter) Médias (figures, animations, PDF publiés) -> content/ de Quartz ..."
    python3 web/sync_quartz_assets.py --quartz-content "$QUARTZ_CONTENT"
fi

if [ -f "$QUARTZ_DIR/package.json" ]; then
    echo "7) Build Quartz ..."
    (cd "$QUARTZ_DIR" && npx quartz build)
else
    echo "7) Quartz 5 introuvable dans $QUARTZ_DIR -- build sauté (voir DEPLOY_RASPBERRY.md)."
fi

if [ -d "$QUARTZ_CONTENT" ]; then
    echo "8) Vérification des liens (wikilinks du graphe, PDF, QCM) ..."
    python3 tools/check_quartz_links.py --quartz-content "$QUARTZ_CONTENT" || echo "   ⚠️  liens à corriger (voir ci-dessus) -- le site est publié quand même."
fi

echo "✅ Profil '$PROFILE' publié."
