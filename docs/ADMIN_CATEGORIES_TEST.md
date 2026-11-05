> La persistance PHP/MariaDB est maintenant implémentée : voir [FILTRES_PERSISTANCE.md](FILTRES_PERSISTANCE.md). Les descriptions de stockage en mémoire ci-dessous concernent uniquement l’export hors ligne historique.

# Administration — Filtres et catégories (prototype statique)

Page : `app/public/admin-categories-test.html`, menu **Administration → Filtres et catégories · test**, sur la branche de reprise. Aucun déploiement ni écriture serveur.

## Présentation

Sélecteur unique de filtre, activation locale, badge éditable/non éditable, présentation avec icône, description et unité, onglets Catégories/Informations. Tableau compact avec couleurs, plages de valeurs, explications courtes, statut et actions. Le bouton Réordonner révèle les flèches de déplacement utilisables au clavier. Interface adaptée aux écrans étroits et aux thèmes clair/sombre.

Le catalogue est fixé à **13 filtres : 9 avec catégories éditables et 4 issus des métadonnées**. Il n’est pas possible de créer ou supprimer un indicateur.

| Filtre éditable | Mesures illustrées / unité |
|---|---|
| Volatilité | Volatilité quotidienne, %/séance |
| Liquidité | Montant historique ou montant coté Yahoo (sources distinctes), €/jour |
| Volume moyen échangé | Volume historique, titres/séance |
| Séances positives | Proportion de séances en hausse, affichée en % |
| Pics de hausse / baisse | Meilleure et pire séances séparées, en % ; la pire conserve son signe |
| Concentration des gains | Trois définitions distinctes : meilleure hausse log / hausses positives log ; meilleure hausse simple / gain net simple ; meilleure hausse log / gain net log |
| Drawdown maximal | Amplitude positive du recul maximal, % |
| Rendements par horizon | Catégories propres aux horizons semaine/mois/trimestre |
| Qualité des données | Continuité, fraîcheur (états) et couverture (%) séparées |

| Filtre non éditable | Provenance |
|---|---|
| Pays | Pays associé au titre |
| Secteur | Classification sectorielle du titre |
| Marché / Place | Place de cotation |
| Type d’actif | Type fourni par le catalogue : action, ETF, OPCVM, etc. |

Les quatre derniers présentent des **exemples fictifs en lecture seule** : aucun ajout, édition, suppression, réordonnancement, seuil ou couleur à configurer. L’activation reste un réglage simulé indépendant pour chacun des 13 filtres ; elle conserve les catégories et n’a aucun effet sur l’Explorer réel.

## Modèle de démonstration

`admin-categories-demo.js` contient le catalogue embarqué. Les mesures dérivent de l’instantané V4 déjà présent dans le prototype, regroupées selon les neuf noms demandés. Des seuils et couleurs illustratifs restent des propositions de maquette, pas des paramètres métier validés. La volatilité contient six catégories, dont Inconnue ; sa plage initiale est subdivisée pour illustrer Très faible/Faible, sans convertir arbitrairement une volatilité quotidienne en volatilité annualisée. Les proportions de séances positives et de couverture sont affichées en % (multiplication par 100 des valeurs de l’instantané dans cette maquette seulement).

Un sous-sélecteur distingue les mesures ou horizons lorsqu’un filtre en comporte plusieurs. Chaque mesure conserve ses catégories propres : modifier la semaine n’affecte pas le mois ; les trois définitions de concentration ne sont jamais fusionnées. L’efficacité du chemin et le recul actuel ne deviennent pas des filtres supplémentaires de cette liste de 13.

Les catégories ont nom, explication courte (180 caractères maximum), couleur, activation et bornes/valeurs. L’identité de l’indicateur et son unité restent en lecture seule. Aucun changement du moteur, des calculs ou des stratégies.

## Interactions et validation

Même formulaire inline pour ajouter ou modifier, Annuler abandonne le brouillon, Enregistrer valide puis met à jour le tableau. Supprimer demande confirmation. Changer de filtre ou de mesure protège un brouillon modifié par une confirmation. Le réordonnancement affecte seulement l’affichage, jamais les bornes.

Les intervalles initiaux suivent la convention basse exclue/haute incluse de l’instantané ; les quatre variantes sont sélectionnables. Une borne absente représente l’infini et reste ouverte. Les erreurs proches des champs bloquent les noms vides/dupliqués, valeurs non numériques, plages inversées/vides, chevauchements actifs (y compris un point partagé inclus deux fois), couleurs invalides et doublons d’Inconnue. Les trous de couverture et l’absence d’une Inconnue active sont signalés sans empêcher la sauvegarde locale.

Les états de qualité/fraîcheur s’éditent par choix de valeurs, sans imposer de bornes numériques. L’Inconnue n’a ni borne ni valeur ; elle reste distincte de zéro. Les catégories inactives ne participent pas à la couverture active. Supprimer ou désactiver une catégorie peut donc créer un avertissement.

Toutes les modifications sont en mémoire de cette page : **recharger rétablit la démonstration**. Aucune intégration à Explorer, à sa configuration de catégories ou aux données réelles à cette étape. La page Filtres par défaut reste hors périmètre.

## Tests et export autonome

```sh
node tests/e2e/admin-categories-model.cjs
# Servir app/public sur 127.0.0.1:18121 :
node tests/e2e/admin-categories-test.cjs
python3 scripts/export_classement_test.py --page admin-categories-test.html /tmp/administration-filtres-v2.html
```

Le test du modèle vérifie le catalogue 13/9/4, les intervalles, états, inconnues, explications et l’indépendance des horizons. Le test navigateur couvre clair/sombre en 1600/1280/390/375 px, les actions de catégories, les quatre filtres verrouillés, l’activation, les onglets, les sous-mesures, les brouillons, le rechargement et les débordements. Seules les lectures simulées de session/navigation sont autorisées ; aucune connexion DB ni API métier.

L’export HTML embarque une session administrateur fictive hors ligne. La page hébergée conserve `J.init(...,{admin:true})`. Aucun contournement d’autorisation serveur, aucune nouvelle API d’administration. Les interfaces Simple/Expert et le classement fictif sont inchangés.
