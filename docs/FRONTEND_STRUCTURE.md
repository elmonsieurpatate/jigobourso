# Frontend : structure et conventions

`app/public/*.html` garde les routes et l'ordre de chargement actuels. `assets/app.css` contient les variables des thèmes et les composants partagés. Les CSS de domaine (`pf.css`, `strategies-ui.css`, `help.css`, etc.) portent les règles propres aux pages qui les chargent. Éviter les blocs `<style>` et les attributs `style` statiques dans le HTML. Garder les valeurs réellement calculées en JavaScript près du composant qui les produit.

`assets/app.js` expose `J` : API, formats et navigation. Les autres scripts sont chargés dans l'ordre de dépendance indiqué dans chaque page ; leurs fonctions publiques existantes restent disponibles. Ne déplacer une responsabilité que lorsque tous ses consommateurs et chargements dynamiques ont été vérifiés. Les routes et la logique financière restent dans PHP/Python.

Pour une modification visuelle, changer d'abord la variable ou le composant partagé ; ajouter une règle de page seulement si le besoin est propre à cette page. Tester les deux thèmes, 390 px, clavier, états vide/erreur et le cache d'asset (`?v=`). Pour une suppression, chercher les références dans HTML, JS, PHP et tests avant de retirer le fichier.
