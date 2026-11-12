# Design system : comment changer l'apparence

Trois fichiers communs, chargés dans cet ordre sur toutes les pages, puis le CSS propre à la page.

| Fichier | Rôle | Quand le modifier |
|---|---|---|
| `assets/tokens.css` | Variables : couleurs (clair et sombre), rayons, ombres, espacements `--sp-*`, polices | Pour changer la couleur de marque, les arrondis, la police, les teintes ok/danger/warn/info |
| `assets/base.css` | Mise en page générale : en-tête, menu latéral, titres, formulaires, grilles | Pour changer la structure de l'application |
| `assets/components.css` | Composants partagés : `.btn`, `.card`, `table`, `.badge`, `.tabs`, `.seg`, `.toast`, utilitaires d'espacement | Pour changer l'allure d'un type d'élément partout à la fois |
| `assets/<page>.css` | Styles propres à une page (`explorer.css`, `filtres.css`, `plan-suivi.css`, `pf.css`…) | Seulement pour ce qui n'existe que sur cette page |

## Règles

- **Aucune couleur écrite en dur** (`#abc`, `rgb(…)`) hors de `tokens.css` : toujours `var(--…)`. Pour une nouvelle teinte, créer le jeton (avec sa valeur sombre) dans `tokens.css`.
- **Un composant, une classe.** Variantes combinables : `.btn.primary.sm`, `.badge.ok.outline`, `.card.flush`. Ne pas recréer de `.ma-page-btn` : utiliser `.btn`.
- Thème : `theme-init.js` pose `data-theme="light|dark"` avant le premier affichage (valeur enregistrée, sinon réglage du système). Le bouton lune/soleil de l'en-tête bascule et mémorise le choix.
- Pour tester un changement : parcourir les pages en clair et en sombre, en 1280 px et 390 px.

## Composants

- **Bouton** `.btn` : `.primary`, `.danger`, `.ghost`, taille `.sm`, carré `.icon` (+ `.sm`).
- **Carte** `.card` : `.flush` (sans padding), `.tight`, `.flat` (sans ombre), `.inset` (panneau interne grisé).
- **Tableau** `table` + `.dense` ; conteneur `.table-wrap` avec `.tall` (hauteur max, en-tête collant) et `.boxed` (cadre).
- **Badge** `.badge` : `.ok .warn .danger .info .accent`, `.outline`, `.sm` (remplace tag, chip, pill).
- **Onglets** `.tabs` (soulignés) et **segments** `.seg` (choix exclusif). Actif : `.on`, `.selected` ou `aria-selected` / `aria-pressed`.
- **Notification** `.toast` (`J.toast`, `#ct-feedback`, `#ac-feedback`), `role="status"`.

## Reste à faire

Styles `style="…"` générés par le JS (étape 8 de l'audit, environ 130 restants).
