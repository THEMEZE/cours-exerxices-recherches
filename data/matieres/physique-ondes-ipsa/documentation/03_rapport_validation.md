# Rapport de validation

## Ce qui a été vérifié (et comment)

| Contrôle | Outil | Résultat |
|---|---|---|
| Physique : 70+ vérifications symboliques/numériques (équations exactes, linéarisation, ordres, modes, battements, énergie, Floquet, Bessel…) | `outils_verification/verif_physique_td4.py` | **74 OK, 0 échec** |
| Syntaxe YAML (PyYAML safe_load) des 10 fichiers | idem validateur | OK |
| Cohérence de structure avec les 30 `ex*.yaml` existants (clés de 1ᵉʳ niveau, clés de question, format des items `titre/texte`, `discipline/texte`, `niveau/titre/texte`, accroche, figure, `_meta`) | `valider_yaml_td4.py` | **OK, aucune clé inconnue** |
| `exercices_ordre` = fichiers présents ; ids `td4_exK` ; ids de questions `q1…qn` séquentiels | idem | OK |
| Compilation LaTeX (pdflatex, amsmath/enumitem) des **1 340 champs texte** | `test_latex_td4.py` | **0 erreur** |

## Principales vérifications physiques
- Force du ressort `= h(sin α2 − sin α1)cos α1 + O(ε⁴)` (rapport d'erreur ≈ 16 quand l'amplitude est divisée par 2).
- Ex. 3 : `T = 1,26 s` ; `A2 = −(k/k_c) a0` à l'antirésonance ; mode bas en phase, mode haut en opposition ; écart `≥ 2Ω²`.
- Ex. 4 : `k ≈ 1919 N/m` ; `det(K − ω²M) = ω²(m1m2ω² − k(m1+m2))` ; modes M-orthogonaux mais pas euclidiens.
- Ex. 5 : `ω_c² = k h²/(mℓ²)`, `T_b = 40,3 s`, `κ = 4,85 %`, transfert complet à `T_b/2`.
- Ex. 6 : valeurs propres `2 − √2, 2, 2 + √2` ; formule de Rayleigh ; solution modale = intégration numérique.
- Ex. 7 : écart des niveaux, fraction `sin²2θ`, `T_b(Δ=0) = 126 s`, `T_b(Δ=2) = 56 s`.
- Ex. 8 : modes exacts (période elliptique), mode en opposition (1D) et Poincaré–Lindstedt ; équation de Hill vérifiée par dérivation symbolique des équations exactes ; seuil `A_c = 0,378` (numérique 0,381).
- Ex. 9 : `ω_p = 2ω0 sin(πp/N)` pour N = 2…8 ; `x_n = a0 J_{2n}(2ω0 t)` (erreur < 1e-6) ; solution N = 4.

## Limites à connaître
1. **Le code du générateur Python n'était pas dans le ZIP** : la compatibilité est validée contre le schéma *observé* dans vos 30 exercices existants, pas par une génération réelle. Un premier passage dans votre générateur reste la vraie validation.
2. `seance: 5` et les libellés de niveau sont des hypothèses (voir LISEZMOI).
3. Le test LaTeX utilise un préambule standard (pas votre préambule) ; si vos macros diffèrent (ex. `itemize[label = $\bullet$]` suppose `enumitem`, déjà utilisé dans TD1-TD3), cela n'a pas d'impact.
4. Les figures `ref:` actives (`td4_ex1_…`, etc.) ne sont pas fournies ; les « Suggestion : » sont commentées.
5. La relecture de fond (pertinence pédagogique, niveau) reste de votre ressort ; les calculs sont contrôlés, pas le goût.
