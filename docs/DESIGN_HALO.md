# CSS Halo

La référence visuelle est `design-demos/terminal-ultraviolet.html` (variante 6).
Dans l'application, `app/public/assets/halo.css` possède la palette claire et
sombre, la typographie et l'apparence des composants communs. Les pages le
chargent en dernier. C'est ici qu'il faut changer la taille des titres
(`--h1-size`), des boutons (`--btn-size`), des champs (`--control-h`,
`--control-size`), des cases (`--check-size`) et des tableaux (`--cell-pad`,
`--th-size`, `--td-size`).

`base.css` fournit le reset, la structure de l'application et les utilitaires.
Les feuilles propres aux pages définissent
leurs grilles et leurs éléments métier : elles ne doivent pas redéfinir la
palette ou les dimensions d'un composant commun. Les couleurs transparentes
des ombres et des graphiques restent des cas particuliers.

`python3 scripts/check_halo_css.py` vérifie la présence de Halo sur les pages,
son ordre de chargement et l'absence d'une seconde palette commune. Ce contrôle
ne remplace pas la comparaison visuelle des pages et des états dynamiques.
