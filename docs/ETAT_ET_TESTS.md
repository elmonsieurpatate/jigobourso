# État du développement et validations restantes (28/10/2026)

## Fait en local (V2 isolée, non déployé depuis la refonte « catalogue manuel »)
- Parcours manuel : Import FinanceDatabase → Filtrage → Import Yahoo → Filtrage Yahoo → catalogue final → « Importer / mettre à jour les historiques » (page Yahoo).
- Cron limité à l'entretien (`daily:`, `intraday:`, `maintenance`) du catalogue final + titres détenus ; jamais d'import ni de filtre. État du cron honnête (seul un vrai passage du cron compte).
- Places de cotation libres (toutes celles des données importées), filtre de catégories optionnel.
- Pages admin : FinanceDatabase, Yahoo, Actions / ETF, Cron, Journaux, Utilisateurs, Réglages.
- Historiques sans retéléchargement inutile (`daily_plan`, `intraday_plan`), sans doublon.

## Validations déjà faites (ne pas rejouer sans changement des fichiers concernés)
- `make fast` : 52 verts. `make integ` : 33 verts, dont `tests/integ/test_catalogue_flow.py` (parcours complet avec faux Yahoo : ordre des étapes, pas de retéléchargement au 2e passage, cron sans effet sur le catalogue, places libres, motifs d'exclusion).
- Données réelles en dev : import 153 495 lignes (22 s), filtrage (46 s).
- Navigateur admin (`tests/e2e/admin.mjs`) : toutes les vérifications passées sauf la comparaison « avant/après » du seuil Yahoo qui dépendait d'un état laissé par un essai précédent (test rendu robuste côté base, pas côté code).

## Reste à faire
1. UN parcours navigateur global final : `tests/e2e/smoke.mjs` (site général, ~3 min) puis `tests/e2e/admin.mjs` (~2,5 min), une seule fois, chacun lancé seul.
2. Test réel du bouton « Importer / mettre à jour les historiques » avec le vrai Yahoo : impossible dans le bac à sable (pas de réseau) ; à faire au premier usage en production après déploiement.
3. Déploiement en production : UNIQUEMENT sur accord explicite. La prod a encore la version précédente de l'admin (nouveaux types de jobs, nouveau `tick`, nouvelles pages à copier ; les 3 tables sont déjà créées). Après copie : lancer « Importer FinanceDatabase » puis « Filtrer » depuis l'admin.
4. Point connu : la page Actions / ETF avec le filtre « dans mon catalogue » prend ~9 s sur 153 000 lignes (à optimiser si gênant).

## Méthode de validation
Tests rapides (fonctions, API, traitements) d'abord ; navigateur ciblé seulement pour l'interactif ; jamais deux tests lourds en parallèle sur la même base ; un échec = correction ciblée puis relance du seul test concerné.
