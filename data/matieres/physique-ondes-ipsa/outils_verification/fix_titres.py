"""Convertit en guillemets simples les valeurs 'titre:'/'intitule:' entre guillemets doubles contenant un backslash LaTeX non doublé."""
import re,sys
for p in sys.argv[1:]:
    out=[]
    for ln in open(p,encoding='utf-8'):
        m=re.match(r'^(\s*(?:- )?(?:titre|intitule|legende|label|niveau):\s*)"(.*)"\s*$',ln.rstrip('\n'))
        if m and '\\' in m.group(2) and '\\\\' not in m.group(2):
            body=m.group(2).replace("'","''")
            ln=f"{m.group(1)}'{body}'\n"
        out.append(ln)
    open(p,'w',encoding='utf-8').writelines(out)
