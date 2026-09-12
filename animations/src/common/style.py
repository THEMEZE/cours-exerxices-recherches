"""Style partagé pour toutes les animations (cohérence visuelle cours <-> Instagram)."""
import matplotlib.pyplot as plt

COLORS = {
    "corde": "#1565C0",       # bleu
    "onde_reflechie": "#B71C1C",
    "onde_incidente": "#0F4C3A",
    "accent": "#8C0000",
    "fond": "#FFFFFF",
    "grille": "#CCCCCC",
}


def apply_style(use_latex: bool = True):
    """A appeler en tout début de script. use_latex=False si LaTeX indisponible
    (ex : génération rapide sur une machine sans TeXLive, ou export web)."""
    plt.rcParams.update({
        "text.usetex": use_latex,
        "font.family": "serif",
        "figure.figsize": (6, 3.5),
        "figure.dpi": 150,
        "axes.grid": True,
        "grid.color": COLORS["grille"],
        "grid.alpha": 0.4,
        "axes.edgecolor": "#333333",
    })
    if use_latex:
        plt.rcParams["text.latex.preamble"] = r"\usepackage{amsmath}"
