#!/usr/bin/env python3
"""
Anime les modes propres d'une corde fixée aux deux extrémités (ondes
stationnaires). Réutilise le moteur de rendu de anim_corde_onde.py.

Usage :
    python3 animations/src/anim_corde_stationnaire.py --ref anim_corde_stationnaire \
        --N-max 4 --highlight-nodes --formats gif frames_pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anim_corde_onde import (  # noqa: E402
    build_frames_modes_propres, render_frames, assemble_gif, assemble_mp4,
    OUT_ROOT,
)
from common.style import apply_style  # noqa: E402
import argparse  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ref", required=True)
    p.add_argument("--mode", default="modes_propres", help="ignoré (compat avec le schéma générique)")
    p.add_argument("--N-max", type=int, default=4, dest="n_max")
    p.add_argument("--highlight-nodes", action="store_true")
    p.add_argument("--n-frames", type=int, default=40)
    p.add_argument("--formats", nargs="+", default=["gif"], choices=["gif", "mp4", "frames_pdf"])
    p.add_argument("--no-latex", action="store_true")
    args = p.parse_args()

    apply_style(use_latex=not args.no_latex)

    outdir = OUT_ROOT / args.ref
    outdir.mkdir(parents=True, exist_ok=True)

    frames = build_frames_modes_propres(args.n_max, n_frames=args.n_frames,
                                         highlight_nodes=args.highlight_nodes)
    png_paths = render_frames(frames, outdir, "modes_propres")

    if "gif" in args.formats:
        assemble_gif(png_paths, outdir, args.ref)
        print(f"   -> {outdir / 'animation.gif'}")
    if "mp4" in args.formats:
        assemble_mp4(outdir, args.ref)
    if "frames_pdf" in args.formats:
        print(f"   -> frames PDF dans {outdir / 'frames'}")


if __name__ == "__main__":
    main()
