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

Tailles partagées (jetons de `theme/tokens.css`, relevés à 40 px / 32 px sur mobile) : **contrôle standard 35 px** (`--control-h`), **contrôle compact 29 px** (`--control-h-sm`). Boutons, champs, sélecteurs multiples et onglets utilisent la première ; la variante compacte est toujours explicite (`.sm`). Aucune page ne définit la hauteur ou le remplissage d'un bouton, d'un champ ou d'un badge : `make css-check` échoue sinon.

| Composant | Classe | Variantes | Hauteur |
|---|---|---|---|
| Bouton | `.btn` | `.primary` `.danger` `.ghost` ; `.sm` compact ; `.icon` carré (+ `.sm`) | 35 / 29 px |
| Sélecteur de période | `.px-per button`, `.as-win button` | compact par construction (même géométrie que `.btn.sm`) | 29 px |
| Choix exclusif | `.seg` (+ `.as-seg` `.ct-seg` `.px-seg`) | actif : `.on` ou `aria-pressed` | 29 px |
| Onglets | `.tabs` (+ `.pf-nav` `.px-zones` `.sr-tabs`) | actif : `.on`, `.selected`, `aria-selected` | 35 px |
| Champ | `input` `select` `textarea` ; déclencheur `.ct-multi-trigger` | — | 35 px |
| Badge | `.badge` | `.ok .warn .caution .danger .info .accent`, `.outline`, `.sm` ; états métier `.as-pill`, `.ps-tag`, `.ac-badge`, `.ct-demo-badge` partagent la même base | 25 px (`.sm` 21 px) |
| Carte | `.card` | `.flush` `.tight` `.flat` `.inset` | — |
| Tableau | `table` | voir ci-dessous | — |
| Notification | `.toast` (`J.toast`) | `role="status"` | — |

**Tableaux.** Un seul socle (`components/tables.css`) : en-tête 10 px / graisse 800 / majuscules, cellules 11 px, séparateurs 1 px `--line`, survol `--halo-hover`, valeurs numériques tabulaires alignées à droite (`.num`), tri sur `th.sortable` / `aria-sort`, états vides `.empty`. Variantes explicites : **standard** (`table`), **dense** (`table.dense`, remplissage `--cell-pad-dense`), **financière** (`.px-t` : lignes cliquables, cellule identité `.ident`, gains `.pos` / `.neg`), **administration** (`table` standard dans `.table-wrap.tall` ou `.boxed`). Tableaux spécialisés conservés : matrice de performance et dynamique (`.pfd-table`, point thermique `--temp-1…7`, flèche de dynamique) et suivi des positions (`.psr-t`, jauge, carte sous 900 px) ; ils réutilisent les mêmes en-têtes et séparateurs.

**Couleurs sémantiques.** Hausse et gain `--ok`, baisse et perte `--danger`, avertissement `--warn`, réévaluation `--caution`, information `--info`. Échelle de température `--temp-1` (forte baisse) à `--temp-7` (forte hausse) pour la performance du cours et la jauge de suivi. Les palettes de séries de graphiques (`--series-*`, `--chart-*`) sont volontairement distinctes.

## Créer une nouvelle page sans réintroduire de styles

1. Balisage : `.card` / `.px-card` pour les blocs, `.btn` (+ variante) pour les actions, `table` pour les listes, `.badge` pour les statuts, `.seg` ou `.tabs` pour les choix. Ne pas inventer `.ma-page-bouton`.
2. CSS de page : uniquement la disposition (grille, flex, espacement, largeurs) dans `app/styles/layout/<page>.css`. Pas de couleur, de bordure, de hauteur ni de remplissage de composant.
3. Apparence propre au métier (visualisation, couleur d'état) : `app/styles/features/<page>.css`, avec des jetons.
4. Valeurs : uniquement l'échelle de `css_scale.py` (espacements, tailles, rayons, interlignes, points de rupture). Pas de `!important` hors des utilitaires déjà présents.
5. `make css-format css-build css-check`, puis `.venv/bin/python -m pytest tests/fast/test_css_scale.py tests/fast/test_css_components.py`, puis un contrôle visuel en clair et en sombre à 1440 et 390 px.

## Reste à faire

Styles `style="…"` générés par le JS (étape 8 de l'audit, environ 130 restants).
