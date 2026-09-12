"""
Petite bibliothèque de logos SVG prédéfinis pour l'appli QCM (voir
_matiere.yaml -> theme.logo). Chaque logo est un cercle de couleur
(couleur "happy" du thème, cf. build_qcm_artifact.py) + un symbole blanc
au centre -- cohérent avec le style d'origine (vague pour les ondes).

Pour un logo totalement personnalisé, mets `logo: custom` dans le thème
et ajoute `logo_svg_path:` pointant vers un fichier .svg (voir
web/README_QCM.md) -- son contenu sera injecté tel quel à la place.
"""

LOGOS = {
    "onde": (
        '<path d="M8 26c4-8 8 8 12 0s8-8 12 0 8-8 8-8" '
        'stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/>'
    ),
    "sigma": (
        '<text x="24" y="33" font-size="26" font-weight="700" '
        'text-anchor="middle" fill="#fff" font-family="Georgia, serif">&#931;</text>'
    ),
    "atome": (
        '<ellipse cx="24" cy="24" rx="16" ry="6" stroke="#fff" stroke-width="2" fill="none"/>'
        '<ellipse cx="24" cy="24" rx="16" ry="6" stroke="#fff" stroke-width="2" fill="none" '
        'transform="rotate(60 24 24)"/>'
        '<ellipse cx="24" cy="24" rx="16" ry="6" stroke="#fff" stroke-width="2" fill="none" '
        'transform="rotate(120 24 24)"/>'
        '<circle cx="24" cy="24" r="3" fill="#fff"/>'
    ),
    "fiole": (
        '<path d="M19 8h10 M20 8v10l-8 16a3 3 0 0 0 3 4h18a3 3 0 0 0 3-4l-8-16V8" '
        'stroke="#fff" stroke-width="2.5" fill="none" stroke-linejoin="round"/>'
        '<path d="M16 30h16" stroke="#fff" stroke-width="2"/>'
    ),
    "livre": (
        '<path d="M24 14c-3-3-9-3-13-1v20c4-2 10-2 13 1c3-3 9-3 13-1V13c-4-2-10-2-13 1z" '
        'stroke="#fff" stroke-width="2.2" fill="none" stroke-linejoin="round"/>'
        '<path d="M24 14v20" stroke="#fff" stroke-width="2"/>'
    ),
    "boussole": (
        '<circle cx="24" cy="24" r="15" stroke="#fff" stroke-width="2.2" fill="none"/>'
        '<path d="M29 19l-3 8-8 3 3-8z" fill="#fff"/>'
    ),
    "pi": (
        '<text x="24" y="33" font-size="26" font-weight="700" '
        'text-anchor="middle" fill="#fff" font-family="Georgia, serif">&#960;</text>'
    ),
}

DEFAULT_LOGO = "onde"


def logo_inner_svg(name: str) -> str:
    return LOGOS.get(name, LOGOS[DEFAULT_LOGO])
