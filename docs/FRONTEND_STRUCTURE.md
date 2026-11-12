# Frontend : structure et conventions

`app/public/*.html` garde les routes et l'ordre de chargement actuels. `assets/app.css` contient les variables des thèmes et les composants partagés. Les CSS de domaine (`pf.css`, `strategies-ui.css`, `help.css`, etc.) portent les règles propres aux pages qui les chargent. Éviter les blocs `<style>` et les attributs `style` statiques dans le HTML. Garder les valeurs réellement calculées en JavaScript près du composant qui les produit.

`assets/app.js` expose `J` : API, formats et navigation. Les autres scripts sont chargés dans l'ordre de dépendance indiqué dans chaque page ; leurs fonctions publiques existantes restent disponibles. Ne déplacer une responsabilité que lorsque tous ses consommateurs et chargements dynamiques ont été vérifiés. Les routes et la logique financière restent dans PHP/Python.

Pour une modification visuelle, changer d'abord la variable ou le composant partagé ; ajouter une règle de page seulement si le besoin est propre à cette page. Tester les deux thèmes, 390 px, clavier, états vide/erreur et le cache d'asset (`?v=`). Pour une suppression, chercher les références dans HTML, JS, PHP et tests avant de retirer le fichier.

## Versions des fichiers CSS et JS

Toutes les pages référencent leurs fichiers avec le même marqueur : `assets/app.js?v=__BUILD__`. Ne jamais écrire une version à la main (`?v=2026…`) : `ops/deploy.sh` remplace `__BUILD__` par l'identifiant du déploiement (date UTC `AAAAMMJJhhmm`) dans toutes les pages, puis vérifie qu'aucun marqueur ne reste. En local le marqueur est servi tel quel, ce qui est sans effet.

Un fichier ajouté à une page prend donc `?v=__BUILD__`, comme les autres (le script `app.js` charge `passwords.js` avec la même chaîne de version). `tests/fast/test_asset_versions.py` vérifie que chaque référence porte le marqueur et que chaque fichier existe.

Cache (`app/public/.htaccess`) : une ressource avec `?v=` se garde un an (`immutable`), les pages HTML se revalident à chaque visite (`no-cache`), les images, SVG et polices se gardent un mois. Les réponses JSON de l'API ne reçoivent aucune règle `Expires`.
