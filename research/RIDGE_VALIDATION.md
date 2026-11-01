# Expérience Ridge : rapport de validation (résultat négatif, conservé tel quel)

Sortie brute de `python3 scripts/research_ridge.py valid` (commit 9741783), exécutée sur Hostinger sur les historiques exportés, lecture seule. Protocole : `research/PROTOCOLE_RIDGE.md`. La période finale (dates de décision à partir du 2023-01-01) n'a PAS été lue. Verdict : non concluant → Ridge rejeté dans sa forme actuelle.

# Expérience Ridge (exploratoire) · mode valid

*Étude exploratoire sur les survivants sélectionnés aujourd'hui par Jigobourso : biais de survie et de sélection NON corrigés ; aucune conclusion de surperformance historique réelle ne peut en être tirée. Actions seulement, USD, valeur échangée >= 1 M, données depuis 1998.*

1481 titres, 318575 lignes (titre × date), 343 dates de décision (toutes les 21 séances), calendrier 1998-01-02 -> 2026-10-30. Écartés : {'A3': 6, 'titres': 1481, 'trop court': 72}. Exemples neutralisés (A1) : 69 ; titres A3 : 6.

## Horizon 21 séances

| Modèle | Dates | IC moyen | % IC > 0 | Excès brut Top 20 (pts) [IC95 blocs] | Net 10 pb | Net 30 pb | Net 60 pb | Net 100 pb | Rotation | CVaR95 (net 60, rendement) |
|---|---|---|---|---|---|---|---|---|---|---|
| Momentum 6-1 seul | 226 | +0.004 | 53 | +0.48 [-0.17 ; +1.13] | +0.39 | +0.21 | -0.06 | -0.43 | +45 % | -20.84 |
| Momentum 12-1 seul | 226 | +0.013 | 61 | +0.77 [+0.08 ; +1.48] | +0.71 | +0.59 | +0.42 | +0.18 | +29 % | -19.99 |
| Faible volatilité seule | 226 | +0.006 | 54 | -0.68 [-1.16 ; -0.22] | -0.71 | -0.77 | -0.87 | -1.00 | +16 % | -10.38 |
| R² seul | 226 | +0.012 | 55 | +0.45 [+0.03 ; +0.86] | +0.34 | +0.12 | -0.20 | -0.64 | +55 % | -17.56 |
| Pente seule | 226 | +0.007 | 54 | +0.45 [-0.27 ; +1.14] | +0.38 | +0.23 | +0.02 | -0.27 | +36 % | -19.93 |
| Ridge V1 (cœur) | 226 | -0.008 | 48 | +0.05 [-0.85 ; +0.92] | -0.05 | -0.25 | -0.55 | -0.96 | +50 % | -22.38 |
| Ridge V2 (+drawdown, 5 séances) | 226 | +0.014 | 51 | +0.46 [-0.35 ; +1.33] | +0.30 | -0.01 | -0.47 | -1.09 | +78 % | -21.48 |
| Ridge V1 écrêté 1-99 % | 226 | -0.010 | 50 | -0.21 [-0.92 ; +0.45] | -0.32 | -0.52 | -0.82 | -1.22 | +50 % | -21.09 |

Déciles de score (rendement moyen réel à l'horizon, en %, du plus bas au plus haut) :

- Momentum 6-1 seul : +1.5, +1.2, +0.9, +1.4, +1.0, +1.1, +1.1, +1.2, +1.1, +1.5
- Ridge V1 (cœur) : +1.2, +1.4, +0.9, +1.1, +1.1, +1.1, +1.6, +1.1, +1.2, +1.3

Coefficients Ridge V1 par pli (rangs d'indicateurs) :

| Indicateur | Coefficient moyen | Signe stable | lambda choisis |
|---|---|---|---|
| m61 | -0.0049 | 84 % | [(1.0, 7), (0.0001, 6), (0.1, 3)] |
| m121 | +0.0014 | 79 % | [(1.0, 7), (0.0001, 6), (0.1, 3)] |
| slope | +0.0027 | 74 % | [(1.0, 7), (0.0001, 6), (0.1, 3)] |
| r2 | +0.0061 | 100 % | [(1.0, 7), (0.0001, 6), (0.1, 3)] |
| vol | +0.0042 | 95 % | [(1.0, 7), (0.0001, 6), (0.1, 3)] |

Écart Ridge V1 - Momentum 12-1 seul (excès brut Top 20, par date) : moyenne -0.72 · IC95 blocs [-1.66 ; +0.10] · IC 98,75 % (2 tests) [-1.78 ; +0.18]

- 2004-2010 : écart moyen -0.30 sur 85 dates
- 2011-2016 : écart moyen -0.68 sur 71 dates
- 2017-2022 : écart moyen -1.27 sur 70 dates

Sensibilités (jamais utilisées pour choisir le modèle principal) : IC moyen / excès brut Top 20 / net 60 pb, Ridge V1 et Momentum 6-1 seul

| Configuration | Ridge V1 : IC | brut | net 60 | Momentum 6-1 : IC | brut | net 60 |
|---|---|---|---|---|---|---|
| nettoyage principal (référence) | -0.008 | +0.05 | -0.55 | +0.004 | +0.48 | -0.06 |
| S1 : sans exemples touchés par C | -0.011 | -0.13 | -0.73 | +0.004 | +0.58 | +0.03 |
| S3 : sans exemples touchés par un mouvement de 40 % (borne agressive) | -0.011 | -0.19 | -0.76 | +0.002 | +0.29 | -0.27 |
| brut : données d'origine, aucun nettoyage | -0.008 | +0.05 | -0.55 | +0.004 | +0.48 | -0.06 |

Entrée à la clôture de t+1 (décalage d'exécution) : Ridge V1 excès brut +0.03 · Momentum 6-1 +0.28.

Règle de décision (protocole) : NON aux cinq critères → Horizon 21 : non concluant ou écarté.

## Horizon 63 séances

| Modèle | Dates | IC moyen | % IC > 0 | Excès brut Top 20 (pts) [IC95 blocs] | Net 10 pb | Net 30 pb | Net 60 pb | Net 100 pb | Rotation | CVaR95 (net 60, rendement) |
|---|---|---|---|---|---|---|---|---|---|---|
| Momentum 6-1 seul | 222 | +0.003 | 54 | +1.54 [-0.11 ; +3.13] | +1.39 | +1.09 | +0.65 | +0.05 | +75 % | -29.72 |
| Momentum 12-1 seul | 222 | +0.007 | 57 | +0.95 [-0.81 ; +2.81] | +0.84 | +0.63 | +0.32 | -0.10 | +52 % | -30.33 |
| Faible volatilité seule | 222 | +0.010 | 55 | -2.17 [-3.55 ; -0.86] | -2.24 | -2.36 | -2.55 | -2.81 | +32 % | -18.22 |
| R² seul | 222 | +0.011 | 55 | +0.81 [+0.01 ; +1.64] | +0.63 | +0.27 | -0.27 | -0.98 | +89 % | -26.17 |
| Pente seule | 222 | +0.004 | 53 | +1.32 [-0.48 ; +2.97] | +1.16 | +0.85 | +0.38 | -0.24 | +78 % | -29.11 |
| Ridge V1 (cœur) | 222 | -0.030 | 46 | -1.43 [-3.66 ; +0.65] | -1.59 | -1.90 | -2.36 | -2.98 | +77 % | -36.35 |
| Ridge V2 (+drawdown, 5 séances) | 222 | -0.026 | 42 | -0.69 [-2.63 ; +1.29] | -0.85 | -1.18 | -1.67 | -2.32 | +82 % | -34.22 |
| Ridge V1 écrêté 1-99 % | 222 | -0.030 | 45 | -1.44 [-3.40 ; +0.50] | -1.60 | -1.92 | -2.40 | -3.04 | +80 % | -33.30 |

Déciles de score :

- Momentum 6-1 seul : +4.5, +3.3, +3.0, +3.5, +3.0, +3.1, +3.8, +3.5, +3.8, +4.3
- Ridge V1 (cœur) : +3.2, +3.7, +3.4, +3.2, +3.4, +3.4, +3.9, +3.1, +4.0, +4.4

Coefficients Ridge V1 par pli :

| Indicateur | Coefficient moyen | Signe stable | lambda choisis |
|---|---|---|---|
| m61 | +0.0008 | 42 % | [(0.0001, 6), (1.0, 5), (0.01, 4)] |
| m121 | -0.0027 | 58 % | [(0.0001, 6), (1.0, 5), (0.01, 4)] |
| slope | -0.0039 | 53 % | [(0.0001, 6), (1.0, 5), (0.01, 4)] |
| r2 | +0.0162 | 100 % | [(0.0001, 6), (1.0, 5), (0.01, 4)] |
| vol | +0.0210 | 100 % | [(0.0001, 6), (1.0, 5), (0.01, 4)] |

Écart Ridge V1 - Momentum 6-1 seul (excès brut Top 20, par date) : moyenne -2.97 · IC95 blocs [-5.04 ; -0.91] · IC 98,75 % (2 tests) [-5.33 ; -0.58]

- 2004-2010 : écart moyen -2.38 sur 83 dates
- 2011-2016 : écart moyen -3.85 sur 69 dates
- 2017-2022 : écart moyen -2.81 sur 70 dates

| Configuration | Ridge V1 : IC | brut | net 60 | Momentum 6-1 : IC | brut | net 60 |
|---|---|---|---|---|---|---|
| nettoyage principal (référence) | -0.030 | -1.43 | -2.36 | +0.003 | +1.54 | +0.65 |
| S1 : sans exemples touchés par C | -0.027 | -0.66 | -1.59 | +0.004 | +1.86 | +0.96 |
| S3 : sans exemples touchés par un mouvement de 40 % (borne agressive) | -0.025 | -0.84 | -1.77 | +0.001 | +1.20 | +0.29 |
| brut : données d'origine, aucun nettoyage | -0.030 | -1.43 | -2.36 | +0.003 | +1.54 | +0.65 |

Entrée à la clôture de t+1 : Ridge V1 excès brut -1.43 · Momentum 6-1 +1.41.

Règle de décision (protocole) : NON aux cinq critères → Horizon 63 : non concluant ou écarté.

## Verdict global : non concluant
