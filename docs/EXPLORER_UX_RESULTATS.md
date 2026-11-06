# Explorer test — classement en premier

Implémentation de la direction validée : classement immédiatement après la recherche et les commandes compactes. Branche `feature/explorer-ux-results-first`. La page historique `index.html`, son moteur et les stratégies ne changent pas.

## Organisation livrée

- Consultation : contexte de stratégie et périodes, recherche dans les exemples, Réglages, Filtres, tri et Options. Aucun formulaire permanent au-dessus du classement.
- Mobile : quatre colonnes essentielles, Titre / Score / Courbe 1M / Variation 1J. Pas de défilement horizontal dans cette vue. Les colonnes personnalisées restent disponibles dans Options → Toutes mes colonnes sur mobile.
- Ordinateur : tableau détaillé avec score et courbe prioritaires ; les choix de colonnes sont conservés.
- Un seul dialogue de configuration : panneau latéral sur ordinateur, plein écran sur téléphone. Stratégie et Filtres partagent cette surface ; aucun second éditeur de filtres.
- Simple/Expert synchronisés, toutes les périodes et les groupes ET/OU conservés. Les périodes inactives et les outils secondaires sont repliés. Une combinaison experte non représentable en Simple n’est ni réinterprétée ni supprimée.
- Annuler restitue les réglages appliqués ; Fermer conserve le brouillon en mémoire et le signale ; Appliquer enregistre les choix dans le document local existant. Les résultats fictifs ne sont pas recalculés par la stratégie.
- Les sélections de filtres sont désormais validées par Appliquer ; leurs identifiants, défauts administrateur, priorités locales par utilisateur et archives restent conservés. Aucune nouvelle table ni clé de stockage parallèle.
- La recherche locale porte sur les données fictives disponibles, par nom et symbole. Un état sans résultat permet de réinitialiser la recherche sans effacer les préférences de filtre.
- Les catégories affichent leurs bornes en français, sans notation d’intervalle permanente. Les bornes et unités stockées ne changent pas.
- Détails accessibles en touchant le titre. Dialogues nommés, retour de focus et de défilement ; commandes atteignables sur viewport réduit. Le fond est verrouillé pendant la configuration pour empêcher ses variations de hauteur de déplacer le pied d’actions.

## Conventions préservées

Le jeu actuel fournit une variation du jour et une courbe fictive sur un mois. La réalisation les nomme **1J** et **1M** ; elle ne transforme pas la variation du jour en rendement mensuel pour reproduire les images de conception. Aucun cours ni score n’est inventé en plus du jeu fictif existant.

Les treize filtres chargent toujours `explorer/secondary-filters`. Le filtrage des résultats de marché reste non raccordé dans cette page de test ; le texte du panneau l’indique. Aucun appel au moteur de classement n’a été ajouté.

La validation du chargement local accepte aussi les pentes finies définies dans l’éditeur Expert hors plage des curseurs simples : elles restent conservées, avec curseurs verrouillés quand la combinaison ne peut pas être représentée. Cela évite une réinitialisation de l’ensemble du profil au rechargement.

## Vérifications exécutées

| Vérification | Résultat |
|---|---|
| `make fast` | 445 tests réussis ; un avertissement de calendrier préexistant |
| `classement-test-mobile.cjs` | 375/390/430/1280 px, clair/sombre : classement dès le premier écran, score/courbe ensemble, recherche, modes, Annuler/Fermer/Appliquer, préférences au rechargement, vue complète, dialogues et pied d’actions sur viewport de 430 px |
| `classement-test-ranking.cjs` | 1440/1280/390/375 px, clair/sombre : tri, pagination, valeurs manquantes, colonnes, détails, état vide, scores et rangs inchangés |
| `classement-test.cjs` | 1440/1280/1024/850/768/390/375 px : règles, groupes imbriqués ET/OU, périodes, sauvegarde et rechargement, absence de débordement et d’appel au moteur |
| `classement-test-secondary.cjs` | 1440/1024/390/375 px, clair/sombre : configuration administrateur, listes, recherche, inconnus, réinitialisation, clavier, aucun éditeur de seuils dans Explorer |
| `scripts/test_secondary_filters.sh` | PHP/MariaDB réels sur base jetable : migrations, activation, catégories, défauts, préférences par utilisateur, restauration, droits, conflits ; tests navigateur ci-dessus intégrés au scénario |
| Export autonome | 13 filtres, 6 catégories de volatilité, dialogue et score visibles ; aucune requête API ni erreur JavaScript |
| Contrôles de source | Syntaxe JS/Python et `git diff --check` réussis ; moteur, schéma, services, routes, workflow et Explorer historique inchangés |

Mesures sur fenêtre de 844 px de haut : premier titre à environ **316 px sur mobile**, contre un bloc de classement auparavant situé à 1 274 px ; premier titre à environ **313 px sur ordinateur**. Lignes mobiles d’environ 61 px. Les tests vérifient au moins six titres complets à 844 px et quatre à 650 px de hauteur utile, avec score et courbe visibles.

Les captures sont celles de la réalisation rendue dans Chromium, pas les images générées de conception. Elles sont disponibles dans `/workspace/explorer-ux-implementation/`, avec `explorer-apercu.html`, aperçu autonome sans backend. L’export utilise les propositions de catégories du dépôt, pas les personnalisations d’une base de production.

### Limites explicites

- Safari iPhone réel n’a pas été exécuté : WebKit était indisponible et son téléchargement bloqué par la politique réseau. Les tests tactiles sont des contextes Chromium mobiles ; ils ne prouvent pas le comportement du clavier ni des barres Safari.
- La hauteur disponible est gérée par le viewport dynamique et `visualViewport` lorsqu’il existe, avec zone sûre inférieure. La recette sur appareil réel reste nécessaire avant d’annoncer une validation iPhone.
- Le classement demeure fictif et indépendant des réglages de sélection. Aucun raccordement financier, calcul, seuil ou score n’est modifié par cette refonte.
- Aucun déploiement de cette réalisation n’a été lancé. La livraison est sur la branche de travail pour revue, conformément à la demande de validation avant publication.

## Fichiers concernés

- `app/public/classement-test.html`
- `app/public/assets/classement-test.css`
- `app/public/assets/classement-test.js`
- `app/public/assets/classement-test-filters.js` (libellés de bornes uniquement)
- `scripts/export_classement_test.py` (aperçu autonome cohérent avec les treize filtres)
- Tests navigateur `classement-test-mobile`, `classement-test-ranking`, `classement-test-secondary`, `classement-test`, `secondary-persistence-browser` et leur helper de navigation `classement-test-harness.cjs`.
