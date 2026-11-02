# Journal des analyses

Chaque exécution est notée ici, y compris les échecs.

- Protocole figé (research/PROTOCOLE.md) avant tout résultat de ces analyses.
- Inventaire des données (cron temporaire, lecture seule) : 3000 titres (1553 actions, 1447 ETF), volumes 100 %, secteur absent.

## 2026-10-31 · exécution complète sur Hostinger (lecture seule)
- Panel : 510 993 lignes (titre × date), 410 dates (1993-02-12 → 2026-10-23), 3 000 titres, 2 667 classements de profils. Durée du calcul : environ 10 minutes.
- Six analyses exécutées (risk, horizons, candidates, deciles, ic, rank). Aucune hypothèse retirée ; les six candidates ont été écartées.
- Famille principale (10 tests, seuil p < 0,005) : seul le Momentum 6-1 est significatif (21 et 63 séances).
- Rapport : research/RAPPORT.md. Graphiques non produits à ce stade.

## 2026-11-02 · règles de sortie (research/PROTOCOLE_SORTIES.md)
- Exécution sur Hostinger, lecture seule (cron temporaire supprimé après lancement), commit 5c81eeb, 76 s, 1 448 sélections.
- Toutes les règles coûtent du rendement contre « conserver 126 séances » et réduisent le risque. Contre une durée fixe équivalente, seule « momentum 6-1 négatif » (Momentum) est nettement meilleure (+2,12 [+0,67 ; +3,63]) ; « sous la moyenne 50 j » (Rebond) +0,99 [+0,34 ; +1,75]. Détail : research/RESULTATS_SORTIES.md.
