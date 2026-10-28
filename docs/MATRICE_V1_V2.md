# Matrice V1 → V2 (fonctionnalités et ergonomie)

Établie le 28/10/2026 à partir du code réel de l'ancien site (`rapport.html`, `static/*.js`, `titre.html`, `bilan.js`, `admin.html`, `systeme.php`, `finance-database*.php`, `historiques.php`, `univers-*.php`) et de la V2 livrée le même jour.
Statuts : **repris** (équivalent présent), **repensé** (même besoin, autre conception), **absent** (manque constaté à la livraison, traité dans le chantier « richesse » : colonne *Traitement*).

## Explorer, stratégies, filtres

| # | Fonctionnalité V1 | Statut à la livraison | Traitement |
|---|---|---|---|
| 1 | 4 stratégies + « personnalisée » | repris | cartes de stratégie toujours visibles |
| 2 | Mode Débutant / Avancé du réglage | repensé (éditeur seulement en mode avancé, **peu visible**) | éditeur de stratégie accessible directement depuis l'Explorer, deux niveaux : réglages guidés (pente, régularité, repli, accélération) et réglage détaillé |
| 3 | Réglage par période : séances (1–252), pente, R², ER, performance, volatilité, repli, accélération | repris (éditeur avancé) ; **accélération absente** (abandonnée de la méthode) | accélération réintroduite comme critère facultatif (mesure + seuil + tri) |
| 4 | Niveaux de pente (douce→très forte) et de régularité (aucune→stricte) | absent | sélecteurs guidés remplissant les seuils |
| 5 | Tolérance aux corrections (repli max 5/10/20 %) | absent | sélecteur guidé |
| 6 | Filtres techniques : cours > MM50, MM50 ascendante, variation jour max, écart MM20 max | repris | conservés, visibles |
| 7 | Tri : tendance / performance / régularité / stabilité ; poids par période ; pénalisation k | repris (modes, poids) ; **k absent** (supprimé : exposant non démontré) | modes et poids visibles dans l'éditeur |
| 8 | Filtres pratiques : marché, type, PEA, recherche (nom/ticker/ISIN) | repris | enrichis |
| 9 | Filtre budget / part entière | **absent** | filtre « prix d'une part ≤ budget » |
| 10 | Avis minimum, risque maximum | repensé (note /10 remplacée par score 0–100 + verdict expliqué) | filtre score minimum, volatilité maximale, repli maximal |
| 11 | « Place ouverte » | **absent** | filtre « place ouverte maintenant » |
| 12 | Détenus seulement | repris | conservé |
| 13 | Statuts Retenus / Écartés / Non évaluables / Tous avec compteurs | repris | conservé |
| 14 | Tri des résultats (7 critères) | **appauvri** (3) | colonnes triables : rang, nom, prix, pente, R², performance, volatilité, repli, volume, fraîcheur |
| 15 | Pagination | repris | taille de page réglable |
| 16 | Stratégie enregistrée par portefeuille | repris | conservé |
| 17 | Actions et ETF classés séparément | repris | + vue **comparaison actions / ETF** côte à côte |
| 18 | Statistiques d'exclusion et explications détaillées | **absent** | panneau « pourquoi ces titres sont écartés » (par critère, par période) |
| 19 | Source des données (FinanceDatabase, Yahoo) | **absent** | bandeau de sources : catalogue FinanceDatabase, cours Yahoo Finance, fraîcheur, couverture |
| 20 | Export CSV du classement | absent (déjà absent de la V1 sur l'Explorer) | export CSV des résultats filtrés |

## Fiche titre

| # | V1 | V2 à la livraison | Traitement |
|---|---|---|---|
| 21 | Graphique historique, plusieurs étendues | repris | conservé, refait |
| 22 | Graphique 15 min | **partiel** : un tracé des 140 dernières barres, sans séances ni fuseau | vue intraday dédiée : **deux dernières séances**, fuseau de la place, bougies/volume, trous signalés |
| 23 | Verdict critère par critère, valeur mesurée / seuil | repris | conservé |
| 24 | Six périodes : pente, R², ER, performance, volatilité, repli | repris | conservé, tableau complet |
| 25 | Moyennes mobiles MM20/MM50, écart | repris | + courbes MM20/MM50 sur le graphique |
| 26 | Identité, ISIN, place, devise, PEA probable | repris | conservé |
| 27 | Données Quote : volume séance, volume moyen 10 j / 3 mois, état du marché, horodatage | **absent** (partiel) | bloc « données de marché » avec fraîcheur et source |
| 28 | Avertissement produit à effet de levier / structure du fonds | **absent** | détection par nom et catégorie, bandeau |
| 29 | Fiche ETF (frais, encours, composition, secteurs) | repris (nouveau) | conservé |
| 30 | Positions détenues sur le titre | repris | conservé |
| 31 | Ajouter à un portefeuille depuis la fiche | partiel | bouton direct |
| 32 | Autres cotations d'un même produit | repris | conservé |

## Portefeuilles et bilan

| # | V1 | V2 à la livraison | Traitement |
|---|---|---|---|
| 33 | Portefeuilles multiples, défaut, création, renommage | repris | |
| 34 | Achat/vente, frais, devise, édition, suppression, export CSV | repris | |
| 35 | Valorisation, plus-values latentes/réalisées, prix de revient moyen | repris | |
| 36 | « Filet de sécurité » (stop) et « objectif » par position, position du cours entre les deux | **absent** | stop et objectif par position (stockés, affichés, alerte visuelle) |
| 37 | Graphiques « depuis l'achat » et « dernier mois », en % ou en € | **absent** | graphique de position |
| 38 | Bilan global, réalisé par année | repris | |

## Suivi

| 39 | Suivi des classements 1/3/5 séances vs indice | repensé (V2 : vs univers, jours reconstitués étiquetés) | conservé |

## Administration

| # | V1 | V2 à la livraison | Traitement |
|---|---|---|---|
| 40 | Utilisateurs : créer, mot de passe, activer/désactiver | repris | |
| 41 | Invitations (mot d'invitation) | repris (réglage) | |
| 42 | Chargement FinanceDatabase avec journal et détail des fichiers | repensé (bouton + ligne de journal) | page Sources : dernier chargement, lignes lues, commit, fichiers, relance |
| 43 | Filtrage FinanceDatabase configurable (critères, priorité des marchés) | **absent** de l'interface (règles dans le code) | affichage des règles actives et des réglages modifiables (seuils de liquidité, prix) |
| 44 | Catalogues brut / filtré / final consultables (recherche, type, marché, statut) | **absent** | explorateur du catalogue : toutes les cotations avec statut, motif d'exclusion, source |
| 45 | Yahoo Quote : lots, paramètres, journal, annulation | repensé (traitements `nightly`/`tick`) | page Traitements : détail, journal, relance, annulation |
| 46 | Historiques Yahoo 1d (+ 1h/5m supprimés) | repris | |
| 47 | État du système : crons, actions manuelles, chaîne de données, erreurs | partiel | page Système complète : places, fraîcheur, couverture, trous, erreurs, crons |
| 48 | Univers d'investissement : récapitulatif, répartition par marché | partiel | tableau de bord Univers |
| 49 | « Relancer le calcul » avec logs | repris | |

## Transverse

| 50 | Thème clair / sombre | repris | |
| 51 | Mots de passe : visibilité, récupération par jeton | partiel (visibilité absente) | affichage du mot de passe ; récupération par l'administrateur |
| 52 | Navigation, menu mobile | repris | refaite |
| 53 | Identité visuelle | **générique** | refonte du design (voir `DESIGN.md`) |

## Bilan du traitement (28/10/2026, développement local, non déployé)

Traité : 2 (éditeur guidé + détaillé, poids par période), 4, 5, 6, 7 (poids), 8, 9, 10, 11, 14, 15, 17 (comparaison côte à côte), 18, 19, 20, 21, 22 (intraday 15 min, deux séances), 25, 27, 28, 31, 36, 37, 42, 43 (règles du dernier chargement affichées), 44, 45 (journal par traitement), 47–48 (page Données publique, admin Données), 52, 53.
**Non repris, volontairement** : 3 (critère d'accélération : abandonné par la méthode V1 elle-même, aucune démonstration de son apport ; réintroduction possible si on la valide sur le suivi) ; 7 (pénalisation k : exposant non démontré) ; 51 (affichage du mot de passe : choix de sécurité, la réinitialisation passe par l'administrateur). Réglages du préfiltre de liquidité modifiables dans Administration › Réglages (43).
Relance manuelle limitée à l'analyse complète et au chargement du catalogue : les passages `tick` restent pilotés par le cron.
