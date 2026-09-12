#!/usr/bin/env python3
"""
Anime une onde sur une corde (progressive ou stationnaire / modes propres).

Sorties, dans animations/outputs/<ref>/ :
    frames/frame_0000.pdf, frame_0001.pdf, ...   -> pour \\animategraphics (package animate)
    <ref>.gif                                     -> pour le web / Instagram
    <ref>.mp4                                     -> si ffmpeg est disponible

Usage :
    python3 animations/src/anim_corde_onde.py --ref anim_corde_onde \
        --mode onde_progressive --lam 1.0 --T 1.0 --xmax 4 \
        --formats gif frames_pdf

    python3 animations/src/anim_corde_onde.py --ref anim_corde_stationnaire \
        --mode modes_propres --N-max 4
"""
import argparse
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.style import apply_style, COLORS

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "animations" / "outputs"


def build_frames_onde_progressive(lam, T, xmax, n_frames=60):
    x = np.linspace(0, xmax, 400)
    k = 2 * np.pi / lam
    omega = 2 * np.pi / T
    frames = []
    for i in range(n_frames):
        t = i * T / n_frames
        y = np.sin(k * x - omega * t)
        frames.append((x, y, rf"$t = {t:.2f}$ s"))
    return frames


def build_frames_modes_propres(N_max=4, L=1.0, n_frames=60, highlight_nodes=False):
    x = np.linspace(0, L, 400)
    frames = []
    for i in range(n_frames):
        phase = 2 * np.pi * i / n_frames
        # superposition simple des 2 premiers modes pour illustrer la variété de formes
        y = 0.6 * np.sin(np.pi * x / L) * np.cos(phase) \
            + 0.3 * np.sin(2 * np.pi * x / L) * np.cos(2 * phase)
        nodes = [j * L / 1 for j in (0, 1)] if not highlight_nodes else \
                [j * L / N_max for j in range(N_max + 1)]
        frames.append((x, y, nodes, rf"$\omega t = {phase:.2f}$"))
    return frames


def render_frames(frames, outdir: Path, kind: str):
    frames_dir = outdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, frame in enumerate(frames):
        fig, ax = plt.subplots()
        if kind == "onde_progressive":
            x, y, label = frame
            ax.plot(x, y, color=COLORS["corde"], lw=2)
        else:
            x, y, nodes, label = frame
            ax.plot(x, y, color=COLORS["corde"], lw=2)
            for xn in nodes:
                ax.plot(xn, 0, "o", color=COLORS["accent"], ms=5)
        ax.set_ylim(-1.2, 1.2)
        ax.set_xlabel("$x$")
        ax.set_ylabel("$y$")
        ax.set_title(label)
        fig.tight_layout()
        png_path = frames_dir / f"frame_{i:04d}.png"
        pdf_path = frames_dir / f"frame_{i:04d}.pdf"
        fig.savefig(png_path)
        fig.savefig(pdf_path)
        paths.append(png_path)
        plt.close(fig)
    return paths


def assemble_gif(png_paths, outdir: Path, ref: str, fps=20):
    from PIL import Image
    images = [Image.open(p) for p in png_paths]
    images[0].save(
        outdir / "animation.gif",
        save_all=True,
        append_images=images[1:],
        duration=int(1000 / fps),
        loop=0,
    )


def assemble_mp4(outdir: Path, ref: str, fps=20):
    if shutil.which("ffmpeg") is None:
        print("   (ffmpeg non trouvé : mp4 non généré, gif/frames_pdf suffisent)")
        return
    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(outdir / "frames" / "frame_%04d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-pix_fmt", "yuv420p", str(outdir / "animation.mp4"),
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ref", required=True, help="identifiant -> animations/outputs/<ref>/")
    p.add_argument("--mode", choices=["onde_progressive", "modes_propres"], required=True)
    p.add_argument("--lam", type=float, default=1.0)
    p.add_argument("--T", type=float, default=1.0)
    p.add_argument("--xmax", type=float, default=4.0)
    p.add_argument("--N-max", type=int, default=4, dest="n_max")
    p.add_argument("--highlight-nodes", action="store_true")
    p.add_argument("--n-frames", type=int, default=40)
    p.add_argument("--formats", nargs="+", default=["gif"], choices=["gif", "mp4", "frames_pdf"])
    p.add_argument("--no-latex", action="store_true", help="désactive text.usetex (rendu plus rapide)")
    args = p.parse_args()

    apply_style(use_latex=not args.no_latex)

    outdir = OUT_ROOT / args.ref
    outdir.mkdir(parents=True, exist_ok=True)

    if args.mode == "onde_progressive":
        frames = build_frames_onde_progressive(args.lam, args.T, args.xmax, args.n_frames)
    else:
        frames = build_frames_modes_propres(args.n_max, n_frames=args.n_frames,
                                             highlight_nodes=args.highlight_nodes)

    png_paths = render_frames(frames, outdir, args.mode)

    if "gif" in args.formats:
        assemble_gif(png_paths, outdir, args.ref)
        print(f"   -> {outdir / 'animation.gif'}")
    if "mp4" in args.formats:
        assemble_mp4(outdir, args.ref)
    if "frames_pdf" in args.formats:
        print(f"   -> frames PDF dans {outdir / 'frames'} "
              f"(à utiliser avec \\animategraphics dans le .tex)")


if __name__ == "__main__":
    main()
