# Frontend : structure et conventions

`app/public/*.html` garde les routes. Chaque page charge `theme-init.js` (thème avant affichage), puis `base.css`, le CSS de la page, et **`halo.css` en dernier** (source unique des jetons et composants ; voir [DESIGN_HALO.md](DESIGN_HALO.md)). Les CSS de page ne portent que la mise en page. Éviter les blocs `<style>` et les attributs `style` statiques dans le HTML. Garder les valeurs réellement calculées en JavaScript près du composant qui les produit.

`assets/app.js` expose `J` : API, formats et navigation. Les autres scripts sont chargés dans l'ordre de dépendance indiqué dans chaque page ; leurs fonctions publiques existantes restent disponibles. Ne déplacer une responsabilité que lorsque tous ses consommateurs et chargements dynamiques ont été vérifiés. Les routes et la logique financière restent dans PHP/Python.

Pour une modification visuelle, changer d'abord la variable ou le composant partagé ; ajouter une règle de page seulement si le besoin est propre à cette page. Tester les deux thèmes, 390 px, clavier, états vide/erreur et le cache d'asset (`?v=`). Pour une suppression, chercher les références dans HTML, JS, PHP et tests avant de retirer le fichier.

## Sources CSS et fichiers servis

Les fichiers de `app/public/assets/*.css` sont générés. Ne pas les corriger à la main.
Les sources lisibles et le manifeste de construction sont dans `app/styles/` :

- `theme/tokens.css` : palette, polices et variables communes ;
- `components/` : apparence et dimensions des composants partagés, par famille ;
- `features/` : apparence réellement propre à un métier ;
- `layout/` : disposition des pages et utilitaires explicitement nommés.

`manifest.json` fixe l'ordre de cascade. Les styles métier assemblés dans Halo sont
conditionnés par la présence du lien vers la feuille de cette page (`:where` n'ajoute
aucune spécificité). Les URL publiques et leur ordre de chargement sont conservés.
Les animations qui changent une apparence appartiennent aussi aux composants.

Installation des outils : `npm ci --ignore-scripts` et les dépendances Python de
développement. `make css-format` formate les sources puis reconstruit les 11 feuilles ;
`make css-check` vérifie le formatage, leur synchronisation et les frontières de
responsabilité. Le compilateur CSS épinglé ne compresse que les espaces ; il ne
renomme pas les classes et ne construit aucun JavaScript. Les sources restent lisibles.

Le garde-fou analyse les déclarations et les sélecteurs, y compris `:is`, `:where`,
les règles conditionnelles et les animations. Une surcharge de couleur ou de bordure
dans une mise en page échoue. Les géométries des boutons et autres contrôles partagés
restent également dans leurs composants. Les utilitaires explicites sont conservés.

## Versions des fichiers CSS et JS

Toutes les pages référencent leurs fichiers avec le même marqueur : `assets/app.js?v=__BUILD__`. Ne jamais écrire une version à la main (`?v=2026…`) : `ops/deploy.sh` remplace `__BUILD__` par l'identifiant du déploiement (date UTC `AAAAMMJJhhmm`) dans toutes les pages, puis vérifie qu'aucun marqueur ne reste. En local le marqueur est servi tel quel, ce qui est sans effet.

Un fichier ajouté à une page prend donc `?v=__BUILD__`, comme les autres (le script `app.js` charge `passwords.js` avec la même chaîne de version). `tests/fast/test_asset_versions.py` vérifie que chaque référence porte le marqueur et que chaque fichier existe.

Cache (`app/public/.htaccess`) : une ressource avec `?v=` se garde un an (`immutable`), les pages HTML se revalident à chaque visite (`no-cache`), les images, SVG et polices se gardent un mois. Les réponses JSON de l'API ne reçoivent aucune règle `Expires`.

## Noyau JS commun

`assets/core.js` est chargé avant `app.js` sur toutes les pages et définit `J` : `J.$` / `J.$$` (sélecteurs), `J.esc` (échappement HTML), `J.api` / `J.post` (seul accès réseau), formats français (`J.num`, `J.int`, `J.pct`, `J.eur`, `J.money`, signés `J.numS` / `J.pctS` / `J.eurS`, dates), `J.store` (stockage local JSON, jamais d'exception, abonnement) `J.dom.h` (construction d'éléments), les composants `J.badge` / `J.seg` / `J.tabs`, les tableaux `J.table` (en-têtes, tri `button[data-sort]` + `aria-sort`, `sortRows`, `nextSort`, `onSort`, ligne vide) et les briques de graphiques `J.svg` / `J.ticks` / `J.priceDec` / `J.chartBox`. `app.js` ajoute la coque (navigation, graphiques, dialogues, thème, compte).

**Pages à gros état.** Le Classement et les Scores d'administration sont scindés en trois fichiers : un modèle sans DOM (`explorer-model.js`, testé sous Node par `tests/e2e/explorer-model.cjs`), des gabarits HTML purs (`explorer-view.js`, `admin-scores-view.js`) et le fichier de page (`explorer.js`, `admin-scores.js`) qui garde l'état, les événements et les appels API. La vue d'`admin-scores` lit l'état par des accesseurs (`ctx`) et ne l'écrit jamais. Chargement : `core.js`, `app.js`, puis modèle, vue, page.

Règle : un script de page ne redéfinit ni `$`, ni `esc`, ni un formateur de nombre, et n'appelle pas `localStorage` ni `toLocale…` / `Intl.DateTimeFormat` directement, n'écrit pas d'en-tête de tableau (`<thead>`, `<th>`) et ne redéfinit pas `seg` / `pills` / `badge` / `tabs` (`tests/fast/test_js_core.py` le vérifie). Un alias (`const $ = J.$`) est permis. `theme-init.js` lit `localStorage` lui-même : il doit s'exécuter avant tout le reste pour poser le thème sans flash.

## Formatage

`make js-format` (Prettier 3.3.3, `.prettierrc`) puis `make js-check` (formatage + `node --check`). Un changement de formatage fait toujours l'objet d'un commit séparé.

## Contrats du noyau (étape 4)

**Réseau.** `J.api(route, { method, body, params, signal, timeout })` est le seul accès réseau. Il renvoie le JSON décodé ; en cas d'échec il lève une `Error` dont le message est celui du serveur (`error`) ou `Erreur <statut>` ; un 401 hors `login.html` redirige vers la connexion. `timeout` (120 000 ms par défaut, `0` = aucun) lève `Délai dépassé…` : aucune action ne reste bloquée sur une réponse qui n'arrive pas. `signal` permet d'annuler ; l'annulation lève une erreur reconnue par `J.isAbort(e)` qui ne doit jamais s'afficher à l'utilisateur.

**Réponses périmées.** `const g = J.latest(); const t = g.next(); const r = await J.api(…); if (!g.isCurrent(t)) return;` : une réponse arrivée après une demande plus récente (frappe, changement de panneau, de filtre) est ignorée. Utilisé dans l'administration (liste des titres de l'entonnoir, titres, « pourquoi ce titre a disparu ? »). Le Classement garde `loading` et compare `applied` pour ses courbes.

**Cycle de vie des écouteurs.** Un composant qui écoute `document` ou `window` le fait avec un `AbortController` (`{ signal }`) et l'annule à sa fermeture, à son remplacement ou à son nouveau rendu ; il expose `destroy()` s'il vit plus longtemps qu'un rendu. Exemples : `SUI.picker()` (un seul écouteur de clic extérieur par sélecteur, retourne `{ destroy }`), `SUI.openInfo()` (fenêtre d'information, tous les écouteurs retirés par `closePop()`, y compris après Échap), le détail d'un titre dans `pf-home.js` (`detailAc`). Les écouteurs posés sur un élément recréé à chaque rendu disparaissent avec lui ; ceux posés une fois à l'initialisation (Classement, administration) ne sont pas répétés. Vérifié par `tests/e2e/strategies-ui.cjs` (compte des écouteurs `click` actifs sur `document` après plusieurs rendus du même sélecteur) et `tests/e2e/core.cjs` (`J.latest`, `J.api` : délai, annulation, erreur serveur).

**Échappement.** Tout texte inséré dans un gabarit passe par `J.esc`. Les composants `J.badge`, `J.seg`, `J.tabs`, `J.dom.h` échappent leurs arguments texte. Sont du **HTML voulu, fourni par l'appelant et déjà échappé** : les libellés d'en-tête de `J.table.head` (`label`), les cellules de `J.table.body`, le message de `J.table.empty`, le `body` de `J.dialog`, et les chaînes renvoyées par `J.icon`. Le titre de `J.dialog` et le texte de `J.confirm` sont échappés par le composant. Une donnée issue du serveur ou de l'utilisateur n'y entre jamais sans `J.esc`.

**Stockage.** `J.store` est le seul accès à `localStorage` (JSON, sans exception, abonnement entre onglets). `theme-init.js` lit `jigo_theme` lui-même pour poser le thème avant l'affichage.

**Styles calculés (`data-style`).** Les gabarits écrivent `data-style="prop:valeur;…"` pour une valeur réellement calculée (couleur de série, largeur, position) ; `core.js` l'applique par l'API CSSOM (la CSP interdit l'attribut `style`). Règle de fusion, définie et conservée : à l'insertion d'un nœud, une valeur déjà posée par le code (`el.style.x = …`) l'**emporte** sur le gabarit ; quand l'attribut `data-style` **change**, il **remplace** les valeurs (`force`). Le pont reste nécessaire : 108 `data-style` calculés ou de mise en page subsistent. Un `data-style` de présentation fixe est une erreur : il va dans `halo.css`.

**Globals publics.** `J` (noyau), `SUI` (sélecteur de stratégie), `STRATEGY_ICONS`, `TableLayout`, `HELP_CHAPTERS` / `HELP_TITLES` / `HC` (aide), `ExplorerModel` / `ExplorerView`, `AdminScores` / `AdminScoresView`, `AdminColumns`, `AdminCategoryModel` / `AdminCategoryDemo`, `ClassementTestSecondary` / `JigoSecondaryPersonal`, `JEtf`. Aucun autre global n'est un contrat ; `__asResize` et `__asLayoutWatch` sont des drapeaux internes d'`admin-scores.js`.

**Ordre des scripts.** `core.js` puis `app.js` toujours en tête (vérifié par `tests/fast/test_js_core.py`) ; ensuite, pour les pages à gros état, modèle → vue → page. Un script de données (`filtres-catalogue-*.js`, `help-ch-*.js`) ne dépend que de `window`/`J` et s'enregistre dans un global ; le script de page qui le consomme est chargé après.

## Frontières par page

| Page | Modèle (sans DOM) | Vue | État et câblage | Persistance / réseau |
|---|---|---|---|---|
| Classement | `explorer-model.js`, `explorer-filters.js`, `explorer-session.js` (restauration et migrations pures) | `explorer-view.js` | `explorer.js` | `explorer-storage.js` (seul fichier qui connaît les clés `localStorage`) ; API via `J.api` |
| Scores admin | — | `admin-scores-view.js` | `admin-scores.js` | `J.api` |
| Colonnes | `table-layout.js` (partagé Classement/Scores) | `admin-columns.js` | `admin-columns.js` | `J.api` |
| Catégories | `admin-categories-model.js` | `filtres.js` | `filtres.js` | `secondary-filter-store.js` |
| Portefeuilles | `pf-math.js` (calculs) | `pf-home.js` (vue d'ensemble, transactions) et `pf-detail.js` (détail d'une ligne, 3 onglets) | `pf-home.js` (état `S`, contexte `C`) | `J.api`, `J.store` (`jigo_pfx_`) |
| Administration | — | `admin-sources.js` (FinanceDatabase, Yahoo), `admin-titres.js`, `admin-cron.js` (Cron, Journaux), `admin-users.js` (Utilisateurs, Réglages) | `admin.js` (coquille : onglet courant, titre, rendu) | `admin-common.js` (traitements, formulaire de règles, entonnoir) |
| Graphiques | `J.svg`, `J.ticks`, `J.priceDec`, `J.chartBox` (noyau) | `charts.js`, `intraday.js` | `financial-chart.js` (canvas, indépendant) | — |

**Administration.** `admin-common.js` crée `window.AdminCore` (`tabs`, `page`, `tab()`, `render()` et les aides partagées) ; chaque fichier d'onglet s'y enregistre (`AdminCore.tabs.<nom>`) ; `admin.js`, chargé en dernier, fixe `page`, `tab()` et `render()` puis affiche l'onglet du hash. Ordre dans `admin.html` : `admin-common`, `admin-sources`, `admin-titres`, `admin-cron`, `admin-users`, `admin`.

**Portefeuilles.** `pf-home.js` expose son état et ses aides à `pf-detail.js` par `window.PFHomeX` ; `pf-detail.js` (chargé après) expose `window.PfDetail { MAIN, openDetail, renderPlan }`.

## Présentation fixe et valeurs calculées (F08)

- Une présentation **fixe** (marge, largeur, grille, masquage…) est une classe utilitaire `u-<propriété>-<valeur>` définie dans `base.css` (une déclaration par classe, `!important` : le style en ligne qu'elle remplace l'emportait sur toute règle).
- `data-style` ne porte plus que des valeurs **calculées** (largeur d'une barre de données, couleur d'une série), appliquées en CSSOM par `core.js` (la CSP interdit `style=`).
- Un élément que le script masque puis réaffiche utilise `.is-off` (`classList.add/remove("is-off")`), jamais `style.display`.
- `tests/fast/test_frontend_policy.py` interdit tout `data-style` fixe et vérifie que chaque classe `u-…` utilisée est définie et inversement.
- `scripts/probe_utilities.cjs` (navigateur, base jetable) vérifie que chaque classe rencontrée donne le même style calculé que l'ancien style en ligne : 2026-11-15, 347 vérifications sur 45 des 66 classes (onglets d'administration, chapitres d'aide, fiches titre, stratégies), 0 écart. Les 21 autres classes n'apparaissent que dans des états non atteints par la sonde.

## Clarification des contrôleurs après audit

`explorer-session.js` reconstruit l’état et migre les sauvegardes sans DOM, réseau
ni accès au stockage. Le contrôleur lit les entrées, persiste seulement si nécessaire
et branche les événements. La restauration copie ses entrées et conserve le
cloisonnement des choix par compte (régressions Node dans explorer-model.cjs).
Les colonnes et le rendu du tableau Scores sont dans admin-scores-view.js ; le
contrôleur garde sélection, chargements et événements. Les demandes d’aperçu passent
par le cache asynchrone commun à états pending/ready/error, avec reprise explicite.
Cela ne transforme pas les contrôleurs en fichiers vides : ils coordonnent encore
les parcours et leur état, ce qui reste leur rôle.

Les règles héritées de la feuille de base ne restent pas dans un bloc
« foundation » indifférencié : navigation, graphiques de marché/performance,
signaux, indicateurs, réglages de stratégie, filtres, états, risque et accessibilité
ont chacun leur source dans components. Leur ordre explicite dans le manifeste
conserve la cascade ; ce découpage supplémentaire ne change aucun octet des
11 sorties compilées, vérifié par build_styles --check.
