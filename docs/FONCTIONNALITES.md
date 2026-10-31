# Fonctionnalités : de l'ancien site à la V2

Référence : les besoins utilisateur, pas l'ancienne implémentation. Chaque ligne indique le sort de la fonctionnalité.

| Besoin | Ancien site | V2 |
|---|---|---|
| Trouver les meilleurs titres | Explorer `rapport.html`, snapshot JSON de 107 Mo recalculé par cron | **Explorer** `index.html` : évaluation à la demande depuis la base (mesures pré-calculées la nuit), 4 stratégies en cartes, éditeur avancé |
| Quatre stratégies | `regular`, `fast`, `recovery`, `low_volatility` + niveaux de pente/régularité | **Conservées et redéfinies** : Croissance régulière, rapide, Rebond, Hausse calme (réglages documentés dans `docs/METHODE.md`) |
| Deux stratégies « momentum » (essai) | `momentum` (6 mois, J−126 → J−21 séances), `momentum12` (12 mois, J−252 → J−21 séances) | **Ajoutées** : classement par la progression passée en ignorant le dernier mois, sans seuil ; filtres habituels et négociabilité conservés ; suivi à 21 et 63 séances (`docs/METHODE.md`) |
| Périodes réglables | six horizons, séances 1–252 | **Conservé** : six périodes, 1–252 séances, sept critères chacune |
| Tri / mode de classement | trend, performance, regularity, stability + exposant k | **Conservé** (4 modes, poids par période) ; exposant k **supprimé** (peu lisible) |
| Filtres techniques | MA50, MA50 ascendante, variation max, écart MA20 | **Conservés** |
| Actions et ETF classés séparément | oui (phase 1) | **Conservé** |
| Titre exclu jamais recommandé | défaut (DVDG.DE présent à tort) | **Garanti** par `v_recommendable` + test d'intégration |
| Recherche par nom/ticker/ISIN, y compris titre non retenu | oui | **Conservée** ; les titres exclus sont étiquetés avec leur motif |
| Filtres pratiques | marché, PEA, budget, ouvert, note, risque | Marché, type, PEA, « détenus ». **Retirés** : filtre « budget/part entière » et « note » (la note /10 mélangeait des choses non comparables ; remplacée par un score de classement 0–100 et un verdict expliqué). « Place ouverte » : à reconsidérer |
| Fiche titre | `titre.html` : graphique, notes, risques | **Refaite** : cours 1M→Tout + 15 min, verdict détaillé critère par critère, mesures par période, repères techniques, autres cotations, positions détenues |
| Fiche ETF pédagogique | orpheline (jamais reliée) | **Faite** : frais, encours, composition, secteurs (Yahoo quoteSummary, cache 30 jours) |
| Prix datés (« Dernier cours », « Clôture », « Cours différé ») | oui | **Conservés** (`price_source`) |
| Portefeuilles multiples, par défaut, stratégie par portefeuille | oui | **Conservés** |
| Achats, ventes partielles, frais, devises | registre `jb_portfolio_transactions` | **Conservés** + contrôle de vente ≤ quantité détenue, édition/suppression, export CSV |
| Valorisation, plus-values latentes/réalisées | oui | **Refaites** : prix de revient moyen pondéré, poids, titres sans cours signalés |
| Bilan | page `bilan.html` | **Refait** : totaux, par portefeuille, réalisé par année |
| Titre détenu mais exclu | pouvait disparaître | **Toujours visible**, badge « Hors sélection », toujours actualisé |
| Notes par titre | `jb_notes`, vide | **Supprimées** |
| Suivi (page figée) | `suivi.html`, classement du jour enregistré à la main | **Refaite** : chaque nuit, les 20 premiers actions/ETF de chacune des 4 stratégies sont enregistrés ; à 1, 3 et 5 séances, rendement comparé à la médiane de tout l'univers (écart, % qui battent l'univers). Alerte « trop tôt pour conclure » sous 20 jours de résultats ; jours reconstitués étiquetés (biais de survie) |
| Comptes, sessions, anti-force-brute | `auth.php` | **Refaits** (mêmes protections : bcrypt, cookie HttpOnly/SameSite, 5 essais/15 min, contrôle d'origine) |
| Inscription par mot d'invitation | oui | **Conservée** (réglage Administration) |
| Administration : utilisateurs | oui | **Conservée** (créer, désactiver, réinitialiser) |
| Administration : FinanceDatabase, Yahoo, historiques, toutes les cotations, état du système | 6 pages, 3 générations de tables | **Fusionnées** en 4 onglets : Données, Traitements, Utilisateurs, Réglages |
| Pages orphelines `univers-*`, `finance-database-catalogue` | oui | **Supprimées** |
| Cron | 3 entrées | **Une seule** : `python -m engine.cli tick` toutes les 15 minutes |
| Mode Débutant / Avancé | oui | **Conservé** (Simple / Avancé dans « Mon compte ») |
| Thème | clair | **Clair / sombre / auto** |
| Historiques 15 min | provisoires, figés | **Maintenus** (20 séances), trous détectés et réparés |
| Historiques 5 min, 1 h, yfinance | présents | **Supprimés** |

## Pas encore fait (limites connues)
Actualités et calendrier de résultats (absents aussi de l'ancien moteur en pratique) ; assistant de décision (architecture prête, voir `ARCHITECTURE.md` §10).
