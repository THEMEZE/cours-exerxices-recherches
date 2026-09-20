#!/bin/bash

# ------------------------------------------------------------ 
# Gestion des arguments 
# 
# Usage : 
# ./compile.sh -> compile tous les .tex 
# ./compile.sh file1.tex -> compile seulement file1.tex 
# ./compile.sh a.tex b.tex -> compile une liste précise 
# ------------------------------------------------------------

# ------------------------------------------------------------
# Couleurs
# ------------------------------------------------------------

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BLUE="\033[1;34m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RESET="\033[0m"

# ------------------------------------------------------------
# Compteurs
# ------------------------------------------------------------

success_count=0
warning_count=0
fail_count=0

# ------------------------------------------------------------
# Fonction formatage temps
# ------------------------------------------------------------

format_time() {
    local total_seconds=$1

    local hours=$((total_seconds / 3600))
    local minutes=$(((total_seconds % 3600) / 60))
    local seconds=$((total_seconds % 60))

    if [ $hours -gt 0 ]; then
        printf "%02dh %02dm %02ds" $hours $minutes $seconds
    else
        printf "%02dm %02ds" $minutes $seconds
    fi
}

# ------------------------------------------------------------
# Fonction formatage taille fichier
# ------------------------------------------------------------

format_size() {
    local size=$1

    if [ "$size" -ge 1073741824 ]; then
        awk "BEGIN {printf \"%.2f Go\", $size/1073741824}"
    elif [ "$size" -ge 1048576 ]; then
        awk "BEGIN {printf \"%.2f Mo\", $size/1048576}"
    elif [ "$size" -ge 1024 ]; then
        awk "BEGIN {printf \"%.2f Ko\", $size/1024}"
    else
        printf "%d o" "$size"
    fi
}

# ------------------------------------------------------------
# Temps global
# ------------------------------------------------------------

global_start=$(date +%s)

echo -e "${BLUE}🔹 Recherche et compilation des fichiers .tex...${RESET}"
echo

# ------------------------------------------------------------
# Gestion des arguments
# ------------------------------------------------------------

if [ $# -gt 0 ]; then
    texfiles="$@"
else
    texfiles=$(find . -type f -name "*.tex" \
        ! -name "._*" \
        ! -path "*/.*/*" \
        | awk '{ print length, $0 }' \
        | sort -nr \
        | cut -d" " -f2-)
fi

# ------------------------------------------------------------
# Vérification
# ------------------------------------------------------------

if [ -z "$texfiles" ]; then
    echo -e "${RED}❌ Aucun fichier .tex trouvé.${RESET}"
    exit 1
fi

# ------------------------------------------------------------
# Compilation
# ------------------------------------------------------------

for texfile in $texfiles; do

    if [ ! -f "$texfile" ]; then
        echo -e "❌ ${RED}Fichier introuvable${RESET} : $texfile"
        ((fail_count++))
        echo
        continue
    fi

    basename=$(basename "$texfile")

    if [[ "$basename" == .* ]]; then
        continue
    fi

    folder=$(dirname "$texfile")

    pdf_file="${texfile%.tex}.pdf"

    echo -e "${CYAN}🔄 Compilation de${RESET} $texfile"

    # --------------------------------------------------------
    # Temps début fichier
    # --------------------------------------------------------

    start_time=$(date +%s)

    log_file=$(mktemp)

    # --------------------------------------------------------
    # Affichage live du chrono
    # --------------------------------------------------------

    (
        while true; do
            now=$(date +%s)
            elapsed=$((now - start_time))

            printf "\r⏱️  Temps compilation : %s" "$(format_time $elapsed)"

            sleep 1
        done
    ) &

    timer_pid=$!

    # --------------------------------------------------------
    # Double compilation
    # --------------------------------------------------------

    pdflatex \
        -interaction=nonstopmode \
        -output-directory="$folder" \
        "$texfile" >"$log_file" 2>&1

    pdflatex \
        -interaction=nonstopmode \
        -output-directory="$folder" \
        "$texfile" >>"$log_file" 2>&1

    # --------------------------------------------------------
    # Stop chrono live
    # --------------------------------------------------------

    kill $timer_pid 2>/dev/null
    wait $timer_pid 2>/dev/null

    end_time=$(date +%s)
    duration=$((end_time - start_time))

    printf "\r"

    # --------------------------------------------------------
    # Taille PDF
    # --------------------------------------------------------

    if [ -f "$pdf_file" ]; then
        pdf_size_bytes=$(stat -f%z "$pdf_file" 2>/dev/null)

        # Fallback Linux
        if [ -z "$pdf_size_bytes" ]; then
            pdf_size_bytes=$(stat -c%s "$pdf_file" 2>/dev/null)
        fi

        pdf_size=$(format_size "$pdf_size_bytes")
    else
        pdf_size="PDF non généré"
    fi

    # --------------------------------------------------------
    # Analyse log
    # --------------------------------------------------------

    if grep -q "Fatal error" "$log_file" || \
       grep -q "! LaTeX Error" "$log_file"; then

        echo -e "   ❌ ${RED}Erreur de compilation${RESET} : $basename"
        echo -e "   ⏱️  Temps : ${RED}$(format_time $duration)${RESET}"
        echo -e "   📄 Taille PDF : ${RED}$pdf_size${RESET}"

        ((fail_count++))

    elif grep -qi "warning" "$log_file"; then

        echo -e "   ⚠️  ${YELLOW}Compilation avec avertissements${RESET} : $basename"
        echo -e "   ⏱️  Temps : ${YELLOW}$(format_time $duration)${RESET}"
        echo -e "   📄 Taille PDF : ${YELLOW}$pdf_size${RESET}"

        ((warning_count++))

    else

        echo -e "   ✅ ${GREEN}Compilation réussie${RESET} : $basename"
        echo -e "   ⏱️  Temps : ${GREEN}$(format_time $duration)${RESET}"
        echo -e "   📄 Taille PDF : ${GREEN}$pdf_size${RESET}"

        ((success_count++))
    fi

    rm -f "$log_file"

    echo
done

# ------------------------------------------------------------
# Temps global
# ------------------------------------------------------------

global_end=$(date +%s)
global_duration=$((global_end - global_start))

# ------------------------------------------------------------
# Résumé
# ------------------------------------------------------------

echo -e "${MAGENTA}──────────── Résumé ────────────${RESET}"

echo -e "✅ ${GREEN}Réussies : $success_count${RESET}"
echo -e "⚠️  ${YELLOW}Avec avertissements : $warning_count${RESET}"
echo -e "❌ ${RED}Échouées : $fail_count${RESET}"

echo
echo -e "🏁 ${BLUE}Temps total : $(format_time $global_duration)${RESET}"

echo -e "${MAGENTA}────────────────────────────────${RESET}"