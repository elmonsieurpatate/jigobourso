# Journal des analyses

Chaque exécution est notée ici, y compris les échecs.

- Protocole figé (research/PROTOCOLE.md) avant tout résultat de ces analyses.
- Inventaire des données (cron temporaire, lecture seule) : 3000 titres (1553 actions, 1447 ETF), volumes 100 %, secteur absent.

## 2026-10-31 · exécution complète sur Hostinger (lecture seule)
- Panel : 510 993 lignes (titre × date), 410 dates (1993-02-12 → 2026-10-23), 3 000 titres, 2 667 classements de profils. Durée du calcul : environ 10 minutes.
- Six analyses exécutées (risk, horizons, candidates, deciles, ic, rank). Aucune hypothèse retirée ; les six candidates ont été écartées.
- Famille principale (10 tests, seuil p < 0,005) : seul le Momentum 6-1 est significatif (21 et 63 séances).
- Rapport : research/RAPPORT.md. Graphiques non produits à ce stade.

## 2026-11-01 · score appris (apprentissage automatique)
- Protocole figé avant tout résultat : research/PROTOCOLE_APPRENTISSAGE.md (2 modèles ridge sur rangs, fenêtre croissante, écart de 2 dates, réapprentissage tous les 12 dates, Bonferroni sur 2).
- Programme : scripts/research_ml.py ; tâche : research/jobs/apprentissage.sh.
- 2026-11-02 · exécution sur Hostinger (lecture seule, cron temporaire supprimé après lancement) : commit ee0976c, Python 3.9.25, 26 s. 348 dates de décision (dès 1998-03-11), 30 réapprentissages.
- Résultat (usd_1M) : M1 −0,56 point par période contre le Momentum 6-1 [−1,22 ; +0,08], p = 0,092 ; M2 −0,60 [−1,29 ; +0,09], p = 0,091. CVaR 95 % −15,4 / −15,2 contre −18,0 ; rotation 0,78 contre 0,46. IC moyen +0,013 / +0,016 contre +0,006 pour le momentum 6-1.
- Verdict réglé d'avance : « réduit le risque mais coûte du rendement » pour les deux modèles, dans les deux scénarios. Aucun réglage modifié après lecture. Détail : research/RESULTATS_APPRENTISSAGE.md.
