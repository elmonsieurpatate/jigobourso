# Design Halo — où modifier quoi

Référence visuelle : `design-demos/terminal-ultraviolet.html`, variante Halo (clair et sombre).

## Règle d'or

`app/public/assets/halo.css` est la **seule** source des jetons et des composants communs. Les feuilles de page (`explorer.css`, `pf.css`, `filtres.css`, `help.css`, `admin-*.css`, `plan-suivi.css`, `splits.css`, `strategies-ui.css`) ne gardent que la mise en page (grille, position, largeurs, défilement) et les valeurs réellement calculées. `halo.css` est toujours chargée en dernier.

`base.css` fournit le reset, la structure de l'application et les utilitaires. Les couleurs transparentes des ombres et des graphiques restent des cas particuliers. `scripts/check_halo_css.py` ne remplace pas la comparaison visuelle des pages et des états dynamiques.

## Modifier une valeur commune

| Pour changer… | Variable dans `halo.css` (`:root`, puis bloc sombre) |
|---|---|
| Palette, fonds, lignes, accent, états ok/avert./danger | `--bg --surface --surface-2 --line --text --muted --accent --ok --warn --danger` (+ `-soft`, `-ink`) |
| Titres | `--h1-size --h1-weight --h1-tracking --h1-leading`, `--h2-size`, `--h3-size`, `--h4-size` |
| Texte | `--text-sm --kicker-size --label-size` |
| Champs et boutons | `--control-h --control-h-sm --control-radius --control-size --control-size-mobile --btn-size --btn-size-sm --btn-pad --btn-pad-sm` |
| Cases, onglets, segments | `--check-size --tab-size --tab-pad --seg-size --seg-pad` |
| Tableaux et badges | `--th-size --td-size --cell-pad --badge-size --badge-pad` |
| Cartes | `--card-pad --panel-radius --panel-bg` |

Mobile (≤ 700 px) : `--control-h` 40 px, `--control-h-sm` 32 px, champs à 16 px (évite le zoom iOS). ≤ 640 px : `--card-pad` 14 px.

## Composants communs (tous dans `halo.css`)

Titres, kicker, boutons (`.btn`, `.primary`, `.ghost`, `.danger`, `.sm`, `.lg`, `.icon`), champs (`input`, `select`, `textarea`), cases et boutons radio natifs (`accent-color`), interrupteur `input.switch`, onglets `.tabs`, segments `.seg`, badges `.badge`, cartes `.card`, tableaux (`th`, `td`, `.table-wrap`), messages `.notice`, états `.empty`/`.spinner`, dialogues et menus.

## Garde-fous

- `make css-check` : formatage Prettier 3.3.3 (`.prettierrc`) et `scripts/check_halo_css.py` : jetons uniques, `halo.css` dernière feuille, aucune couleur littérale hors `halo.css`, **aucune surcharge visuelle d'un composant commun dans une feuille de page**.
- Exceptions autorisées (liste `EXCEPTIONS` du script, avec raison) : colonnes figées de l'Explorateur (fond opaque), tableaux transformés en cartes sur mobile (bordures de ligne).
- `!important` : 2 usages justifiés (`[hidden]`, réduction des animations).
- Le remplacement d'un `style` par un `data-style` n'est pas une centralisation : les `data-style` restants (108) portent des valeurs calculées (couleurs de catégories ou de séries, largeurs, hauteurs) ou de la mise en page.

## Galerie et références visuelles

- `design/galerie.html` : tous les composants et états avec les feuilles réelles (hors `app/public` : le test `test_core_is_loaded_before_app_on_every_page` impose `core.js` sur toute page déployée).
- `make visual` compare les styles calculés de la galerie (clair/sombre, 1280/390 px) à `tests/visual/galerie.json`. Écart voulu : `make visual-update`, puis commit de la référence. Captures de revue : `tests/visual/out/` (ignorées par Git).
- Variables requises : `PLAYWRIGHT_MODULE` et `JIGO_CHROMIUM`.

## Choix de design conservés

h3 à 15 px (la maquette est à 20 px) ; champs à 16 px sur mobile ; cases à cocher natives ; dégradé Halo sur toutes les cartes ; glyphe de tri à 18 px sur mobile.

## Contrastes

Texte atténué et couleurs d'état du thème clair assombris (`--muted` #596988, `--accent` #4963ae, `--ok` #27726a, `--warn` #8c6130, `--danger` #a5556c) pour atteindre 4,5:1 sur le fond de page. Mesure automatique sur 6 pages ; les fonds en dégradé (boutons principaux, puces) ne sont pas résolus par la mesure et ont été contrôlés à l'œil.

## Limites connues

Émulation mobile uniquement (pas d'appareil réel). Dialogues de création et de renommage de stratégie vérifiés par les tests e2e, pas à l'écran.
