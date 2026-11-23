# Modifications — hébergement PDF / Quartz / QCM

## Le flux, en une image

```
data/**/*.yaml  ──►  build/build.py ──► build/output/*.pdf ─┐
 (la « base »)            │ pdf_status : fait / périmé / à faire │
                          │                                      ▼
                          ├─► web/export_markdown.py ──► Quartz5/content/**.md  (+ wikilinks du graphe)
                          └─► web/build_qcm_artifact.py ► build/output/qcm_app_<matiere>.html
                                                         │
                         web/publish_hosting.py  ◄───────┘
                              ▼
                       build/public/{pdfs,qcm,graph.json}   ◄── nginx
```

## Ce que fait maintenant le code

**PDF — « fait / défait »** (`build/pdf_status.py`, nouveau)
- Compare `config.yaml` (ce qui est demandé), les sources YAML + templates (empreinte) et `build/output/` (ce qui existe).
- États : `ok`, `perime` (sources changées), `manquant` (à faire), `present_sans_empreinte` (PDF d'avant ce système), `cible_cassee`, + PDF orphelins.
- `python3 build/pdf_status.py` : tableau. `python3 build/build.py --stale` : ne recompile que le manquant/périmé.
- `manifest.json` est reconstruit d'après le disque (avant : 11 entrées de cibles supprimées, 7 vers des PDF absents).
- `web/publish_hosting.py` synchronise `build/public/pdfs/` : un PDF supprimé ou retiré de `config.yaml` disparaît de l'hébergement.
- **Profils** : `pdf_publies` dans `web/visibility_profiles.yaml`. En `avant_seance`, seuls les énoncés sont en ligne (avant, nginx servait tout `build/output/*.pdf`, corrigés compris). `publier: true|false` dans une cible force un PDF. Les `*_fiche` (enseignant) ne sont jamais publiés par défaut.

**Markdown Quartz** (`web/export_markdown.py`)
- Ne plantait plus sur `solution`/`correction`/`coup_de_pouce` en liste de blocs `{titre, texte}` (600+ cas), ni sur `aller_plus_loin` en liste, ni sur `figure` en liste ou `???`.
- Wikilinks avec chemin complet depuis `content/` (namespace inclus) → les liens entre matières et le graphe Quartz sont fiables.
- Chaque TD/cours pointe vers sa matière et vers ses sujets (`data/graph/sujets.yaml`) → plus d'arêtes dans le graphe.
- Liens PDF = uniquement PDF présents ET autorisés par le profil. Lien QCM = `/qcm/<matiere>/`.
- Pages « défaites » (exercice renommé/retiré) supprimées via `.coursondes-generated.json` ; tes notes manuelles ne sont jamais touchées.
- LaTeX de texte (`{\bf }`, `\textbf`, `\emph`, `enumerate`/`itemize`) converti en Markdown, formules intactes.

**Graphe** (`web/build_subject_links.py`, `web/publish_hosting.py`) : validation des liens (ids inconnus, poids, type), `--create-missing`, export `graph.json` pondéré.

**QCM HTML** : une appli par matière → `/qcm/<matiere>/` (statique via nginx), index `/qcm/`. Les clés de stockage sont préfixées par matière (sinon `current_qcm_id` et `td1_qcm_debut1` se mélangeaient entre matières).

## Corrections dans tes données

| Problème | Correction |
|---|---|
| `onip-iogs/_matiere.yaml` = copie de mécanique (id faux, `sujets: [n]`) | réécrit |
| 3 matières avec `quartz_namespace: physique/ipsa-ondes` (leurs `index.md` s'écrasaient) | namespaces distincts |
| `piscines…` et `traveaux_pratiques-ipsa` sans `_matiere.yaml` → invisibles pour Quartz/QCM | créés (+ défaut automatique si absent) |
| Dossiers « … copie » traités comme de vrais TD (doublons, « voir aussi » dupliqués) | ignorés (ou `publier: false`) |
| `td2_derivation_et_diffeérentielle` : accent en NFD (macOS) → introuvable sur le Raspberry | renommé en ASCII (+ chargement tolérant NFC/NFD) |
| `lie_a: td1_ex4` d'un QCM d'ondes pointait vers un exercice d'une autre matière | clé (matière, id) |
| 4 sujets sans page (mécanique, ONIP, grandeurs, TP) | ajoutés à `sujets.yaml` avec liens **proposés** (à ajuster) |

## Déploiement
- `update_code.sh` / `run.sh` : `build.py --stale`, et un échec LaTeX n'arrête plus la régénération du site.
- `publish_profile.sh` : étape `6bis` (hébergement) et `8` (vérif des liens).
- `nginx-cours.conf` : `/pdfs/`, `/qcm/`, `/graph.json` servis depuis `build/public/`.
- `.gitignore` : `manifest.json`, `status.json`, `build/public/`. Si `manifest.json` est déjà suivi : `git rm --cached build/output/manifest.json`.

## Outils
- `python3 tools/check_data.py` : contrôle des YAML (ids, namespaces, ordre des exercices, noms NFD, liens du graphe, QCM, cibles).
- `python3 tools/check_quartz_links.py --quartz-content ../Quartz5/content` : wikilinks cassés, PDF/QCM absents, pages orphelines.

## À faire de ton côté
1. Supprimer l'ancien dossier `data/matieres/piscines-de-sciences-et-methodologie/td/td2_derivation_et_diffe*rentielle` (version NFD) après décompression.
2. Supprimer `Quartz5/content/physique/ipsa-ondes/` une fois (il contient d'anciennes pages mélangées), puis relancer `publish_profile.sh`.
3. Recopier la nouvelle `deploy/nginx-cours.conf` sur le Pi (`update_code.sh` le fait).
4. Les 12 PDF « à faire » : `python3 build/build.py --missing`.

---

## Ajout : couleur de l'anglais et profil par cours / TP / TD

**Couleur de l'anglais** — `build/config.yaml` → `couleurs.anglais` (hex ou nom de couleur ; `anglais_web` optionnel pour le site). Les YAML gardent `{\color{blue} ...}` : `common_data.normalize_en_color` le redirige vers la couleur nommée `colorEN` (définie dans le préambule LaTeX, et en hex pour le site). Convention : « blue » = anglais.
Sur le site, chaque titre (TD, TP, cours, exercice, sections, blocs coup de pouce / aller plus loin) s'affiche en français, avec l'anglais en couleur sur une ligne dessous ; l'URL et le titre de page n'utilisent que le français (fini les `-color-blue-` dans les adresses).

**Profil par document** — `build/config.yaml` → `publication:`
```yaml
publication:
  defaut: avant_seance
  matieres:
    physique-ondes-ipsa:
      td:
        td1_corde:                       # chapitre terminé : tout montrer
          profil: corrige_complet
          exercices:
            ex3_equation_ondes: avant_seance   # (option) surcharge d'un exercice
        td2_ondes_sonores: pendant_seance_avec_indices
        td3_reflexion_transmission: avant_seance
```
- `./web/publish_profile.sh auto` applique ce bloc ; `./web/publish_profile.sh <profil>` force un profil partout.
- Le profil d'un document règle le contenu Quartz / JSON / notebooks ET les PDF en ligne (`pdf_publies`).
- `python3 tools/add_config_blocks.py` insère les deux blocs dans TON config.yaml sans toucher à tes cibles.
- `avant_seance` n'affiche plus les coups de pouce sur le site (énoncés seulement, comme décrit) ; remets `show_coup_de_pouce: true` dans `web/visibility_profiles.yaml` si tu les voulais.

---

## Ajout : types de documents, rubriques, fichiers rattachés, profils all_eleve / all_prof, liens QCM
Voir **GUIDE_EVOLUTIONS.md**. Nouveau : `web/rubriques_md.py`, `web/fichiers_joints.py`, `tools/check_evolutions.py`, `tools/qcm_stats.py`.
Modifiés : `common_data.py`, `qcm_data.py`, `web/export_markdown.py`, `web/publish_hosting.py`, `web/sync_quartz_assets.py`, `web/visibility_profiles.yaml`,
`web/publish_profile.sh`, `build/config.yaml`, + boucles `td/tp` → types déclarés (`export_json`, `build_notebooks`, `generate_all`, `manage`, `check_data`, `add_config_blocks`).
Déplacé : `td/projet1_Tsiolkovski` → `projet/projet1_Tsiolkovski`.

### Puis : états de chapitre, all_fast, QCM local
`publication.etats` (a_venir / en_cours / termine / les tiens) accepté partout où un profil est attendu (`common_data.expand_profile`) ; profil `all_fast` ; `tools/qcm_local.sh` ; commentaires de `build/config.yaml` réécrits (mode d'emploi + tableau des profils) ; `segno` ajouté à `requirements.txt`.

### Puis : fichiers par profil, show_* explicites, héritage `visibilite:`
`fichiers:` accepte `profils` / `sauf` / `si` ; profils réécrits avec un `show_*` par élément (+ `show_metadonnees` sur le site) ; cibles PDF `visibilite: <profil|état>` (`common_data.apply_visibility_to_target`, empreinte `pdf_status`) ; nouveaux contrôles dans `tools/check_evolutions.py`.
