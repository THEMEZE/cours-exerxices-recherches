#!/usr/bin/env python3
"""
Lit data/graph/sujets.yaml et injecte, dans chaque page Quartz correspondant
à un `quartz_path` déclaré, une section "## 🔗 Sujets liés" listant :
  - le sujet PARENT (s'il y en a un)
  - les SOUS-SUJETS (enfants)
  - les sujets ASSOCIÉS (triés par |poids| décroissant)

Fonctionne aussi bien sur les pages générées par CoursOndes (ex:
Quartz5/content/physique/ipsa-ondes/index.md) que sur tes notes personnelles
écrites à la main (ex: Quartz5/content/physique/theorie-m/index.md) : dans
les deux cas, l'injection est faite dans un bloc délimité et idempotent --
relancer le script ne duplique jamais rien, et ton contenu écrit autour du
bloc n'est JAMAIS touché.

    <!-- SUJETS-LIES:BEGIN (généré par web/build_subject_links.py, ne pas éditer) -->
    ## 🔗 Sujets liés
    ...
    <!-- SUJETS-LIES:END -->

Usage :
    python3 web/build_subject_links.py --quartz-content ~/Quartz5/content
    python3 web/build_subject_links.py --quartz-content ~/Quartz5/content --seuil 0.3
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_data import load_sujets_graph, liens_pour_sujet  # noqa: E402

BEGIN = "<!-- SUJETS-LIES:BEGIN (généré par web/build_subject_links.py, ne pas éditer) -->"
END = "<!-- SUJETS-LIES:END -->"
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)


def poids_badge(poids: float) -> str:
    """Représentation visuelle simple de la force du lien (texte, pas
    d'image -- Quartz n'a pas de rendu de graphe pondéré natif, voir
    README_MATIERES.md pour la discussion sur les limites)."""
    n = max(1, min(5, round(abs(poids) * 5)))
    filled = "●" * n
    empty = "○" * (5 - n)
    sign = "" if poids >= 0 else " (opposé/à distinguer)"
    return f"{filled}{empty}{sign}"


def build_section_for_page(sujet_ids: list, sujets: dict, liens: list, seuil: float) -> str:
    """Construit UNE section combinée pour une page Quartz qui peut
    correspondre à PLUSIEURS sujets à la fois (ex: un TD qui couvre 3
    sujets du programme sur une seule page) -- fusionne parent/enfants/
    associés de tous les sujets, déduplique, et exclut les liens vers un
    autre sujet qui pointe vers CETTE MÊME page (ça n'aurait aucun sens
    d'afficher 'voir aussi -> soi-même')."""
    self_ids = set(sujet_ids)
    seen_parent, seen_enfant, seen_associe = {}, {}, {}

    for sujet_id in sujet_ids:
        parent, enfants, associes = liens_pour_sujet(sujet_id, liens, seuil)
        for lien in parent:
            if lien["de"] in self_ids:
                continue
            seen_parent[lien["de"]] = lien
        for lien in enfants:
            if lien["a"] in self_ids:
                continue
            seen_enfant[lien["a"]] = lien
        for lien in associes:
            if lien["autre"] in self_ids:
                continue
            prev = seen_associe.get(lien["autre"])
            if not prev or abs(lien["poids"]) > abs(prev["poids"]):
                seen_associe[lien["autre"]] = lien

    if not (seen_parent or seen_enfant or seen_associe):
        return ""

    parts = [BEGIN, "", "## 🔗 Sujets liés", ""]

    if seen_parent:
        for sujet_id, lien in seen_parent.items():
            other = sujets.get(sujet_id)
            if other:
                parts.append(f"**Sujet parent :** [[{other['quartz_path']}|{other['nom']}]]")
        parts.append("")

    if seen_enfant:
        parts.append("**Sous-sujets :**")
        for sujet_id, lien in seen_enfant.items():
            other = sujets.get(sujet_id)
            if other:
                parts.append(f"- [[{other['quartz_path']}|{other['nom']}]]")
        parts.append("")

    if seen_associe:
        parts.append("**Voir aussi :**")
        for sujet_id, lien in sorted(seen_associe.items(), key=lambda kv: -abs(kv[1]["poids"])):
            other = sujets.get(sujet_id)
            if not other:
                continue
            note = f" — *{lien['note']}*" if lien.get("note") else ""
            parts.append(f"- {poids_badge(lien['poids'])} [[{other['quartz_path']}|{other['nom']}]]{note}")
        parts.append("")

    parts.append(END)
    return "\n".join(parts)


def inject_into_file(md_path: Path, section: str):
    if not md_path.exists():
        print(f"   ⚠️  page introuvable, section non injectée : {md_path}")
        return False
    text = md_path.read_text(encoding="utf-8")
    if BLOCK_RE.search(text):
        new_text = BLOCK_RE.sub(section, text)
    else:
        sep = "\n\n" if not text.endswith("\n\n") else ""
        new_text = text.rstrip("\n") + "\n" + sep + section + "\n"
    if new_text != text:
        md_path.write_text(new_text, encoding="utf-8")
        return True
    return False


def resolve_page_path(quartz_content: Path, quartz_path: str) -> Path:
    """`quartz_path` (ex: 'physique/ipsa-ondes') peut pointer soit vers
    <quartz_path>.md soit vers <quartz_path>/index.md -- on essaie les deux,
    en préférant index.md s'il existe déjà (page de section)."""
    as_index = quartz_content / quartz_path / "index.md"
    as_file = quartz_content / f"{quartz_path}.md"
    if as_index.exists():
        return as_index
    if as_file.exists():
        return as_file
    return as_index  # défaut : on suppose une page de section


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quartz-content", required=True, help="dossier content/ de Quartz")
    p.add_argument("--seuil", type=float, default=0.0,
                    help="poids minimal (valeur absolue) pour afficher un lien associé (défaut: 0, tout afficher)")
    args = p.parse_args()

    quartz_content = Path(args.quartz_content).expanduser()
    sujets, liens = load_sujets_graph()

    if not sujets:
        print("Aucun sujet trouvé dans data/graph/sujets.yaml")
        return

    print(f"-- Injection des liens de sujets dans {quartz_content}")

    pages = {}  # quartz_path -> [sujet_id, ...]
    for sujet_id, sujet in sujets.items():
        pages.setdefault(sujet["quartz_path"], []).append(sujet_id)

    n_touched = 0
    for quartz_path, sujet_ids in pages.items():
        section = build_section_for_page(sujet_ids, sujets, liens, args.seuil)
        if not section:
            continue
        page = resolve_page_path(quartz_content, quartz_path)
        changed = inject_into_file(page, section)
        marker = "✏️  mis à jour" if changed else "-- déjà à jour"
        print(f"   {marker} : {page.relative_to(quartz_content) if page.exists() else page} "
              f"(sujets : {', '.join(sujet_ids)})")
        n_touched += 1 if changed else 0

    print(f"-- {n_touched} page(s) modifiée(s) sur {len(pages)} page(s) concernée(s) ({len(sujets)} sujet(s) déclarés)")


if __name__ == "__main__":
    main()
