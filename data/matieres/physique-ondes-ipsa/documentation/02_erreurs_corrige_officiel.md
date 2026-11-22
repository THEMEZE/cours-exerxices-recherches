# Erreurs et imprécisions relevées dans le corrigé officiel (« Corrigé TD 2 de Physique des Ondes I », IPSA 2014-2015, correspondant au TD « Oscillateurs couplés »)

Contrôle indépendant par calcul symbolique et numérique (`outils_verification/verif_physique_td4.py`). Les résultats finaux sont en général corrects ; les points ci-dessous sont des erreurs de rédaction, de nommage ou d'interprétation.

## Exercice 1 (pendules couplés)
1. **Équation de forme `y'' + a y' = 0`** : c'est `y'' + ω² y = 0` (pas de terme en `y'`).
2. **`ω = g/l + k/m ∓ k/m`** (1ʳᵉ méthode) : il manque le carré ; c'est `ω² = g/ℓ + k/m ∓ k/m`.
3. **« mouvement antisymétrique »** pour le mode où les deux pendules oscillent en phase : c'est le mode **symétrique** (en phase) ; l'antisymétrique est en opposition de phase.
4. **Deux « périodes » de battement `T1` et `T2`** : le corrigé trouve `T1 = π/ω = 2π/(ω2 − ω1)` (intervalle entre deux annulations de l'amplitude de P1) puis `T2 = π/(ω2 − ω1)`. `T1` est bien la période de battement ; `T2` est l'intervalle entre une annulation de `A1` et la suivante de `A2` (le *temps de transfert complet*, demi-battement) : à nommer comme tel, pas comme une seconde période.
5. **Notations `ω`/`Ω` inversées** par rapport à l'usage : la pulsation lente (enveloppe) est notée `ω = (ω2 − ω1)/2` et la rapide `Ω = (ω1 + ω2)/2`, et `x1 = a sin(ωt) sin(Ωt)` (`ω` ≠ pulsation du pendule) : source de confusion avec la pulsation propre.

## Exercice 2 (oscillateurs dissymétriques)
6. **`ω' = √2`, `ω'' = √7`** : il manque le facteur `ω0` (`ω' = √2 ω0`, `ω'' = √7 ω0`).
7. **`ω0² = √(k/m)`** : c'est `ω0² = k/m` (la racine est en trop).
8. **Équations en `S = x1 + x2`, `D = x1 − x2`** : le découplage par somme/différence est impossible ici (diagonales différentes, `3ω0²` et `6ω0²`). Le corrigé écrit des équations couplées dont les coefficients sont erronés : les bonnes sont `S̈ + (5/2)ω0² S − (3/2)ω0² D = 0` et `D̈ + (13/2)ω0² D − (3/2)ω0² S = 0` ; le corrigé affiche `ω0²/2` devant `S` et place `−3ω0²/2` et `13ω0²/2` devant `D` et `S` (rôles inversés). Il faut passer par les valeurs propres de `K` (ou la combinaison `x1 + βx2`).
9. **Battements** : le corrigé dit qu'ils sont « obtenus séparément pour `x1` si `A' = ±A''` et pour `x2` si `A' = ±4A''` ». C'est formellement un produit de sinusoïdes, mais la notion de battement exige `ω2 − ω1 ≪ ω1 + ω2` ; ici `ω''/ω' = √7/√2 ≈ 1,87`, les fréquences ne sont pas voisines : il n'y a pas de battement au sens physique.

## Exercice 3 (pendule-chariot)
10. **Équation du pendule** écrite avec `F sin θ` et `F ≈ mg` : correct à l'ordre 1, mais il vaut mieux projeter sur la tangente pour éliminer la tension (`T = mg cos θ + …`, égale à `mg` seulement à l'ordre 0).
11. **Déterminant** : le déterminant écrit contient « `− Ω²` » à la place de `− Ω⁴` (coquille ; l'équation bicarrée qui suit est, elle, correcte).
## Exercice 4 (molécule diatomique)
12. **`f0 = 6,5·10²³ Hz`** : l'ordre de grandeur est faux ; `f0 = c/λ0 = 3·10⁸ / 4,6·10⁻⁶ = 6,5·10¹³ Hz` (infrarouge). Le calcul de `k ≈ 1918 N/m` est, lui, cohérent avec `f0 = 6,5·10¹³`.
13. **Référentiel barycentrique** : affirmé galiléen car `G` est en mouvement rectiligne uniforme, correct ; mais `x1 = GM1`, `x2 = GM2` imposent `m1 x1 + m2 x2 = 0` : à rappeler pour justifier `x1 = −m2 X/(m1+m2)` et le mode de translation (`ω = 0`).
