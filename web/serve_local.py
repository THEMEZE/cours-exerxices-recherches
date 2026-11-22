#!/usr/bin/env python3
"""
Serveur LOCAL qui imite nginx (deploy/nginx-cours.conf) pour tout voir sur ton Mac :

    /                  site Quartz         (../Quartz5/public, après `npx quartz build`)
    /pdfs/             PDF publiés         (build/public/pdfs/)
    /qcm/<matiere>/    appli QCM           (build/public/qcm/)
    /figures/          figures SVG         (web/public/figures/)
    /animations/       GIF/animations      (animations/outputs/)
    /graph.json        graphe des sujets   (build/public/graph.json)
    /api/...           stockage des QCM    (web/server/app.py, base SQLite locale)

Usage :
    python3 web/serve_local.py                 # http://127.0.0.1:8091
    python3 web/serve_local.py --port 9000 --quartz-public ../Quartz5/public

Écoute uniquement sur 127.0.0.1 (pas accessible depuis le réseau). Pour montrer
le QCM à un téléphone, il faut le Pi (ou --host 0.0.0.0, à tes risques).
"""
import argparse
import sys
from pathlib import Path

from flask import abort, send_from_directory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from web.server import app as appmod  # noqa: E402

app = appmod.app


def make_routes(quartz_public: Path):
    static = {
        "pdfs": ROOT / "build" / "public" / "pdfs",
        "figures": ROOT / "web" / "public" / "figures",
        "animations": ROOT / "animations" / "outputs",
    }

    def serve_static(kind, filename):
        base = static[kind]
        if not base.is_dir():
            abort(404)
        if filename == "" and (base / "index.html").exists():
            filename = "index.html"
        return send_from_directory(base, filename)          # refuse les chemins qui sortent de base

    for kind in static:
        app.add_url_rule(f"/{kind}/", endpoint=f"{kind}_index", defaults={"filename": ""},
                         view_func=lambda filename, kind=kind: serve_static(kind, filename))
        app.add_url_rule(f"/{kind}/<path:filename>", endpoint=f"{kind}_file",
                         view_func=lambda filename, kind=kind: serve_static(kind, filename))

    @app.route("/graph.json")
    def graph_json():
        return send_from_directory(ROOT / "build" / "public", "graph.json")

    def quartz(path=""):
        # même logique que « try_files $uri $uri/ $uri.html =404 » de nginx
        if not quartz_public.is_dir():
            return (f"Quartz pas encore construit : {quartz_public} introuvable.<br>"
                    f"<code>cd {quartz_public.parent} &amp;&amp; npm install &amp;&amp; npx quartz build</code>"), 404
        path = path.strip("/")
        for cand in ([path, f"{path}/index.html", f"{path}.html"] if path else ["index.html"]):
            f = (quartz_public / cand).resolve()
            if quartz_public.resolve() in f.parents or f == quartz_public.resolve():
                if f.is_file():
                    return send_from_directory(quartz_public, cand)
        if (quartz_public / "404.html").exists():
            return send_from_directory(quartz_public, "404.html"), 404
        abort(404)

    # L'ancienne route "/" de app.py redirigeait vers /qcm/ : on la remplace par Quartz.
    app.view_functions["root"] = quartz
    app.add_url_rule("/<path:path>", endpoint="quartz_page", view_func=quartz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--quartz-public", default=str(ROOT.parent / "Quartz5" / "public"))
    args = ap.parse_args()

    qp = Path(args.quartz_public).expanduser().resolve()
    make_routes(qp)
    appmod.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Site local : http://{args.host}:{args.port}/")
    print(f"  Quartz   : {qp} {'(ok)' if qp.is_dir() else '(à construire : npx quartz build)'}")
    print(f"  QCM      : http://{args.host}:{args.port}/qcm/   PDF : http://{args.host}:{args.port}/pdfs/")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
