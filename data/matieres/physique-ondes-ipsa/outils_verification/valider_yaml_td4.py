#!/usr/bin/env python3
"""Validation structurelle des YAML TD4 contre le schéma observé dans les fichiers existants (TD1-TD3).
Usage : valider_yaml_td4.py <racine_projet_existant> <dossier_td4>"""
import sys,glob,os,yaml,collections
ref,new=sys.argv[1],sys.argv[2]
def load(f): return yaml.safe_load(open(f,encoding='utf-8'))
def uni(files):
    top=collections.Counter(); q=collections.Counter(); lvl=set(); items={}
    for f in files:
        d=load(f); top.update(d.keys())
        for qq in d.get('questions',[]) or []: q.update(qq.keys())
        for it in d.get('aller_plus_loin',[]) or []:
            if isinstance(it,dict) and 'niveau' in it: lvl.add(it['niveau'])
    return top,q,lvl
exs=[f for f in glob.glob(ref+'/td/*/ex*.yaml') if 'copie' not in f]
top_r,q_r,lvl_r=uni(exs)
newex=sorted(glob.glob(new+'/ex*.yaml')); top_n,q_n,lvl_n=uni(newex)
err=[];warn=[]
for k in top_n:
    if k not in top_r: err.append(f"clé de premier niveau inconnue du projet existant : {k}")
for k in q_n:
    if k not in q_r: err.append(f"clé de question inconnue du projet existant : {k}")
for l in lvl_n:
    if l not in lvl_r: warn.append(f"niveau aller_plus_loin '{l}' absent des fichiers existants (existants : {sorted(lvl_r)})")
meta=load(new+'/_meta.yaml'); mref=[load(f) for f in glob.glob(ref+'/td/*/_meta.yaml') if 'copie' not in f]
mk=set().union(*[set(m) for m in mref])
for k in meta:
    if k not in mk: err.append(f"_meta : clé inconnue {k}")
base=[os.path.basename(f)[:-5] for f in newex]
if meta['exercices_ordre']!=base: err.append(f"exercices_ordre {meta['exercices_ordre']} != fichiers {base}")
for f in newex:
    d=load(f); b=os.path.basename(f)[:-5]
    if d['td']!=meta['id']: err.append(f"{b}: td != _meta.id")
    n=b.split('_')[0]
    if d['id']!=meta['id']+'_'+n: err.append(f"{b}: id inattendu {d['id']}")
    ids=[q['id'] for q in d['questions']]
    if ids!=[f'q{i+1}' for i in range(len(ids))]: err.append(f"{b}: ids de questions non séquentiels {ids}")
    for q in d['questions']:
        for fld in ('enonce','solution'):
            if fld not in q: err.append(f"{b}/{q['id']}: champ {fld} manquant")
        for fld in ('coup_de_pouce','correction','solution'):
            v=q.get(fld)
            if v is None: continue
            if isinstance(v,list):
                for it in v:
                    if not (isinstance(it,dict) and set(it)=={'titre','texte'}): err.append(f"{b}/{q['id']}/{fld}: item mal formé {list(it) if isinstance(it,dict) else type(it)}")
    FMT={'prerequis':{'titre','texte'},'objectifs_pedagogiques_etudiants':{'titre','texte'},'objectifs_pedagogiques_enseignants':{'titre','texte'},
         'remarques_pedagogiques_ecueils_classiques':{'titre','texte'},'remarques_pedagogiques_conseils_animation':{'titre','texte'},
         'bilan':{'titre','texte'},'outils_mathematiques':{'titre','texte'},'liens_autres_disciplines':{'discipline','texte'},
         'aller_plus_loin':{'niveau','titre','texte'},'accroche_point_cours_essentiel':{'titre','duree_introduction','question_d_accroche','texte'}}
    for sec,keys in FMT.items():
        for it in d.get(sec,[]) or []:
            if not (isinstance(it,dict) and set(it)==keys): err.append(f"{b}/{sec}: item mal formé {sorted(it) if isinstance(it,dict) else type(it).__name__}")
    for fg in d.get('figure',[]) or []:
        if not {'ref','legende','label'}<=set(fg): err.append(f"{b}/figure: clés manquantes {sorted(fg)}")
    for c in d.get('cours_rattache',[]):
        if not isinstance(c,str): err.append(f"{b}: cours_rattache non str")
    if not isinstance(d['facultatif'],bool): err.append(f"{b}: facultatif non booléen")
print(f"Fichiers exercices contrôlés : {len(newex)} ; référence : {len(exs)} fichiers existants")
for w in warn: print("AVERTISSEMENT :",w)
for e in err: print("ERREUR :",e)
print("RESULTAT :", "OK" if not err else f"{len(err)} erreur(s)")
sys.exit(1 if err else 0)
