#!/bin/bash
set -e

echo "📥 Synchronisation..."

git add .

if git diff --cached --quiet
then
    echo "Aucun changement"
    exit 0
fi

MESSAGE="${1:-Mise a jour cours ondes}"

git commit -m "$MESSAGE"

git pull --rebase origin main

git push origin main

echo "✅ Envoyé sur GitHub -- pense à lancer tools/Raspberry/update_code.sh sur le Raspberry"
