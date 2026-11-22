# Choix pédagogiques

## Fil conducteur
Comprendre avant de calculer : chaque exercice commence par le système, le repère et les vecteurs de base, puis les équations **exactes**, puis l'approximation (avec son ordre de grandeur), puis les deux méthodes de découplage, et se termine par une lecture physique.

## 1. Sans approximation d'abord (ex. 1, 3, 5, 8)
- Base locale du pendule `e_r = (sin α, −cos α)`, `e_α = (cos α, sin α)` construite par produits scalaires ; `v = ℓα̇ e_α`, `a = ℓα̈ e_α − ℓα̇² e_r`.
- Les signes des projections sont justifiés par un cas test (« ressort étiré tire vers… »).
- Résultat clé : `x_i = ℓ sin α_i` est exact ; le ressort est incliné de `v = ℓ(cos α1 − cos α2)`, d'ordre 2 ; donc la force du ressort est `ℓ(sin α2 − sin α1)cos α1 + O(ε⁴)` (vérifié numériquement). Pas de terme quadratique dans les équations ; la première non-linéarité est cubique.

## 2. Petits angles : ce qu'on gagne et ce qu'on perd
Équilibre, linéarisation simultanée de toutes les variables, tableau des ordres (cos θ ≈ 1 dans une force, mais 1 − cos θ ≈ θ²/2 dans une énergie), limites de validité (ex. 8 : le seuil d'instabilité du mode en phase `A_c = √(8κ/(ω0²+6κ))` montre que « petit » dépend aussi du couplage).

## 3. DL de sin et cos
Signe, ordre, erreur (premier terme négligé), parité (sin impair → ordre 3, cos pair → ordre 2), lien DL / petits angles / linéarisation (point de cours dans `_meta.yaml`, repris dans les exercices). `T(θ0) = T0(1 + θ0²/16 + 11θ0⁴/3072 + …)` donne l'erreur concrète.

## 4. Deux méthodes pour chaque système couplé
- **Physicien** : somme/différence, symétrie, centre de masse/relatif. Dit pourquoi ça marche (diagonales égales et couplage réciproque) et quand ça échoue (ex. 2 : ailes dissymétriques → combinaison `x1 + βx2` = problème aux valeurs propres déguisé).
- **Mathématicien** : `M X'' + K X = 0`, `(K − ω²M)A = 0`, déterminant, vecteurs propres, M-orthogonalité, diagonalisation explicite 2×2 (angle de mélange `tan 2θ = 2b/(a−c)`), décomposition modale `c_p = u_pᵀ M X0`.
- Comparaison explicite à la fin de chaque exercice.

## 5. Mini-cours sur les équations différentielles d'ordre n (dans `_meta.yaml`, repris ex. 4, 6, 9)
Ordre n scalaire ↔ système d'ordre 1 `Y' = AY` ↔ matrice compagnon ; `exp(At)` ; valeurs propres de `𝒜 = [[0,I],[−M⁻¹K,0]]` : `λ = ± iω_p`, `λ² = −ω²` (on ne confond pas les valeurs propres de 𝒜 avec les ω² du problème mécanique) ; mode nul → bloc de Jordan, solution `a + bt` (ex. 4 et 9).

## 6. Interprétation physique
Modes (nœuds, phase), battements (`T_b = 2π/(ω2−ω1)`, séparation d'échelles), échange d'énergie (ex. 5 : fraction `κ` stockée dans le ressort ; ex. 7 : `sin²2θ`), antirésonance et amortisseur à masse accordée (ex. 3), levée de dégénérescence et anticroisement (ex. 7), propagation (ex. 9).

## 7. Compléments originaux (facultatifs, type ENS)
| Ex. | Niveau | Idée | Objectif |
|---|---|---|---|
| 5 | 1 – CPGE | ressort attaché à mi-hauteur | moment cinétique, `ω_c² = (k/m)(h/ℓ)²`, battements, énergie |
| 6 | 2 | 3 masses / 4 ressorts | symétrie, diagonalisation 3×3, Rayleigh, ordre 6 |
| 7 | 2 | oscillateurs désaccordés | anticroisement, angle de mélange, transfert `sin²2θ`, analogie 2 niveaux |
| 8 | 3 – ENS | modes non linéaires de pendules couplés | variétés invariantes, Poincaré–Lindstedt, Floquet/Mathieu |
| 9 | 3 – ENS | anneau de N oscillateurs | Fourier discret, dégénérescence, Jordan, Bessel, limite continue |

Chaque complément contient : énoncé, objectifs, coups de pouce, correction détaillée, discussion physique, `facultatif: true` et un intitulé « Complément (niveau …) ».

## Cohérence avec le corrigé officiel
Les résultats finaux sont identiques à ceux du corrigé de l'établissement (sauf erreurs listées dans `02_erreurs_corrige_officiel.md`) ; la démarche, elle, est plus détaillée et justifiée.
