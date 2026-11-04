# Explorer V4 — Correctifs techniques P0 et validation

> Document de la phase préalable/P0. La clarification utilisateur autorise désormais
> l’implémentation avec paramètres provisoires. Voir la version intégrée et les
> défauts semaine/mois dans [README_EXPLORER_V4.md](README_EXPLORER_V4.md).

Branche : `feature/explorer-v4-growth`, base applicative `8048982`.
Commit technique : `e3891fe`.
Ce lot ne constitue pas la livraison complète de V4. Les formules et paramètres
fonctionnels restent provisoires, dans l’attente de l’accord utilisateur.

## Correctifs

| Point | Cause | Correction |
| --- | --- | --- |
| Momentum 3/127 | Les deux bornes suffisaient au calcul ; la couverture n’était qu’un avertissement | Exiger chaque clôture du calendrier requis ; contrôler aussi la couverture quand une valeur Momentum stockée est réutilisée |
| MA200 sur 55 points | Une tranche trop courte était quand même divisée par 200 | Taille exacte, unicité des dates, cours positifs et finis pour chaque moyenne ; frontière précédente corrigée à 205 points |
| Fiche historique | Fenêtre technique réduite à 55 selon version de configuration | Utiliser les 205 dates techniques pour toutes les versions, sans modifier les profils |
| Volumes historiques | Présence d’une colonne confondue avec alimentation ; validation limitée à non-null | Garder indisponible si incomplet ; refuser négatif/non-fini ; exposer source, observés, attendus et couverture ; zéro reste une valeur connue |
| Sous-unités FX | Recherche FX spécialisée GBP dans le chemin historique | Réutiliser `SUBUNITS` du moteur commun pour GBp/GBX, ZAc et ILA |
| Cache ancien | Verdicts produits avec les anciennes règles | Révision `CACHE_FORMAT` 8 → 9 ; aucune suppression de données privées |
| Sérialisation Momentum | Dans le chemin par dictionnaire, DECIMAL MariaDB restait non sérialisable dans les contributions | Conversion numérique au même point d’entrée que les autres mesures ; test réel via service et cache |

Pour les volumes, le choix de ce lot est **indisponibilité explicite**, pas une
nouvelle collecte. Aucun volume historique n’est fabriqué à partir de la moyenne
cotée Yahoo. Les mesures déjà connues et valides restent calculables.

L’exigence complète de Momentum concerne les 127/253 cours attendus, même si le
rendement ignore le dernier mois. Les fonctions ne modifient pas leurs entrées.
Les sept profils historiques et leurs configurations restent inchangés ; la
correction porte sur la qualité des données servant à leurs calculs.

## Tests exécutés

Reproduction avant correction : 32 échecs et quatre réussites dans le nouveau
fichier de tests P0. Le test de bout en bout sur base a ensuite révélé le problème
DECIMAL ; il a été corrigé avant la nouvelle validation.

- Tests rapides, avec les exécutables PHP existants dans le PATH : **458 réussis**,
  aucun ignoré ; un avertissement de dépréciation dans `exchange_calendars`.
- Intégration sur MariaDB jetable : **200 réussis**, aucun échec. 964 avertissements
  de dépréciation issus des usages existants de `datetime.utcnow()` et de la
  dépendance de calendrier ; ils ne sont pas présentés comme des erreurs de calcul.
- Compilation Python et `git diff --check` : réussis.
- `scripts/migrate.py --check` : 11 migrations existantes admissibles ; aucune
  migration ajoutée ou appliquée à une base réelle par ce lot.
- Banc de proposition : cinq tests de propriétés, sans validation des coefficients
  et sans intégration de ces formules dans l’application.

Fichiers de non-régression :

- `tests/fast/test_explorer_v4_readiness.py` : 3/127, bornes seules, trous internes,
  mois exclu incomplet, Momentum 6/12, valeur stockée, MA aux frontières
  200/205/206, données invalides, volume zéro/manquant et absence de mutation.
- `tests/integ/test_explorer_v4_readiness.py` : stockage réel et cache,
  fiche historique, collecte sans volumes, conversion des quatre sous-unités.

Commandes de référence :

```bash
make fast
make integ
.venv/bin/python -m scripts.preview_growth_v4
.venv/bin/python scripts/migrate.py --check
```

L’environnement cloud utilise les exécutables locaux existants de
`/workspace/jigo-tools` et la base jetable `jigobourso_it`, sur `127.0.0.1:33307`.
Les tests n’utilisent ni le serveur Hostinger ni ses données. Le refus initial
des sockets dans le bac à sable a été résolu en exécutant ces tests avec l’accès
local nécessaire ; aucun contournement de la politique réseau externe.

## Migration et retour arrière du lot P0

**Procédure documentaire uniquement : aucune exécution en production autorisée.**

1. Examiner et valider les commits sur la branche dédiée. Aucun changement de
   schéma ou de configuration de déploiement n’est nécessaire pour ce lot P0.
2. Si un futur déploiement est expressément autorisé, sauvegarder la base et
   l’artefact précédent selon la procédure existante.
3. Après installation autorisée, recalculer les mesures via le traitement
   `metrics` existant : le nouveau code ne réécrit pas spontanément les anciennes
   valeurs de `series_state`. Planifier ce recalcul avant validation des résultats.
4. Les nouveaux verdicts sont isolés par la version de cache ; ne pas annoncer
   que changer uniquement le code corrige toutes les mesures stockées.
5. Pour retour arrière, restaurer l’artefact précédent ou annuler le commit
   technique, puis recalculer explicitement les mesures avec sa version si
   nécessaire. Aucune suppression de stratégies, transactions ou réglages.

Les migrations d’archivage, l’administration, les catégories et la nouvelle UI
V4 restent à réaliser après arbitrage des paramètres. Il n’existe donc pas
encore de migration complète V4 à appliquer ou de capture d’une nouvelle UI
livrée. Aucun test navigateur de la nouvelle interface n’est revendiqué.
