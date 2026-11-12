# Reprise du nettoyage — 2026-11-12

Branche : `chore/frontend-cleanup-20261112`, départ `3ac8ca8`. Les modifications préexistantes de `app/routes/{alerts,explore,portfolios,tracking}.php`, `app/services/{explorer_library,ledger}.php` et le nouveau `portfolio_access.php` appartiennent à l'utilisateur ; ne pas les intégrer aux commits de nettoyage. Base locale et `private/` préservés.

Confirmé : `app.css` avait un rayon de carte redéfini (14 puis 16 px) et deux règles successives pour le champ/bouton de visibilité du mot de passe ; quatre pages d'authentification portaient les mêmes styles inline ; `mes-strategies.html` contenait un bloc CSS. `multiselect.js` n'est chargé par aucune page HTML mais un test le lit : suppression reportée. Les routes d'API sans appel littéral ne sont pas présumées mortes.

Structure retenue : variables et composants dans `app.css`, domaine dans sa feuille CSS, API et formats dans `app.js`, comportement de page dans ses scripts existants. Lot 1 : suppression des surcharges confirmées, déplacement du CSS statique HTML, mise à jour des versions de cache `app.css`. Aucun calcul ni contrat API modifié.

Référence : `make fast` a d'abord échoué car `pytest` manquait dans `.venv`. Après installation locale, 654 réussites et 6 échecs dans l'état de départ ; un échec sur l'architecture d'exécution, cinq sur les fausses lignes de prix des tests `scores_listing`. Ces fichiers ne sont pas touchés par le lot. Contrôle JS `node --check` sur tous les assets : OK ; `git diff --check` : OK. Parcours navigateur à compléter si Chromium devient disponible. Le serveur local PHP répond sur 127.0.0.1:8090.

À poursuivre : découpage prudent des gros blocs de `app.css`, revue des styles calculés dans les templates JS, vérification avec compte local et base. Ne supprimer un fichier qu'après contrôle de ses usages dynamiques et externes. Aucun push ni déploiement.
