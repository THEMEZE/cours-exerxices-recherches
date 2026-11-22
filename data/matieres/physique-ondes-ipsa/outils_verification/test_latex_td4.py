#!/usr/bin/env python3
"""Compile chaque champ texte des YAML TD4 (pdflatex, préambule standard amsmath/enumitem) pour détecter les erreurs LaTeX.
Usage : test_latex_td4.py <dossier_td4> <dossier_travail>"""
import sys,glob,os,yaml,subprocess,re
src,work=sys.argv[1],sys.argv[2]; os.makedirs(work,exist_ok=True)
PRE=r"""\documentclass{article}\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,enumitem,mathtools}\usepackage[a4paper,margin=1cm]{geometry}\setlength{\parindent}{0pt}
\begin{document}
"""
def strings(o,path=''):
    if isinstance(o,str): yield path,o
    elif isinstance(o,dict):
        for k,v in o.items():
            if k in("exercices_ordre","niveau_public","id",'td','ref','label','width','duree_estimee','type_exercice'): continue
            yield from strings(v,path+'/'+str(k))
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from strings(v,path+f'[{i}]')
tot=0;bad=0
for f in sorted(glob.glob(src+'/*.yaml')):
    d=yaml.safe_load(open(f,encoding='utf-8')); b=os.path.basename(f)[:-5]
    body=[];idx=[]
    for p,t in strings(d):
        if p.startswith('/cours_rattache'): continue
        n=len(idx); idx.append(p)
        body.append(f"\\message{{<<{n}>>}}\n\\begin{{minipage}}{{\\linewidth}}\n{t}\n\\end{{minipage}}\\par\n")
    tex=work+'/'+b+'.tex'; open(tex,'w',encoding='utf-8').write(PRE+''.join(body)+'\\end{document}\n')
    r=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','-output-directory',work,tex],capture_output=True,text=True,cwd=work)
    log=r.stdout; tot+=len(idx)
    # approche tolérante : relancer sans halt pour lister toutes les erreurs
    r=subprocess.run(['pdflatex','-interaction=nonstopmode','-output-directory',work,tex],capture_output=True,text=True,cwd=work); log=r.stdout
    cur=None;errs=[]
    for line in log.splitlines():
        m=re.search(r'<<(\d+)>>',line)
        if m: cur=int(m.group(1))
        if line.startswith('!'): errs.append((idx[cur] if cur is not None else '?',line))
    bad+=len(errs)
    print(f"{b}: {len(idx)} champs, {len(errs)} erreur(s) LaTeX")
    for p,l in errs[:10]: print("   ",p,l)
print("TOTAL champs",tot,"erreurs",bad); sys.exit(1 if bad else 0)
