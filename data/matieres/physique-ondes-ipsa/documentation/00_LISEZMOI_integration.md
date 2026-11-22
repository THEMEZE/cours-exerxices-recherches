# TD 4 « Oscillateurs couplés » — livraison

Contenu : uniquement des **fichiers nouveaux** ; aucun fichier existant du projet n'est modifié, aucun nouveau format YAML, générateur Python non touché.

## Arborescence

```
physique-ondes-ipsa/td/td4_oscillateurs_couples/
  _meta.yaml                                  (nouveau TD : id td4, 9 exercices, cours Chap. 4 en 8 points de cours)
  ex1_pendules_couples_battements.yaml        corrigé du TD, ex. 1 (4 questions)
  ex2_oscillateurs_dissymetriques.yaml        corrigé du TD, ex. 2 (3 questions)
  ex3_pendule_chariot.yaml                    corrigé du TD, ex. 3 (6 questions : libre q1-q3, forcé q4-q6)
  ex4_molecule_diatomique.yaml                corrigé du TD, ex. 4 (4 questions)
  ex5_ressort_a_mi_hauteur.yaml               complément niveau 1 (CPGE)           facultatif: true
  ex6_trois_masses_quatre_ressorts.yaml       complément niveau 2 (ambitieux)      facultatif: true
  ex7_desaccord_anticroisement.yaml           complément niveau 2 (ambitieux)      facultatif: true
  ex8_modes_non_lineaires_pendules.yaml       complément niveau 3 (ENS)            facultatif: true
  ex9_anneau_de_N_oscillateurs.yaml           complément niveau 3 (ENS)            facultatif: true
documentation/        ce fichier, choix pédagogiques, erreurs du corrigé officiel, rapport de validation
outils_verification/  verif_physique_td4.py, valider_yaml_td4.py, test_latex_td4.py, fix_titres.py
```

## Intégration

1. Copier le dossier `td4_oscillateurs_couples/` dans `physique-ondes-ipsa/td/` (à côté de `td1_corde`, `td2_ondes_sonores`, `td3_reflexion_transmission`).
2. Lancer votre générateur comme pour TD1-TD3.
3. Figures : seules les `ref:` actives (`td4_ex1_…`, etc.) sont à fournir ; les figures « Suggestion : » sont commentées (convention TD3) et n'interviennent pas dans la compilation.

## Deux hypothèses à confirmer (le générateur n'était pas dans le ZIP)

- `seance: 5` (numéro de séance du TD4) ; à ajuster si besoin dans `_meta.yaml` et dans chaque `ex*.yaml`.
- Niveaux de `aller_plus_loin` : `licence` et `master` (valeurs déjà présentes dans vos fichiers).

## Conventions de contenu

- LaTeX en bloc `|`, décimales `{,}`, `i` droit, `\dfrac`, `\emph`, `{\bf …}`, `itemize[label = $\bullet$]` (comme TD1-TD3).
- Chaque exercice du TD suit la progression demandée : (1) géométrie et projections sans approximation, (2) petits angles et physique de l'approximation, (3) DL de sin/cos avec ordre et erreur, (4) découplage « physicien » puis « mathématicien », (5) ordre n / système d'ordre 1 / valeurs propres, (6) interprétation physique.
