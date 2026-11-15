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
| Cartes | `--card-pad --card-gap --panel-radius --panel-bg` |

Mobile (≤ 600 px) : `--control-h` 40 px, `--control-h-sm` 32 px, champs à 16 px (évite le zoom iOS). ≤ 600 px : `--card-pad` 14 px.

## Composants communs (tous dans `halo.css`)

Titres, kicker, boutons (`.btn`, `.primary`, `.ghost`, `.danger`, `.sm`, `.lg`, `.icon`), champs (`input`, `select`, `textarea`), cases et boutons radio natifs (`accent-color`), interrupteur `input.switch`, onglets `.tabs`, segments `.seg`, badges `.badge`, cartes `.card`, tableaux (`th`, `td`, `.table-wrap`), messages `.notice`, états `.empty`/`.spinner`, dialogues et menus.

## Échelles communes (espacements, textes, rayons, empilement)

Toutes les feuilles utilisent les mêmes valeurs ; les jetons sont définis une fois dans `halo.css` (`:root`) et vérifiés par `scripts/css_scale.py` (`python scripts/css_scale.py check`, test `tests/fast/test_css_scale.py`, CI).

| Famille | Jetons / valeurs |
|---|---|
| Espacements (margin, padding, gap) | `--sp-2 4 6 8 10 12 14 16 20 24 32 40 48` (px). Au-delà de 48 : largeur propre à une mise en page. Négatifs : marges de recouvrement uniquement ; `1px` : filet. |
| Texte | `--fs-10 11 12 13 14 15 16 18 20 24 28 32` (px, `html` = 14 px) |
| Interlignage | `--lh-none` 1 · `--lh-tight` 1,25 · `--lh-snug` 1,4 · `--lh-normal` 1,5 · `--lh-loose` 1,6 |
| Rayons | `--radius-4 8 12 16`, `--radius-pill` ; `--radius`, `--radius-sm`, `--control-radius`, `--panel-radius` en dérivent |
| Empilement | local 1 à 10 dans un composant ; global `--z-bar` 20 · `--z-header` 30 · `--z-pop` 50 · `--z-backdrop` 55 · `--z-drawer` 60 · `--z-fly` 80 · `--z-top` 1000 |
| Points de rupture | 380, 600, 760, 900, 1100, 1400 px (les `min-width` valent la limite + 1) ; les seuils JavaScript reprennent les mêmes valeurs |
| Bordures | 1, 2, 3, 4 px |
| Opacités atténuées | 0,5 · 0,7 · 0,85 (les voiles décoratifs < 0,3 sont conservés) |

Les égalités se résolvent vers la valeur supérieure. `python scripts/css_scale.py apply` convertit une valeur hors échelle.

### Rythme vertical des pages

Les blocs d'une page (en-tête, cartes, panneaux, tableaux, notices) sont séparés de `--sp-16` **par le conteneur seul** (`display: grid; gap: var(--sp-16)` sur `main.wrap`, `#page`, `#px-page`, `#main`, `.pf-panel`, `.pf-home`, `.bilan-layout`, `.tracking-layout`, `.as`, `.admin-flow`, `.admin-filter-form`, colonnes de `.ac-grid`). Les marges verticales des enfants directs sont neutralisées : ne pas poser de `mt-*`, `mb-*` ni de `margin` sur un bloc de page, ajouter le bloc suffit. Les sections verticales d'une carte utilisent `--card-gap` (12 px), porté par `.card-stack`, `.sr-card`, `.ps-card` et `.admin-filter-aside` ; les marges des enfants sont neutralisées. Utiliser `.card-stack` pour une nouvelle carte de sections. Les lignes d'actions, les grilles de mesures et les repères d'une jauge gardent leurs écarts métier : ne pas leur appliquer un espacement uniforme à l'aveugle.

### Mesure

`scripts/probe_layout.sh` (base jetable) rend les 30 vues réelles à 1280 et 390 px ; `--themes` ajoute le thème sombre (120 vues), `--only` limite les routes par expression régulière. Il mesure débordement horizontal, écarts entre blocs, valeurs réellement rendues. `--out`, `--compare` et `--shots` comparent deux états.

## Garde-fous

- `make css-check` : formatage Prettier 3.3.3 (`.prettierrc`) et `scripts/check_halo_css.py` : jetons uniques, `halo.css` dernière feuille, aucune couleur littérale hors `halo.css`, **aucune surcharge visuelle d'un composant commun dans une feuille de page**.
- Exceptions autorisées (liste `EXCEPTIONS` du script, avec raison) : colonnes figées de l'Explorateur (fond opaque), tableaux transformés en cartes sur mobile (bordures de ligne).
- `!important` : masquage `[hidden]`, réduction des animations et classes utilitaires (elles remplacent la priorité des anciens styles en ligne).
- Le remplacement d'un `style` par un `data-style` n'est pas une centralisation : les `data-style` restants (108) portent des valeurs calculées (couleurs de catégories ou de séries, largeurs, hauteurs) ou de la mise en page.

## Galerie et références visuelles

- `design/galerie.html` : tous les composants et états avec les feuilles réelles (hors `app/public` : le test `test_core_is_loaded_before_app_on_every_page` impose `core.js` sur toute page déployée).
- `make visual` compare les styles calculés de la galerie (clair/sombre, 1280/390 px) à `tests/visual/galerie.json`. `make visual` vérifie aussi les contrastes et toutes les classes utilitaires. Écart voulu : `make visual-update`, puis commit de la référence. Captures de revue : `tests/visual/out/` (ignorées par Git).
- Variables requises : `PLAYWRIGHT_MODULE` et `JIGO_CHROMIUM`. `GALLERY_URL` permet de servir la galerie par HTTP quand le navigateur interdit les URL `file:`. Les trois sondes acceptent cette variable. La capture attend `document.fonts.ready`, pour ne pas comparer aléatoirement une police de secours.

## Choix de design conservés

h3 à 15 px (la maquette est à 20 px) ; champs à 16 px sur mobile ; cases à cocher natives ; dégradé Halo sur toutes les cartes ; glyphe de tri à 18 px sur mobile.

## Contrastes

`tests/visual/contrasts.cjs` vérifie 196 paires clair/sombre calculées par Chromium : texte à 4,5:1 sur les surfaces, variantes sémantiques, navigation et extrémités du dégradé principal ; lignes et séries à 3:1 contre leur fond. Les animations sont neutralisées pendant la mesure. Ce contrat ne prétend pas mesurer chaque pixel ou les couleurs libres saisies par l'utilisateur.

Les couleurs de données sont distinctes des couleurs d'interface dans `halo.css` :
- `--series-1` à `--series-12` : séries du portefeuille, adaptées au thème. Les SVG et légendes utilisent les variables directement : changer le thème actualise aussi les graphiques déjà présents.
- `--chart-ma`, `--chart-ma2`, `--chart-level` : lignes d'analyse.
- `--gauge-*` : continuum rouge → vert fixe, indépendant du thème ; position des seuils toujours calculée par le moteur. Les niveaux sont nommés et chiffrés hors du dégradé : la couleur seule n'est pas une instruction financière.
- Catégories personnelles : couleurs de données conservées ; les pastilles restent accompagnées de leur libellé. Une couleur utilisateur arbitraire ne reçoit pas de garantie de contraste.

Space Grotesk est servie depuis `assets/fonts/`, avec sa licence OFL. Aucun appel à Google Fonts : la CSP du site n'autorise que les sources locales. Le test `test_stylesheets_only_reference_local_fonts_under_the_self_csp` protège ce contrat.

## Limites connues

Émulation mobile uniquement (pas d'appareil réel). Dialogues de création et de renommage de stratégie vérifiés par les tests e2e, pas à l'écran.

Le clavier du dialogue partagé (tabulation, fond inerte, Échap, retour au déclencheur) et des onglets personnels est couvert dans `tests/e2e/keyboard.cjs`, en quatre contextes. Cela ne constitue pas une certification d'accessibilité de tous les parcours.
