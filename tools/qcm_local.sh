#!/usr/bin/env bash
# Teste les QCM EN LOCAL (sans Raspberry) : construit les pages QCM, lance le serveur sur ton ordinateur.
#
#   ./tools/qcm_local.sh                       # http://127.0.0.1:5000/qcm/<matiere>/
#   ./tools/qcm_local.sh physique-ondes-ipsa   # affiche directement l'adresse de cette matière
#   HOST=0.0.0.0 ./tools/qcm_local.sh          # joignable depuis un téléphone du même Wi-Fi (http://<IP du Mac>:5000/...)
#   TOKEN=monjeton PORT=5001 ./tools/qcm_local.sh
#   PYTHON=/chemin/vers/python ./tools/qcm_local.sh      # choisir le Python (par défaut : python3)
#
# Élève : l'adresse ci-dessus.  Enseignant : bouton « mode » de la page, puis le jeton affiché ci-dessous.
# Les réponses vont dans web/server/qcm_data.sqlite3 (ignoré par git) : `python3 tools/qcm_stats.py` les lit.
# Modifier un fichier qcm/*.yaml est pris en compte tout seul (recharger la page) ; pour un changement de
# THÈME ou de gabarit, relance ce script. Figures / animations : voir GUIDE_EVOLUTIONS.md §9.
set -euo pipefail
cd "$(dirname "$0")/.."

# --- Dépendances : on utilise TOUJOURS « python3 -m pip » (le même Python que ce script). Un simple « pip »
#     peut pointer vers un autre Python (ex. Anaconda alors qu'un .venv est actif) : le module s'installe
#     « ailleurs » et reste introuvable ici -- c'est l'erreur « No module named ... ».
PY="${PYTHON:-python3}"
echo "Python utilisé : $("$PY" -c 'import sys; print(sys.executable)')"
missing="$("$PY" - <<'PYEOF'
import importlib.util
need = {"flask": "flask", "yaml": "pyyaml", "jinja2": "jinja2"}
print(" ".join(pkg for mod, pkg in need.items() if importlib.util.find_spec(mod) is None))
PYEOF
)"
if [ -n "$missing" ]; then
  echo "⚠️  Modules manquants : $missing"
  r=""; read -r -p "Les installer maintenant avec « $PY -m pip install $missing » ? [O/n] " r || r="n"
  case "${r:-O}" in
    [Oo]*|[Yy]*) "$PY" -m pip install $missing ;;
    *) echo "→ installe-les :  $PY -m pip install $missing"; exit 1 ;;
  esac
fi
if ! "$PY" -c 'import segno' 2>/dev/null; then
  echo "ℹ️  « segno » n'est pas installé : le test QCM marche, seuls les QR codes des pages Quartz manquent."
  echo "    (pour les avoir :  $PY -m pip install segno)"
fi

export QCM_TEACHER_TOKEN="${TOKEN:-test}"
export HOST="${HOST:-127.0.0.1}" PORT="${PORT:-5000}"

echo "1) Contrôle des questions ..."
"$PY" tools/qcm.py check || { echo "   ❌ corrige les erreurs ci-dessus (les questions invalides sont ignorées)"; }

echo "2) Construction des pages QCM ..."
"$PY" web/build_qcm_artifact.py
for f in build/output/qcm_app_*.html; do
  [ -e "$f" ] || continue
  m="${f#build/output/qcm_app_}"; m="${m%.html}"
  mkdir -p "build/public/qcm/$m" && cp "$f" "build/public/qcm/$m/index.html"
  echo "   élève : http://127.0.0.1:$PORT/qcm/$m/"
done

echo
echo "3) Serveur (Ctrl+C pour arrêter)  — jeton enseignant : $QCM_TEACHER_TOKEN"
[ "$HOST" = "0.0.0.0" ] && echo "   (réseau local ouvert : téléphone = http://<adresse IP de cet ordinateur>:$PORT/qcm/<matiere>/)"
exec "$PY" web/server/app.py
