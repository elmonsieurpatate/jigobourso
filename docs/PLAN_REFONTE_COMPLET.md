# Plan complet de refonte — Jigobourso

> Suivi courant après l’audit de main `2bb2cec` :
> [CORRECTIONS_AUDIT_20261115.md](CORRECTIONS_AUDIT_20261115.md) et
> [matrice de validation](VALIDATION_AUDIT_20261115.md).
> Les étapes et journaux ci-dessous conservent leur contexte historique ;
> une étape cochée ne valide pas implicitement chacun de ses critères.

## Objectif

Obtenir une application lisible, cohérente visuellement, testable et organisée
par responsabilités. Remplacer les anciennes implémentations et supprimer les
doublons, plutôt que déplacer le désordre ou ajouter une couche de correctifs.

Ordre demandé : maquettes et CSS d'abord, puis JavaScript, fiabilité,
règles financières, PHP, Python, données et exploitation.

Référence : audit indépendant du 13 novembre 2026 sur main :
079e40ce61284e8b1c1940bc0346dc9df3585a85.

Travailler sur le main courant. Ne pas revenir automatiquement à cette révision.
Vérifier les changements intervenus depuis l'audit.

Une fonctionnalité déjà présente doit être vérifiée avant d'être déclarée
conforme. Les cases non cochées restent à traiter ou à valider.

### État courant au 15 novembre 2026 — reprise de clôture

Base de cette reprise : `origin/main` **7a55926**, branche
`chore/cloture-refonte-20261115`. Le choix Halo est conservé. Les précédents
journaux restent historiques : leur annonce « étape close » ne vaut pas
vérification de chaque critère.

Le suivi de la reprise est dans [CLOTURE_REFONTE.md](CLOTURE_REFONTE.md) :
palettes et contrastes, sections de cartes, utilitaires, police locale,
compteur SQL isolé, recette navigateur et correction du responsive de la fiche.
Les règles permanentes et la méthode répétitive ne portent plus de cases :
elles s'appliquent toujours, elles ne sont pas des travaux à « terminer ».
Les critères détaillés renvoient désormais à leurs preuves ; la portée de recette est Chromium et émulation mobile, jamais une certification sur appareil réel.
Les contrôles Hostinger et appareils réels restent séparés des travaux locaux.

---

## Règles pour Codex, Claude ou le développeur

- Lire les instructions du dépôt, ce plan et le dernier journal de reprise.
- Vérifier l'état Git et préserver toutes les modifications préexistantes.
- Identifier la révision de départ et le lot demandé.
- Réutiliser les connaissances et preuves existantes ; ne pas recommencer
      un audit global à chaque reprise.
- Exécuter seulement l'étape ou le sous-lot demandé.
- Résoudre les choix techniques courants sans demander confirmation
      à chaque détail.
- Ne pas inventer la direction graphique pendant la préparation des maquettes.
- Ne pas pousser, fusionner ou déployer sans instruction de l'utilisateur.
- Ne pas modifier les données réelles pour faciliter une refonte ou un test.
- Utiliser une base jetable clairement identifiée pour les tests destructifs.
- Ne pas modifier les dépendances de .venv ou les bibliothèques tierces.
- Ne pas introduire de framework ou de bundler sans bénéfice concret justifié.
- Séparer les commits de formatage des corrections de comportement.
- Préserver les contrats API, les routes et les règles métier pendant
      les déplacements de code.
- Supprimer les anciennes implémentations effectivement remplacées.
- Ne pas supprimer un fichier ou sélecteur sur la seule absence de référence
      dans le HTML statique : vérifier les templates et chargements dynamiques.
- Exécuter les contrôles pertinents pendant le lot ; élargir la validation
      à sa clôture, sans tout relancer après chaque petite modification.
- Ne pas modifier un test uniquement pour le faire passer.
- Mettre à jour le suivi après chaque lot.
- Fournir un bilan court : changements, vérifications, limites et prochain lot.

### Signification d'une case cochée

Une case [x] signifie : réalisé ET vérifié.

Elle ne signifie pas : lu, essayé, prévu, renommé ou déplacé.

Pour chaque lot terminé, enregistrer :
- le commit ou le diff ;
- les vérifications et leurs résultats ;
- les anciennes implémentations retirées ;
- les limites ou exceptions.

Une tâche bloquée reste non cochée. Un point non applicable doit être justifié,
pas présenté comme réalisé.

---

## Tableau de bord

- [x] Étape 0 — Départ fiable et réception des maquettes. Preuve : C15 : version, branche, références, baseline et parcours identifiés ci-dessous.
- [x] Étape 1 — Architecture CSS et composants de référence. Clôturée 2026-11-14 : lint, css-check, visual, fast (656), e2e, integ (336) verts ; voir journal.
- [x] Étape 2 — Migration et harmonisation de toutes les pages. Clôturée 2026-11-14 : lint, css-check, visual, fast (656), e2e, integ (336) verts ; voir journal.
- [x] Étape 3 — Validation et verrouillage du résultat CSS. Clôturée 2026-11-14 : lint, css-check, visual, fast (656), e2e, integ (336) verts ; voir journal.
- [x] Étape 4 — Lisibilité et architecture JavaScript. Clôturée 2026-11-14 : lint, js-check, css-check, visual, fast (656), e2e, integ (336) verts ; voir journal.
- [x] Étape 5 — Fiabilité des échanges et des contrôles.
- [x] Étape 6 — Cohérence financière : splits, unités et intégrité.
- [x] Étape 7 — Architecture et cas d'usage PHP. Clôturée 2026-11-14 : lint, js-check, css-check, visual, fast (691), e2e, integ (346) verts ; voir journal.
- [x] Étape 8 — Architecture et dépendances Python. Clôturée 2026-11-14 : cycles supprimés, couches verrouillées, fonctions longues découpées ; voir journal.
- [x] Étape 9 — Données, migrations et accès SQL. Clôturée 2026-11-14 : lint, js-check, css-check, visual, fast (692), e2e, integ (349) verts ; docs/DATA_CONTRACT.md.
- [x] Étape 10 — Performance et observabilité. Clôturée 2026-11-14 : lint, js-check, css-check, visual, fast (697), e2e, integ (350) verts ; docs/PERFORMANCE.md (données synthétiques, limites indiquées).
- [x] Étape 11 — Installation, CI, livraison et restauration. Clôturée 2026-11-15 : voir docs/DELIVERY.md ; Hostinger réel non testé (répétition locale à la place).
- [x] Étape 12 — Nettoyage final, documentation et recette. Clôturée 2026-11-15 ; F07 et F08 fermés le 2026-11-15 (voir docs/RECETTE_FINALE.md).

---

# Étape 0 — Départ fiable et réception des maquettes

## Version et références

- [x] Identifier le main courant et les changements pertinents depuis l'audit. Preuve : C15 : départ 7a55926, branche dédiée, historique distant comparé.
- [x] Vérifier les défauts encore présents sans rouvrir ceux déjà corrigés. Preuve : C15 : galerie, contrastes, utilitaires, compteur SQL, captures réelles ; deux défauts de cascade corrigés.
- [x] Définir le mode Git du chantier en suivant l'instruction de l'utilisateur. Preuve : C15 : worktree isolé, aucune modification préexistante écrasée, aucun push ni déploiement.
- [x] Inventorier les pages actives, les redirections et les assets chargés. Preuve : C15 : check_halo_css.py, 19 pages, ressources présentes et ordre contrôlé.
- [x] Repérer les composants générés par JavaScript et les dialogues. Preuve : C15 : J.dialog dans app.js, SUI.picker dans strategies-ui.js, templates titre/aide ; parcours e2e réels.
- [x] Identifier les commandes de démarrage et de vérification disponibles. Preuve : C15 : Makefile, scripts/e2e_browser.sh, probe_layout.sh ; commandes de clôture documentées.
- [x] Conserver les résultats de référence et les échecs préexistants éventuels. Preuve : C15 : baseline 713 tests rapides, galerie avant/après, run CI historique identifié ; CLOTURE_REFONTE.md.
- [x] Capturer les pages importantes avant modification, mobile et desktop,
      clair et sombre si ces thèmes sont pris en charge. Preuve : Références initiales de l’audit 079e40c conservées dans artifacts/audit-main-079e40c ; captures C15 après refonte. Ne pas confondre ces deux versions.

Référence historique, à ne pas confondre avec une validation du code courant :
656 tests rapides réussis ; 336 cas d'intégration validés en deux exécutions
après correction d'un PATH ; trois parcours navigateur officiels réussis.

## Maquettes

- [x] Recenser les maquettes, leur emplacement, leur version et leur couverture. Preuve : DESIGN_HALO.md : terminal-ultraviolet.html, variante Halo et galerie des composants.
- [x] Distinguer les propositions exploratoires de la direction retenue. Preuve : DESIGN_HALO.md : référence Halo conservée ; aucune nouvelle direction inventée.
- [x] Identifier la direction graphique retenue par l'utilisateur avant
      de figer couleurs, typographie, densité et géométrie. Preuve : DESIGN_HALO.md : choix Halo consigné dans les lots précédents, conservé à cette reprise.
- [x] Extraire les règles communes, plutôt que créer une feuille par maquette. Preuve : halo.css : source unique des jetons et composants ; garde-fou exécuté.
- [x] Identifier les états manquants : mobile, sombre, chargement, erreur,
      désactivation, vide, textes longs et grandes valeurs. Preuve : Galerie (désactivé, vide, chargement, erreur, textes longs), financial/keyboard e2e ; limites appareils réels séparées.
- [x] Établir la correspondance entre maquettes et composants réutilisables. Preuve : DESIGN_HALO.md : tableau des jetons, composants et consommateurs.
- [x] Documenter les choix ouverts sans inventer silencieusement leur réponse. Preuve : CLOTURE_REFONTE.md : limites externes explicites ; choix Halo conservés.

Tant que les maquettes sont en cours, avancer sur l'inventaire, les références,
le relevé des conflits et le formatage CSS sans changement visuel.
Ne pas figer prématurément le design final.

## Comportements à préserver

- [x] Aucune recherche automatique lors d'une modification de réglages. Preuve : tests/e2e/financial.cjs et tests/e2e/strategies-ui.cjs : absence de ranking avant Appliquer.
- [x] Recherche déclenchée par « Appliquer les réglages », chargement explicite. Preuve : tests/e2e/financial.cjs : bouton, chargement, résultats réels synthétiques.
- [x] Réglages personnels et isolation entre comptes. Preuve : tests/integ et tests/e2e/strategies-ui.cjs : comptes distincts.
- [x] Sélection, sauvegarde et restauration des stratégies. Preuve : tests/e2e/strategies-ui.cjs, tests/integ : stratégies et permissions.
- [x] Consultation et modification des transactions. Preuve : tests/integ/test_portfolio_audit.py et e2e financier.
- [x] Navigation, droits, tableaux et graphiques. Preuve : 351 tests d’intégration et parcours e2e financier, stratégies, compte ; captures des pages réelles.

Clôture : version, références, direction visuelle et premier lot sont identifiés.

---

# Étape 1 — Architecture CSS et composants de référence

Constats : F07, F08, F16, F19.

## Architecture cible

Responsabilités à distinguer :
- Tokens : couleurs, typographie, espaces, rayons, ombres, superpositions.
- Base : document, reset et accessibilité de base.
- Composants : boutons, champs, cartes, tableaux, onglets, fenêtres, messages.
- Disposition : navigation, conteneurs et grilles partagés.
- Pages : disposition spécifique et véritables composants métier.

Cela ne fixe pas un nombre obligatoire de fichiers.
Centraliser les composants n'impose pas un CSS monolithique.

- [x] Cartographier les définitions communes et les surcharges locales. Preuve : DESIGN_HALO.md, FRONTEND_STRUCTURE.md et garde-fou check_halo_css.py.
- [x] Identifier une source d'autorité par famille de composants. Preuve : halo.css, bloc « SOURCE UNIQUE ».
- [x] Fixer l'ordre de chargement et une spécificité maîtrisée. Preuve : `check_halo_css.py` (ordre des feuilles) ; composants à spécificité de classe.
- [x] Définir des conventions de composants, variantes et états. Preuve : DESIGN_HALO.md : composants, variantes, jetons et exceptions.
- [x] Interdire les sélecteurs de page qui modifient arbitrairement
      l'apparence d'un composant commun. Preuve : check_halo_css.py exécuté : surcharges communes interdites, exceptions nommées.
- Ne pas ajouter une feuille « corrections finales » après toutes les autres.
- Prévoir la suppression des règles remplacées pendant la migration.

## Lisibilité CSS

- [x] Choisir un formatage automatique et reproductible. Preuve : .prettierrc et Makefile : Prettier 3.3.3, vérification réussie.
- Formater dans un commit distinct du changement de design. Historique : `e2a2ed4` (Prettier CSS).
- Vérifier l'absence de changement sémantique dû au formatage. Les corrections C15 sont des changements volontaires de comportement/style, pas présentées comme du formatage pur.
- [x] Documenter les commandes de formatage et de contrôle. Preuve : Makefile et DESIGN_HALO.md.
- [x] Rendre les règles et déclarations lisibles, sans lignes de milliers
      de caractères. Preuve : Prettier : feuilles et scripts formatés, contrôle réussi.

## Tokens issus des maquettes retenues

- [x] Palette sémantique : surfaces, texte, bordures, accent, information,
      succès, vigilance et danger. Preuve : `:root` clair et sombre de halo.css.
- [x] Couleurs de texte adaptées aux fonds, en clair et sombre. Preuve : mesures clair/sombre sur 14 pages.
- [x] Typographie : familles, tailles, graisses, interlignages et chiffres. Preuve : variables --h*, --*-size, tabular-nums.
- [x] Espacements et densités réellement partagés. Preuve 2026-11-15 : échelle `--sp-*` (13 valeurs) appliquée aux 11 feuilles, 0 valeur hors échelle (`css_scale.py check`, test_css_scale.py) ; rendu : 38 → 22 valeurs d'espacement distinctes sur 60 vues ; écart entre blocs de page = 16 px partout (gap du conteneur).
- [x] Rayons, ombres, focus et transitions. Preuve : --control-radius, --panel-radius, --shadow*, :focus-visible.
- [x] Niveaux de superposition des menus, en-têtes, fenêtres et notifications. Preuve 2026-11-15 : jetons `--z-bar/header/pop/backdrop/drawer/fly/top`, 10 usages ; test_css_scale.py.
- [x] Palettes de données séparées si nécessaires : catégories, séries, jauges. Preuve : C15 : --series-*, --chart-*, --gauge-* centralisés et consommateurs migrés ; DESIGN_HALO.md.
- [x] Contrastes et lisibilité des valeurs vérifiés. Preuve : C15 : tests/visual/contrasts.cjs, seuils et limites documentés.
- [x] Pas de token artificiel pour chaque nombre isolé sans usage commun. Preuve 2026-11-15 : chaque jeton d'échelle est utilisé (au moins 1 à 217 fois) ; valeurs isolées > 48 px conservées en dur.

## Galerie de référence

- [x] Créer une galerie ou un parcours de référence utilisant les composants réels. Preuve 2026-11-14 : design/galerie.html rendue (1280/390, clair/sombre) avec les feuilles réelles ; elle a révélé 3 défauts corrigés.
- [x] Présenter variantes et états. Preuve 2026-11-14 : boutons (variantes, tailles, désactivé, chargement), champs, cases, interrupteur, onglets, segments, badges, messages, vide/chargement.
- [x] Inclure textes longs, gros montants, valeurs absentes et icônes. Preuve 2026-11-14 : libellé long, 1 234 567,89 €, valeur absente « – », icônes.
- [x] Utiliser les mêmes sources CSS que l'application. Preuve 2026-11-14 : liens vers app/public/assets/base.css et halo.css.
- [x] Identifier les références visuelles retenues. Preuve : DESIGN_HALO.md et design/galerie.html ; référence calculée en 4 contextes.

## Boutons

- [x] Variantes : principal, secondaire, discret et destructif. Preuve : .btn, .primary, .ghost, .danger mesurés.
- [x] Tailles : normale, compacte, icône ; comportement tactile commun. Preuve : Galerie, captures à 390/1280, keyboard.cjs en contexte tactile émulé.
- [x] États : hover, focus, actif, désactivé et chargement. Preuve : halo.css (états et focus), galerie, contrat de contraste, e2e chargement et clavier ; animations neutralisées seulement dans les mesures.
- [x] Cohérence entre liens d'action et boutons lorsque c'est intentionnel. Preuve : Galerie : <a class="btn"> et <button class="btn"> utilisent la même définition commune.
- [x] Bonne sémantique HTML conservée. Preuve : Galerie : boutons natifs, liens, champs nommés ; J.dialog conserve <dialog> natif. Aucun remplacement de contrôle par un div dans ce lot.
- [x] Icônes, spinner, libellés longs et retours à la ligne prévus. Preuve : Galerie réelle revue à 390 px, références calculées clair/sombre.
- [x] Variantes choisies explicitement, pas selon le nom de la page. Preuve : DESIGN_HALO.md et classes .primary/.ghost/.danger/.sm/.lg/.icon ; garde-fou des surcharges locales exécuté.

## Formulaires

- [x] Champs texte, recherche, nombres, e-mail, mot de passe et textarea. Preuve : mesures 35 px / 12 px sur 14 pages + 5 pages publiques.
- [x] Sélecteurs, radios, cases à cocher et interrupteurs. Preuve : cases 13 px mesurées ; interrupteur 46x26 conservé.
- [x] Libellés, aides, unités, obligation, erreurs et désactivation. Preuve : Galerie, contrôles de compte e2e et tests API/validation ; routes et formulaires conservés.
- [x] Visibilité des mots de passe. Preuve : œil visible sur login/register (captures).
- [x] Pas de débordement des options et libellés sur mobile. Preuve : C15 : sélecteur touché et mesuré à 390, deux thèmes ; 120 vues et correction responsive titre.
- [x] Taille des textes adaptée au mobile et vérification du zoom. Preuve : champs 16 px en mobile (--control-size-mobile).
- [x] Distinction fonctionnelle entre action et sélecteur à menu. Preuve : SUI.picker (aria-haspopup=listbox, aria-expanded, options) et bouton natif Appliquer ; tests stratégies et tactile.

## Autres composants

- [x] Cartes/panneaux : densité, sections, en-tête, pied, sous-panneau. Preuve : C15 : --card-gap et .card-stack, variantes tight/flush/inset, captures réelles. Grilles métier explicitement conservées.
- [x] Tableaux : tri, chiffres, sélection, vide, chargement et pagination. Preuve : financial.cjs, strategies-ui.cjs, keyboard.cjs (requête au clic, chargement) et galerie (vide, valeurs extrêmes).
- [x] Défilement horizontal et colonnes fixes utilisables au toucher. Preuve : C15 : geste tactile émulé dans .ct-table-wrap en deux thèmes ; définition des colonnes fixes conservée et captures examinées.
- [x] Badges lisibles, sans information transmise uniquement par couleur. Preuve : Galerie : libellés explicites et variantes sémantiques ; contrats de contraste.
- [x] Onglets et segments : états et navigation clavier. Preuve : keyboard.cjs : flèches, Home, End sur onglets ; galerie et tests stratégies pour états des segments.
- [x] Dialogues/panneaux : focus, fermeture et retour au déclencheur. Preuve : keyboard.cjs : tabulation, fond inerte, Échap et retour au déclencheur (4 contextes) ; dialogues de transaction et compte e2e.
- [x] Messages, notifications, erreurs et chargements communs. Preuve : Galerie, composants communs, tests HTTP et e2e financier.
- [x] Menus et infobulles contenus dans le viewport. Preuve 2026-11-13 : parcours automatique des boutons non destructifs de 14 pages (bureau clair, 390 px sombre) : 0 menu/dialogue hors écran, 0 débordement.
- [x] Primitives graphiques partagées lorsque leur fonction est identique. Preuve : charts.js partagé par les consommateurs ; couleurs de séries/lignes/jauge centralisées ; palette personnelle préservée.

Clôture : composants réels conformes à la direction retenue, variantes identifiées,
références vérifiées et aucune couche finale de surcharges nécessaire.

---

# Étape 2 — Migrer toutes les pages et supprimer les anciennes règles

## Méthode à répéter pour chaque page

- Identifier composants, états et templates dynamiques utilisés.
- Migrer le balisage vers les composants communs.
- Déplacer la présentation fixe hors du HTML et des templates JS.
- Conserver les styles réellement calculés près du composant concerné.
- Supprimer les anciennes règles, classes et composants remplacés.
- Vérifier les références et chargements dynamiques avant suppression.
- Préserver les fonctionnalités et les données affichées.
- Comparer aux maquettes et à la galerie commune.
- Vérifier mobile/desktop, clair/sombre et interactions importantes.
- Enregistrer les preuves et les limites.

Une page n'est pas terminée si seul son écran initial a été regardé alors que
ses formulaires, menus ou fenêtres ont changé.

## Pages à migrer

Pour chaque case, documenter : composants migrés, ancien CSS supprimé,
tailles/thèmes testés et interactions vérifiées.

- [x] Connexion. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Inscription. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Récupération de compte. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Nouveau mot de passe. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Confirmation d'e-mail. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Explorateur / classement. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Mes stratégies. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran. Limite : création/renommage/suppression vérifiés par e2e/integ, pas à l'écran.
- [x] Mes paramètres de scores. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Mes filtres et catégories. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Mes colonnes et tris. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Fiche d'un titre. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Portefeuilles et transactions. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Bilan. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Suivi. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Aide et simulateurs. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Administration et toutes ses sections. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran. Limite : création/renommage/suppression vérifiés par e2e/integ, pas à l'écran.
- [x] Administration des filtres. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Données et diagnostics. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Revue des splits. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.
- [x] Compte et dialogues transversaux. Preuve : mesurée 2026-11-14 : 4 largeurs (320/390/768/1280) × clair/sombre, aucun débordement, texte coupé, focus invisible ni erreur JS ; menus et dialogues ouverts sans sortie d'écran.

Adapter cette liste aux pages réellement actives du dépôt courant.

## Points particuliers de l'Explorateur

- [x] Sélecteur de stratégie contenu sur petit écran. Preuve : menu à 25–365 px sur 390 px, clair et sombre (mesure + capture).
- [x] Options et badges lisibles au clavier et au toucher. Preuve : C15 : sélecteur tactile et clavier, captures clair/sombre, libellés textuels et contrastes sémantiques.
- [x] Modification d'une stratégie ou d'un filtre sans recherche automatique. Preuve 2026-11-14 : modification d'un réglage Expert, 0 requête ranking.
- [x] Application explicite et chargement perceptible. Preuve 2026-11-13 : « Recherche en cours… », spinner, #ct-apply désactivé (bureau/mobile, clair/sombre).
- [x] États distincts : à jour, réglages modifiés, aucun résultat, erreur. Preuve 2026-11-14 : à jour, chargement, aucun résultat, erreur (500 simulé) et réglage modifié (invitation « Cliquez sur Appliquer les réglages », 0 requête ranking) vus.
- [x] Tableau consultable sans élargir toute la page. Preuve 2026-11-13 : tableau défile dans .ct-table-wrap (1384 px dans 1010 px ; 966 dans 364 mobile), scrollWidth page = 390.
- [x] Règles ET/OU, colonnes, tris et modes toujours utilisables. Preuve : tests rapides/intégration des stratégies et ranking ; strategies-ui.cjs (contrats conservés), contrôles tri/colonnes présents dans les captures.

## Points particuliers financiers

- [x] Montants, signes, devises, décimales et dates inchangés. Preuve : 351 tests d’intégration, contrats financiers conservés ; aucun changement de calcul dans ce lot.
- [x] Valeur, résultat personnel et diagnostic visuellement distingués. Preuve : captures fiche/portefeuille et primitives financières existantes ; aucun déplacement de valeur ni changement de calcul.
- [x] Graphiques, légendes, jauges et niveaux conservent leur sens. Preuve : C15 : palette seulement, seuils et calculs conservés ; tests financiers et revue des captures.
- [x] Prévisualisation, ajout, modification et suppression de transaction vérifiés. Preuve : tests/integ/test_portfolio_audit.py, tests/integ/test_api.py et e2e financier.
- [x] Confirmations et erreurs restent compréhensibles. Preuve : galerie de messages, dialogue natif conservé, e2e compte et tests HTTP/API/transactions.

Clôture : toutes les pages actives sont vérifiées ; les définitions locales
remplacées ont été retirées ; les exceptions sont explicites.

---

# Étape 3 — Valider et verrouiller le CSS

## Contrôles

- [x] Formatage CSS contrôlé automatiquement. Preuve 2026-11-13 : Prettier 3.3.3 (.prettierrc), `make css-format` / `make css-check`, commit e2a2ed4.
- [x] Règles adaptées contre les surcharges locales interdites. Preuve 2026-11-13 : check_halo_css.py : refus de toute surcharge visuelle d'un composant commun hors halo.css (test : .btn{padding} refusé).
- [x] Exceptions légitimes documentées. Preuve 2026-11-13 : 5 exceptions avec raison dans EXCEPTIONS de check_halo_css.py (colonnes figées, tableaux en cartes mobile).
- [x] Styles calculés comparés pour un même composant dans plusieurs pages. Preuve : script de mesure, 56 combinaisons page/thème/largeur.
- [x] Références visuelles stables avec procédure de mise à jour. Preuve 2026-11-14 : `make visual` / `make visual-update`, tests/visual/galerie.cjson (4 contextes, styles calculés) ; procédure dans docs/DESIGN_HALO.md.
- [x] Conservation des !important réellement justifiés. Preuve : 2 restants ([hidden], réduction des animations).
- [x] Le remplacement style → data-style n'est pas accepté comme preuve Preuve 2026-11-14 : data-style 142 → 108, restants = valeurs calculées ou mise en page ; règle écrite dans docs/DESIGN_HALO.md.
      de centralisation.

## Recette

- [x] 375/390 px, largeur intermédiaire et 1280 px. Preuve 2026-11-13 : 390, 768 et 1280 mesurés sur 19 pages.
- [x] 320 px pour les parcours qui doivent le supporter. Preuve 2026-11-13 : 320 mesuré sur 19 pages + fiche titre : aucun débordement.
- [x] Thèmes, affichage initial et absence de flash. Preuve 2026-11-14 : 8 combinaisons préférence × système sur login et index : thème et fond corrects au DOMContentLoaded.
- [x] Clavier, ordre de tabulation, focus et retour des fenêtres. Preuve : C15 : tests/e2e/keyboard.cjs, dialogue partagé et onglets personnels en 4 contextes ; pas une certification exhaustive.
- [x] Contrastes, texte agrandi et réduction des animations. Preuve 2026-11-14 : contrastes clairs 4,5:1 sur 6 pages après ajustement des jetons ; 320 px (équivalent 400 %) sans débordement ; reducedMotion actif pendant les 152 mesures. Limite : fonds en dégradé contrôlés à l'œil.
- [x] Vide, données absentes, erreur, chargement long et désactivation. Preuve 2026-11-14 : vide, erreur (500 simulé), chargement (spinner, bouton désactivé), désactivation et valeur absente « – » vus.
- [x] Absence de débordement ou d'action inaccessible. Preuve 2026-11-13 : 19 pages × 320/390/768/1280 × clair/sombre : aucun débordement après correction du tableau Données.
- [x] Absence d'erreur JS, ressource manquante ou violation CSP. Preuve 2026-11-13 : mêmes 19 pages : 0 erreur après correction de titre.js et ajout de favicon.svg (404 /favicon.ico).
- [x] Distinguer émulation mobile et vérification sur appareil réel. Preuve 2026-11-14 : documenté : émulation uniquement, pas d'appareil réel (docs/DESIGN_HALO.md).

## Clôture

- [x] Documentation du design mise à jour. Preuve 2026-11-14 : docs/DESIGN_HALO.md créé.
- [x] Exceptions visuelles maintenues et justifiées. Preuve 2026-11-14 : 5 EXCEPTIONS du garde-fou + 5 choix de design listés dans docs/DESIGN_HALO.md.
- [x] Couverture comparée à la liste des pages et aux maquettes. Preuve 2026-11-14 : 19 pages mesurées (14 connectées, 5 publiques) × 4 largeurs × 2 thèmes ; maquette Halo comparée par styles calculés.
- [x] Versions des assets cohérentes avec la convention du dépôt. Preuve 2026-11-13 : 19 pages utilisent ?v=__BUILD__.
- [x] Bilan des styles supprimés, mutualisés et conservés. Preuve 2026-11-14 : blocs CSS 2129 → 2356 (halo.css 391 blocs ajoutés ; explorer 502→459, filtres 270→249, pf 198→191) : gain = une seule définition par composant, pas une baisse de volume ; 16 règles + interrupteur + .lg corrigés déplacés dans halo.css ; 5 !important ; 108 data-style.

Le CSS n'est terminé que lorsque les étapes 1, 2 et 3 sont validées.

---

# Étape 4 — Refaire l'organisation JavaScript

Constats : F09, F16, F19.

## Sources et contrats

- [x] Formatage automatique JS dans un commit séparé. Preuve 2026-11-14 : Prettier 3.3.3, `make js-format` / `make js-check`, commit 4613946.
- [x] Interfaces publiques du noyau et des composants documentées. Preuve 2026-11-14 : docs/FRONTEND_STRUCTURE.md « Contrats du noyau » (J.api, J.latest, J.store, échappement, globals).
- [x] Source unique pour API, formats, échappement et stockage. Preuve 2026-11-14 : J.api/J.post, J.num…, J.esc, J.store dans core.js ; règle vérifiée par tests/fast/test_js_core.py.
- [x] Contrat clair entre texte à échapper et HTML volontairement produit. Preuve 2026-11-14 : section « Échappement » de docs/FRONTEND_STRUCTURE.md (liste des entrées HTML voulues).
- [x] Dépendances et globals publics identifiés. Preuve 2026-11-14 : liste des globals publics et des drapeaux internes dans docs/FRONTEND_STRUCTURE.md.
- [x] Dépendances accidentelles à l'ordre des scripts éliminées. Preuve 2026-11-14 : ordre documenté ; core.js avant app.js vérifié par test_js_core.py ; scripts de données ne dépendent que de window/J. Pas de nouvelle dépendance introduite.

## Séparation des fonctionnalités

Modèle : logique testable sans navigateur.
État : données et transitions possédées explicitement.
Vue : rendu sans réseau caché.
Contrôleur : événements, API et orchestration.

- [x] Explorer : frontières modèle, rendu, état et persistance terminées. Preuve 2026-11-14 : explorer-model/-filters (modèle), explorer-view (rendu), explorer.js (état), explorer-storage.js (persistance : seul à connaître les clés ; plus aucun J.store dans explorer.js) ; vérifié en navigateur : clé de visibilité écrite, fiche titre reçoit le contexte.
- [x] Stratégies : montage, mise à jour et destruction des composants. Preuve 2026-11-14 : SUI.picker (AbortController par sélecteur, retourne { destroy }) et SUI.openInfo (closePop retire tous les écouteurs).
- [x] Portefeuilles : calculs de présentation, état, requêtes et templates séparés. Preuve 2026-11-14 : pf-math.js (calculs), pf-home.js (état, vue d'ensemble), pf-detail.js (détail, 3 onglets) via window.PFHomeX ; vérifié en navigateur (vue d'ensemble, détail, onglets, Échap, fermeture) identique à l'ancien code.
- [x] Administration : fonctionnalités et vues clairement délimitées. Preuve 2026-11-14 : admin.js (978 lignes) scindé en admin-common/-sources/-titres/-cron/-users + coquille admin.js (56 lignes) ; 9 onglets vérifiés en navigateur, entonnoir, recherche, fiche de traitement, navigation par hash.
- [x] Filtres, colonnes et scores : composants partagés sans fusionner Preuve 2026-11-14 : table-layout.js partagé par explorer.js et admin-scores.js ; règles métier non fusionnées.
      des règles métier différentes.
- [x] Graphiques : mutualisation des primitives réellement communes. Preuve 2026-11-14 : J.svg/J.ticks/J.priceDec/J.chartBox dans core.js utilisés par charts.js et intraday.js ; financial-chart.js (canvas) sans duplication.

## Cycle de vie

- [x] Corriger les écouteurs accumulés par le sélecteur. Preuve 2026-11-14 : picker : un seul écouteur de clic extérieur par hôte ; mesure navigateur : ancien code 4→10 écouteurs après 6 rendus, nouveau 3→4 (un par hôte distinct).
- [x] Nettoyer les écouteurs des fenêtres fermées par clic, Échap ou remplacement. Preuve 2026-11-14 : openInfo (AbortController, fermeture par Échap/clic/remplacement) et openDetail de pf-home (detailAc).
- [x] Encadrer observateurs, minuteries et abonnements. Preuve 2026-11-14 : inventaire : 3 MutationObserver/1 ResizeObserver globaux, 0 setInterval ; resize d'admin-scores gardé par drapeau, pointeurs d'admin-columns retirés au pointerup/cancel.
- [x] Éviter qu'une réponse ancienne écrase une demande plus récente. Preuve 2026-11-14 : J.latest dans admin.js (items de l'entonnoir, titres, explication) ; Classement : loading + comparaison applied.
- [x] Gérer chargement, erreurs et annulations sans action bloquée. Preuve 2026-11-14 : J.api : timeout 120 s, signal/annulation (J.isAbort) ; liste de titres de l'entonnoir affiche l'erreur ; tests/e2e/core.cjs.
- [x] Définir la fusion/remplacement des styles calculés, ou retirer le pont global Preuve 2026-11-14 : règle écrite dans docs/FRONTEND_STRUCTURE.md et core.js ; pont conservé (108 data-style calculés).
      devenu inutile.

Clôture : modèles testables sans DOM, composants remontables sans accumulation,
anciens chemins retirés et parcours préservés.

---

# Étape 5 — Fiabilité des échanges et des contrôles

Constats : F03, F04, F05, F15, F17.

- [x] Reproduire l'échec masqué du contrôle lint-php.
- [x] Corriger sa propagation d'erreur sans affaiblir la CI.
- [x] Encoder la réponse avant son statut, ou lever une erreur correctement traitée.
- [x] Vérifier qu'une erreur JSON n'est pas renvoyée en HTTP 200.
- [x] Faire échouer explicitement le client API sur un JSON invalide.
- [x] Définir et vérifier les contrats minimaux des réponses.
- [x] Distinguer validation, absence de droits, conflit et panne interne.
- [x] Borner les corps JSON selon les besoins et refuser explicitement
      les requêtes trop volumineuses.
- [x] Journaliser les détails utiles sans exposer de secrets.
- [x] Tester panne moteur, réponse tronquée et encodage impossible.

Clôture : plus de faux succès ni de null inexpliqué ; les garde-fous échouent
réellement en présence d'une erreur.

---

# Étape 6 — Cohérence financière

Constats : F01, F02, F06, F12.

Isoler les corrections métier des déplacements de code.
La refonte CSS n'autorise aucune modification des données financières.

## Splits et corrections

- [x] Distinguer absence de split et échec de lecture.
- [x] Corriger le catch trop large transformant l'erreur en liste vide.
- [x] Définir une indisponibilité explicite lorsque les événements sont illisibles.
- [x] Recenser les corrections historiques et achats au prix zéro.
- [x] Définir un lien explicite entre correction manuelle et événement.
- [x] Tester plusieurs splits, regroupements, opérations le même jour
      et corrections ultérieures.
- [x] Aligner validation, valorisation, lots, historique et contrôle de release.
- [x] Ne pas appliquer automatiquement un split sur un simple saut de cours.

## Unités et change

- [x] Définir unités, devises de référence et multiplicateurs.
- [x] Couvrir EUR, GBP, GBp/GBX, ZAc/ZAC, ILA et les autres unités supportées.
- [x] Aligner les règles PHP et Python.
- [x] Préserver les taux historiques enregistrés.
- [x] Tester frais, ventes partielles, fractions, précision et données absentes.

## Intégrité

- [x] Corriger le faux diagnostic de vente à découvert après un split valide.
- [x] Partager les règles de quantités/événements ou tester leur parité.
- [x] Comparer les résultats avant/après sur des cas de référence.
- [x] Conserver transactions originales et piste d'audit.
- [x] Ne pas effectuer de réparation automatique des données.
- [x] Si une migration est nécessaire, définir séparément simulation, sauvegarde,
      validation et retour arrière.

Clôture : règles explicites, cas limites couverts et résultats compatibles
entre les différents chemins métier.

---

# Étape 7 — Architecture PHP

Constat : F10.

- [x] Formatage PHP distinct des changements fonctionnels.
- [x] Rôles clairs : HTTP/autorisation, cas d'usage, métier, accès aux données.
- [x] Extraire les opérations encore composées dans les routes de portefeuille.
- [x] Mutualiser la préparation entre prévisualisation et écriture
      lorsque leur contrat est identique.
- [x] Regrouper les accès SQL réellement partagés.
- [x] Définir les frontières transactionnelles et l'ordre des verrous.
- [x] Préserver les contrôles de propriétaire sur tous les chemins d'appel.
- [x] Rendre les dépendances explicites sans ordre accidentel de require.
- [x] Vérifier les interfaces et collisions des fonctions globales.
- [x] Clarifier le contrat PHP/Python : types, objets/listes vides, erreurs, délais.
- [x] Retirer les fonctions et chemins remplacés.

Clôture : routes compréhensibles par responsabilité, cas d'usage testables
sans requête HTTP, permissions toujours vérifiées par les tests HTTP.

---

# Étape 8 — Architecture Python

Constat : F11.

- [x] Formatage et contrôles compatibles avec la version supportée.
- [x] Directions explicites entre calculs purs, cas d'usage, stockage/cache
      et fournisseurs.
- [x] Sortir les spécifications et profils généraux du paquet admin.
- [x] Sortir la sérialisation du cache des responsabilités d'administration.
- [x] Examiner les cycles en incluant les imports différés.
- [x] Résoudre classement/scoring ↔ administration.
- [x] Résoudre fournisseur ETF ↔ présentation/normalisation.
- [x] Clarifier collecte ↔ intraday.
- [x] Clarifier planification ↔ rattrapage.
- [x] Clarifier configuration des stratégies ↔ calcul des scores.
- [x] Extraire les fonctions longues selon leurs responsabilités. (2026-11-14 : history.build 136 → 99 lignes, admin.explore 127 → 79 ; aucune fonction du moteur au-delà de 101 lignes avant formatage ; après `ruff format`, plafond de 190 lignes formatées verrouillé par test ; code mort retiré : collected_rows, score_categories.select, exclusion_reason.)
- [x] Garder les calculs purs indépendants de la base, du réseau et de l'admin.
- [x] Mutualiser les règles communes sans confondre des sémantiques différentes.
- [x] Mettre à jour imports, CLI, tâches, scripts et tests.
- [x] Retirer les anciens chemins et les shims devenus inutiles.
- [x] Contrôler automatiquement les dépendances interdites et nouveaux cycles.

Clôture : dépendances orientées, calculs préservés et absence
d'implémentations parallèles abandonnées.

---

# Étape 9 — Données, migrations et SQL

- [x] Vérifier clés étrangères, index et contraintes utiles.
- [x] Vérifier les identifiants SQL dynamiques et leurs listes blanches.
- [x] Rechercher et mesurer les N+1 avant correction.
- [x] Distinguer base neuve et base ancienne migrée.
- [x] Vérifier idempotence et reprise après DDL partiellement appliqué.
- [x] Documenter l'état de migration requis.
- [x] Éviter les comportements financiers silencieusement dégradés.
- [x] Vérifier isolation, concurrence, révisions et conflits.
- [x] Vérifier conservation/purge des sessions, tentatives, logs et caches.
- [x] Expliciter types numériques et arrondis aux frontières.
- [x] Ne changer le schéma que pour un besoin démontré.

Clôture : schéma, migrations, accès et tests décrivent le même contrat.

---

# Étape 10 — Performance et observabilité

- [x] Définir des scénarios représentatifs : recherche, fiche, portefeuille,
      gros tableau, scores et traitements de fond.
- [x] Mesurer sur un volume réaliste.
- [x] Séparer attente de slot, démarrage Python, SQL, calcul/cache,
      sérialisation, transfert et rendu.
- [x] Mesurer cache froid/chaud, mémoire et concurrence.
- [x] Mesurer JSON transmis et coût du filtrage/tri client.
- [x] Vérifier les assets chargés et leurs consommateurs.
- [x] Ne pas ajouter cache, pagination serveur, worker ou bundler
      sans problème mesuré.
- [x] Rendre les lenteurs et erreurs diagnostiquables.
- [x] Préserver concurrence, heartbeat, verrouillage et reprise.
- [x] Tester pannes fournisseur, données absentes et limitations de débit
      sans correction financière implicite.

Clôture : améliorations chiffrées, causes de timeout mesurées plutôt que supposées.

---

# Étape 11 — Installation, CI et livraison

Constats : F13, F14, F15, F18.

- [x] Vérifier toutes les dépendances avant de déclarer le venv conforme. (scripts/check_env.py : versions + imports + moteur ; exécuté sur un venv neuf, rc=0 ; test_environment.py)
- [x] Définir des versions reproductibles compatibles avec l'hébergement. (bornes hautes testées, contrôle des bornes par le serveur après installation, répété localement ; sous-dépendances libres par décision, voir DELIVERY.md)
- [x] Documenter et tester le démarrage local depuis un environnement neuf. (README « Démarrage depuis zéro » ; venv neuf créé et vérifié 2026-11-14 ; base locale non rejouée depuis zéro)
- [x] Exécuter les contrôles de qualité retenus en CI, pas seulement la syntaxe. (ruff, prettier, Halo en « Contrôles courts » ; CI verte sur b781231)
- [x] Conserver intégration et navigateur dans un environnement jetable. (base jetable seule, JIGO_TEST_DATABASE=1, CI et make)
- [x] Distinguer validation complète et déploiement rapide. (test_deploy_modes.py ; docs/DELIVERY.md)
- [x] Ne jamais présenter un test sauté comme réussi. (la CI échoue si un test est sauté ; a détecté un test sauté en CI, corrigé par une référence figée ; verte sur b781231)
- [x] Préparer une release cohérente avant activation, ou une maintenance maîtrisée. (sauvegardes, contrôles avant/après, transfert différé, retour arrière code + dépendances ; répétition locale ok/fail/fail-deps)
- [x] Éviter les mélanges de versions pendant le transfert. (rsync --delay-updates ; fenêtre résiduelle non mesurée sur l'hébergement)
- [x] Garantir la cohérence HTML, JS, CSS et versions des assets. (test_asset_versions.py ; échec du déploiement si marqueur restant)
- [x] Restaurer code ET dépendances compatibles. (restore_code remet le venv sauvegardé ; testé avec faux serveur, pas sur l'hébergement réel)
- [x] Définir invalidation de cache, recalcul des verdicts et recalcul des mesures. (scripts/release/engine_hash.sh, docs/DELIVERY.md)
- [x] Tester ces décisions, notamment les exclusions du hash moteur. (test_environment.py, test_execution_architecture.py)
- [x] Vérifier sauvegardes et conservation des données. (dumps vérifiés gzip -t, empreintes financière et comptes avant/après ; deploy.sh)
- [x] Tester la procédure sur une cible isolée avant toute livraison autorisée. (2026-11-15 : répétition locale du vrai deploy.sh sur copie jetable d'une base pleine, scripts/rehearse_deploy.sh ; a trouvé et fait corriger un défaut de retour arrière ; l'essai Hostinger lui-même n'a pas été fait, voir docs/DELIVERY.md)

Clôture : installation, activation et restauration reproductibles et cohérentes.

---

# Étape 12 — Recette finale et suppression des anciennes couches

- [x] Vérifier les parcours de bout en bout sur une base locale représentative. (e2e sur base jetable synthétique, 2026-11-14)
- [x] Rejouer les suites rapides, intégration, navigateur et release pertinentes. (fast 706, integ 350, e2e, release-check, visual ; voir docs/RECETTE_FINALE.md)
- [x] Refaire la recette visuelle après les derniers changements de code. (galerie automatisée OK ; recette manuelle des pages réelles : « Visuel ok » par l'utilisateur, 2026-11-15)
- [x] Vérifier les cas financiers et permissions multi-utilisateurs. (test_financial_parity, test_account, account-navigation)
- [x] Supprimer les anciennes fonctions, règles, classes et fichiers remplacés. (collected_rows, select, exclusion_reason retirés ; reste documenté)
- [x] Vérifier références dynamiques, imports et compatibilités avant suppression. (recherche sur engine, app, scripts, ops, tests ; tests verts)
- [x] Retirer les adaptateurs transitoires devenus inutiles. (exclusion_reason retiré ; legacy_upgrade conservé (configurations V3 en base))
- [x] Documenter les exceptions restantes et leur raison. (docs/RECETTE_FINALE.md)
- [x] Mettre à jour README, architecture, design, conventions et commandes. (2026-11-15 : README, DELIVERY, ARCHITECTURE*, RECETTE_FINALE ; références à des fichiers contrôlées par recherche, deux périmées corrigées ; docs de design inchangés car aucun changement de design depuis l'étape 4)
- [x] Indiquer les limites de couverture : navigateurs, appareils, données, (docs/RECETTE_FINALE.md)
      volumes et hébergement non testés.
- [x] Revoir chaque case cochée et sa preuve. (2026-11-15 : 209 cases cochées ; chemins de fichiers cités vérifiés par script, une référence périmée corrigée ; preuves exécutables rejouées par les suites complètes ; contenu des preuves non relu ligne par ligne)
- [x] Fournir une synthèse : conservé, remplacé, supprimé, vérifié, différé. (docs/RECETTE_FINALE.md)

Terminé signifie : une architecture comprise et vérifiée, des composants
réellement partagés, et une seule implémentation maintenue des règles communes.
Aucun objectif artificiel de nombre de fichiers ou de lignes supprimées.

---

## Suivi des constats de l'audit

Pour chaque résolution, indiquer commit et test/preuve.

- [x] F01 — Lecture des splits masquée. Étape 6. Preuve : 2026-11-14 : split_events lève 503 explicite au lieu de []; test_units_parity.py + tests/integ/test_financial_parity.py (table renommée = 503).
- [x] F02 — Correction manuelle ambiguë. Étape 6. Preuve : 2026-11-14 : règle documentée (FINANCIAL_INTEGRITY.md), recensement des achats à prix zéro par le contrôle de release, aucune réécriture ; décision : lien implicite conservé, sans migration.
- [x] F03 — Erreur JSON en HTTP 200. Étape 5. Preuve : 2026-11-14 : json_text encode avant le statut, donnée inencodable = 500 + ref ; tests/fast/test_http_contract.py.
- [x] F04 — Réponse API invalide acceptée. Étape 5. Preuve : 2026-11-14 : J.api lève « Réponse illisible » sur 2xx non JSON ; tests/e2e/core.cjs.
- [x] F05 — Échec lint PHP masqué. Étape 5. Preuve : 2026-11-14 : scripts/lint_php.sh (code 1 sur erreur, 2 sans php/fichier) utilisé par make et la CI ; reproduit avant, tests/fast/test_lint_php.py.
- [x] F06 — Contrôle financier ignorant les splits. Étape 6. Preuve : 2026-11-14 : check_financial_integrity.php et validation partagent oversold_transactions ; parité split_log/corporate_events contrôlée ; test_financial_parity.py.
- [x] F07 — Composants surchargés par les pages. Étapes 1–3. Preuve : 2026-11-15 : recette visuelle des pages réelles validée par l'utilisateur (« Visuel ok »), galerie de référence verte ; 2026-11-13, règles de page retirées (components/base/explorer/filtres/pf/help/splits/strategies-ui/admin-*.css) ; styles calculés conformes à la référence Halo sur 14 pages connecté, clair/sombre, 1280/390 px ; limites ci-dessous.
- [x] F08 — Présentation fixe dans data-style. Étapes 1–3. Preuve : 2026-11-15 : 65 valeurs fixes converties en 66 classes utilitaires (base.css), `.is-off` pour les éléments réaffichés par script ; test_frontend_policy.py ; scripts/probe_utilities.cjs : 347 vérifications de parité de style calculé sur 45/66 classes, 0 écart ; docs/FRONTEND_STRUCTURE.md. Limite : 21 classes non rencontrées par la sonde.
- [x] F09 — Écouteurs accumulés. Étape 4. Preuve : 2026-11-14 : picker, openInfo, détail pf-home ; écouteurs retirés par AbortController.
- [x] F10 — Routes/services PHP incomplets. Étape 7. Preuve : 2026-11-14 : services/portfolios.php (17 cas d'usage sans HTTP), routes minces, own_transaction/tx_carry_fx, tests/fast/test_php_structure.py, docs/ARCHITECTURE_PHP.md.
- [x] F11 — Dépendances Python mal orientées. Étape 8. Preuve : 2026-11-14 : 6 cycles (imports différés compris) supprimés, 0 restant ; tests/fast/test_python_dependencies.py ; docs/ARCHITECTURE_PYTHON.md.
- [x] F12 — Unités monétaires divergentes. Étape 6. Preuve : 2026-11-14 : engine/shared/units.py + app/lib/units.php, ZAc/ILA corrigés dans l'historique et la saisie ; parité PHP/Python testée.
- [x] F13 — Activation/restauration de release. Étape 11. Preuve : 2026-11-14 : restauration code + dépendances testée (faux serveur et répétition complète), empreinte moteur unique testée.
- [x] F14 — Dépendances non complètement validées. Étape 11. Preuve : 2026-11-14 : check_env.py sur venv neuf, bornes testées, contrôle en CI.
- [x] F15 — Garde-fous insuffisants. Étapes 3, 5, 11. Preuve : 2026-11-14 : qualité et tests sautés bloquants en CI (b781231 verte) ; 2026-11-14 : garde lint PHP, contrats HTTP et moteur testés (étape 5).
- [x] F16 — Sources condensées/formatage. Étapes 1, 4, 7, 8. Preuve : 2026-11-15 : ruff format sur engine/tests/scripts (0d00563), E701/E702/E703 interdits, format contrôlé en CI et make lint ; fonctions du moteur ≤ 190 lignes formatées (strategy.rank 188).
- [x] F17 — Taille des corps JSON. Étape 5. Preuve : 2026-11-14 : BODY_MAX 2 Mio, 413 avant lecture ; test_http_contract.py.
- [x] F18 — Classification des changements/cache. Étape 11. Preuve : 2026-11-14 : scripts/release/engine_hash.sh (source unique), exclusions testées, docs/DELIVERY.md.
- [x] F19 — Fusion implicite des styles calculés. Étape 4. Preuve : 2026-11-14 : règle de fusion/remplacement définie et documentée (FRONTEND_STRUCTURE.md).

Un constat peut être résolu par correction, par preuve qu'il n'existe plus
dans la version courante, ou par décision métier explicite.
Modifier son intitulé n'est pas le résoudre.

---

## Journal de reprise

À remplir après chaque lot, sans coller les gros logs.

Date :
Intervenant :
Étape et sous-lot :
Commit de départ :
Commit(s) ou diff produit(s) :
Maquette / référence utilisée :

Changements concrets :
Anciennes implémentations supprimées :
Vérifications et résultats :
Vérifications non réalisées et conséquences :
Décisions et exceptions :
Cases cochées avec preuve :
Blocages :
Prochain sous-lot précis :

Push / fusion / déploiement réellement effectués :

### Lot du 2026-11-13 — centralisation des composants (étapes 1–3, partiel)

Intervenant : Claude. Aucune opération Git. Référence : design-demos/terminal-ultraviolet.html, Halo (clair et sombre).
Changements : halo.css = source unique (variables --h*, --control-*, --btn-*, --tab-*, --seg-*, --th/td-*, --badge-*, --card-*) ; règles de composants retirées des CSS de page, de base.css et de components.css ; .eyebrow fusionné dans .page-kicker (HTML mes-filtres/admin-filtres) ; correctifs : débordement portefeuilles, td.small, fond de page court.
Vérifié : styles calculés sur index, mes-strategies, mes-scores, mes-filtres, mes-colonnes, portefeuilles, bilan, suivi, titre, aide, donnees, splits, admin, admin-filtres (connecté) et 5 pages publiques ; un seul écart voulu (glyphe de tri 18 px, mobile).
Non vérifié : fenêtres, menus ouverts, états chargement/erreur, appareil réel ; make fast / integ / e2e non lancés ; rendu visuel des pages connectées non relu.
Décisions à valider : h3 = 15 px (le h3 de la référence fait 20 px, plus grand que son h2) ; champs 16 px sur mobile (anti-zoom iOS) ; cases à cocher natives 13 px ; cartes en dégradé Halo.
Restant à la date de ce lot : fusion tokens.css / halo.css (réalisée ensuite dans `024768e`), F08 (présentation fixe dans `data-style`), étapes 2–3 non cochées (recette complète, formatage CSS distinct, validation des états dynamiques).

### Lot du 2026-11-13 — consolidation Halo et découplage de l'Aide

Intervenant : Codex. Référence : `design-demos/terminal-ultraviolet.html`.
Commit courant : `024768e` (`Uniformiser le design Halo`) ; le présent plan est
encore une modification locale non ajoutée à Git.

Changements : `halo.css` regroupe la palette et les composants communs ; les
anciennes feuilles `tokens.css` et `components.css` ont été supprimées ;
`base.css` conserve la structure. La page Aide utilise maintenant ses propres
classes de tableaux dans `help.css` et ne dépend plus de `strategies-ui.css` ni
de `strategies-ui.js`. La documentation du design et le contrôle
`scripts/check_halo_css.py` ont été ajoutés.

Vérifications de ce lot : contrôle Halo réussi sur 19 pages ; absence de
référence à `SUI` ou aux classes `sui-*` dans les sources de l'Aide ; syntaxe
des scripts JS modifiés vérifiée avant le commit. Le lot précédent documente
les mesures Chromium réalisées avec des réponses simulées.

Non vérifié dans ce lot : reprise exhaustive des pages authentifiées avec des
données réelles, tous les menus et dialogues ouverts, états d'erreur et de
chargement, appareils réels. Les étapes 1 à 3 ne sont donc pas déclarées
terminées. Aucun test métier ni déploiement exécuté dans ce lot.

Prochain sous-lot : vérifier visuellement les composants et leurs états sur
les pages authentifiées, puis inventorier les exceptions CSS restantes avant
de cocher les pages de l'étape 2 et la recette de l'étape 3.

### Reprise du 2026-11-13 (après `132324f`) — contrôle CI et re-mesure

Intervenant : Claude. Aucune opération Git d'écriture ; aucun déploiement manuel.
CI : workflow du commit `132324f` entièrement vert (Contrôles courts, Tests complets, job hostinger automatique).
Re-mesure des styles calculés sur le code courant, 14 pages connecté, clair/sombre, 1280/390 px : conforme, sauf le glyphe de tri à 18 px sur mobile (voulu).
Inventaire CSS : aucune règle de page ne redéfinit encore un composant commun ; exceptions : `.hdr .quick input` (marge d'icône), `!important` sur `[hidden]` et sur la réduction des animations (justifiés).
Reste : F08 (≈60 `data-style` de présentation fixe, surtout admin.js et donnees.js), états dynamiques (menus, dialogues, erreur, chargement) page par page. F07 décoché jusque-là.

Lot suivant (même jour) : présentation fixe des `data-style` migrée vers des classes de halo.css (admin.js, donnees.js, admin-scores-view.js, titre.js, aide.js, mes-strategies.js) ; restent seulement des valeurs calculées ou de la disposition.
Tests sur l'état local non commité : `make fast` 656 réussis ; `make lint` OK ; `make e2e` OK (3 parcours) ; `make integ` 336 réussis. Re-mesure des styles calculés conforme sur les pages touchées. Recette manuelle locale validée par l'utilisateur.
Commits : `bd23c36` (migration des `data-style`), `4b8435a` (plan). Poussés sur `main` ; le job de déploiement automatique du workflow se déclenche au push (aucun déploiement manuel). Résultat du workflow : voir le prochain lot.
Reste : états dynamiques par page (menus, dialogues, erreur, chargement) pour cocher l'étape 2 ; F08 reste ouvert tant que les `data-style` calculés ne sont pas justifiés un à un.
Prochain sous-lot précis : recette des états dynamiques, page par page, en commençant par l'Explorateur (sélecteur de stratégie, filtres secondaires, menu des colonnes, états vide/erreur/chargement, mobile), puis Mes stratégies, Portefeuilles, Administration.

### Recette Explorateur (partielle) — 2026-11-13
Correction de méthode : mes passes « clair » sur les pages connectées étaient en réalité en sombre (le thème du compte l'emportait sur celui forcé). Script corrigé (`J.applyTheme` après chargement) ; passe complète refaite en vrai clair/sombre, 14 pages, 1280/390 px : conforme, plus détection du texte rogné.
Correctifs : champs et boutons à 40 px sur mobile (texte des listes rogné à 35 px avec une police de 16 px) ; menu des colonnes borné en hauteur (défilement interne) et visuels déplacés dans halo.css.
Vérifié sur l'Explorateur : menus stratégie, colonnes, filtres secondaires, recherche sans résultat, tri, clair/sombre, bureau/mobile, aucun débordement horizontal, aucune erreur JS.
Non vérifié : tableau avec résultats (aucune recherche lancée), états erreur et chargement, clavier. Un 404 de ressource vu une fois, non reproduit.

### État initial

Plan créé, refonte non exécutée.
Maquettes en cours de préparation.
Commencer par l'étape 0, puis les étapes 1 à 3 pour le CSS.
Aucune donnée ni fonctionnalité ne doit changer du seul fait de cette création.

---

## Instruction de démarrage pour l'agent

Lis ce document, les instructions du dépôt et le dernier journal de reprise.
Travaille sur le code courant et préserve les modifications existantes.

Reprends à partir de l'état courant décrit en tête et du dernier journal de
reprise. La direction graphique Halo est déjà retenue : ne relance pas l'étape
de choix des maquettes.

Exécute seulement le lot demandé.
Vérifie le résultat, retire les anciennes implémentations remplacées,
puis mets à jour cases et preuves.

Ne recommence pas un audit global.
Ne pousse et ne déploie rien sans instruction explicite.
Explique le résultat simplement.

### Reprise locale CSS Halo — 13 novembre 2026

Le choix graphique Halo est fixé : `design-demos/terminal-ultraviolet.html`
(variante 6, clair et sombre). Le travail local a conservé cette direction.
La palette et les dimensions des composants communs sont dans
`app/public/assets/halo.css`. Les anciennes feuilles `tokens.css` et
`components.css` ne sont plus chargées ; les utilitaires structurels de la
seconde ont été repris dans `base.css`. Les 19 pages chargent Halo en dernier.

Contrôles effectués : `python3 scripts/check_halo_css.py`, analyse syntaxique
des CSS, réponses HTTP des 19 pages, mesures Chromium des composants communs
sur les 19 pages en clair et sombre aux largeurs 1440 et 390 px. Les hauteurs
forcées des lignes du tableau Explorer ont été retirées. La page d'aide a été
contrôlée avec des réponses d'authentification simulées, en clair et sombre,
sur bureau et mobile ; changement de niveau et sommaire mobile vérifiés.

Les contenus réels des pages nécessitant une session authentifiée n'ont pas
été rejoués dans ce lot. Cette note décrit le lot local antérieur au commit
`024768e` ; elle ne décrit pas à elle seule l'état Git actuel.

### Recette Explorateur (suite) — 2026-11-13

Pagination : `flex-wrap` + visuels dédoublés retirés (halo.css gouverne). Débordement mobile corrigé (scrollWidth 390). Résultats 50 lignes, focus clavier visible sur les premiers arrêts. Non vérifié : état d'erreur, règles ET/OU, badges au tactile. Tests non relancés (fin de lot).


### Lot CSS étape 3 — 2026-11-13

Formatage Prettier (e2a2ed4), garde-fou anti-surcharge, 16 règles déplacées dans halo.css, 5 exceptions documentées, favicon, tableau Données défilant, titre.js protégé. Mesures : 19 pages × 4 largeurs × 2 thèmes, 0 débordement, 0 erreur. Restent : états dynamiques Mes stratégies, Portefeuilles, Administration, dialogues, erreur Explorateur ; galerie de référence ; relance complète des tests.


### Recette dynamique (parcours automatique) — 2026-11-13

Parcours des boutons non destructifs sur 14 pages (1280 clair, 390 sombre) : menus et dialogues s'ouvrent, restent dans l'écran, se ferment avec Échap, aucun débordement, aucune erreur JS. Erreur d'API simulée sur l'Explorateur : message clair, bouton réactivé. Correctif : admin.js affiche une erreur si « Voir les titres » échoue (avant : panneau vide). Non couvert : actions qui écrivent (créer, renommer, supprimer, transactions) vérifiées par les tests e2e/integ sur la base jetable, pas visuellement ; appareil réel ; contraste automatisé.

### Galerie de référence et blocage de vérification — 2026-11-14

`design/galerie.html` créée (titres, boutons et états, champs, cases, onglets, segments, badges, messages, indicateurs, textes longs, valeurs absentes) avec les feuilles réelles base.css et halo.css ; hors `app/public` car le test `test_core_is_loaded_before_app_on_every_page` impose core.js/app.js sur toute page déployée. NON rendue ni mesurée : après redémarrage de la machine, Chromium (/tmp) et le serveur local 8090 ont disparu et le CDN Playwright est inaccessible. Cases « galerie » non cochées. Restent : rendre la galerie (clair/sombre, 390/1280), revoir « réglages modifiés » dans l'Explorateur, valider les 4 choix de design (h3 15 px, champs 16 px mobile, cases natives, dégradé des cartes) — conservés tels quels en attendant.


### Galerie rendue, trois défauts corrigés — 2026-11-14

Chromium réinstallé (Chrome for Testing 153, hors dépôt). La galerie a révélé : (1) `.lg` de légende (base.css) écrasait `.btn.lg` (bouton 12 px tronqué) → `.lg:not(.btn)` ; (2) `select` avec 10 px de marge droite au lieu de 32 px (la règle générique des champs l'emportait) → flèche superposée au texte, corrigé dans halo.css ; (3) interrupteur défini par `#ac-filter-enabled` dans filtres.css → promu en `input.switch` dans halo.css. Garde-fou étendu aux sélecteurs `#id`. Mesure : 19 pages × 320/390/768/1280 × clair/sombre = 152 combinaisons sans débordement, texte coupé, marge de flèche manquante, focus invisible ni erreur. Restent à ta décision : h3 15 px, champs 16 px mobile, cases natives, dégradé des cartes (conservés).



### Clôture des étapes 1 à 3 — 2026-11-14

Contrastes du thème clair relevés (jetons --muted, --accent, --ok, --warn, --danger), thème sans flash, références visuelles (`make visual`), doc `docs/DESIGN_HALO.md`. Passe finale : lint, css-check, visual, fast 656, e2e, integ 336 : tous verts. Dialogues vus à l'écran : Enregistrer sous, Nouvelle transaction (bureau et mobile). Non vus à l'écran : création et renommage de stratégie (e2e seulement). Appareil réel non testé. Instabilité connue : `strategies-ui` expire parfois à la connexion en e2e local (2 échecs sur 5 le 2026-11-14, passe en CI). Quatre choix de design conservés (voir DESIGN_HALO.md).




### Clôture de l'étape 4 — 2026-11-14

Formatage JS (Prettier, commit 4613946, `make js-format` / `make js-check`). Cycle de vie : `SUI.picker` ne cumule plus d'écouteurs (mesure : ancien code 4 → 10 écouteurs `click` après 6 rendus, nouveau 3 → 4), `SUI.openInfo` et le détail de `pf-home.js` retirent tous leurs écouteurs (AbortController). Réseau : `J.api` a un délai (120 s) et un `signal` (`J.isAbort`), `J.latest` ignore les réponses périmées (administration), la liste de titres de l'entonnoir affiche l'erreur. Découpes : `admin.js` (978 lignes) en `admin-common/-sources/-titres/-cron/-users` + coquille de 56 lignes ; `pf-home.js` → `pf-detail.js` ; `explorer-storage.js` (persistance de l'Explorateur). Docs : `docs/FRONTEND_STRUCTURE.md` (contrats du noyau, échappement, globals, ordre des scripts, frontières par page). Tests ajoutés : `core.cjs` (J.latest, J.api : délai, annulation, erreur), `strategies-ui.cjs` (écouteurs actifs après plusieurs rendus). Deux tests de texte source rendus insensibles au style de guillemets (Prettier) : `test_execution_architecture.py`, `test_scores_admin.py`. Vérifié en navigateur sur données réelles : 9 onglets d'administration, entonnoir, détail d'un portefeuille (3 onglets, Échap), Explorateur (colonnes, fiche titre). Non fait : F16 (reste ouverte : étapes 7 et 8 pour PHP/Python). Appareil réel non testé.

## Journal — étape 5 (2026-11-14)

- F05 reproduit (erreur de syntaxe injectée, `make lint-php` sortait 0), corrigé par `scripts/lint_php.sh` ; Makefile et deux workflows l'utilisent (ops/deploy.sh garde `find | xargs php -l`, déjà strict).
- F03 : `json_text($data, &$status)` encode avant `json_headers`; échec = 500 `{error, ref}`. En-tête `X-Request-Id`, `ref` repris dans le journal `api [ref] …`.
- F17 : `BODY_MAX` 2 Mio, 413 par `Content-Length` puis par lecture bornée.
- F04 : `J.api` lève sur 2xx illisible.
- Contrat et statuts : `docs/API_CONTRACT.md`. Tests : moteur 503 (plantage, JSON tronqué, vide, non objet), statuts réels en intégration.
- Passe finale : lint, js-check, css-check, visual, fast 669, e2e, integ 337 — tous verts. Non poussé.

## Journal — étape 6 (2026-11-14)

- Unités : table unique Python (`engine/shared/units.py`) et miroir PHP (`app/lib/units.php`) ; 7 doublons de règles Python remplacés ; ZAc/ILA n'étaient pas divisés par 100 dans l'historique des portefeuilles (`session.py`, `history.py`) ni dans la saisie historique PHP (`historical_fx`).
- Splits : lecture illisible = 503 ; règle de quantité unique `oversold_transactions` ; contrôle de release enrichi (ventes à découvert avec splits, achats à prix zéro, split sans événement moteur), lecture seule.
- Documentation : section « Étape 6 » de FINANCIAL_INTEGRITY.md (décision sur les corrections manuelles, table des unités).
- Passe finale : lint, js-check, css-check, visual, fast 682, e2e, integ 344 verts.

## Journal — étapes 7 et 8 (2026-11-14)

- Livraison étape 6 : le job hostinger a échoué une fois (empreinte « avant » exécutée avec le contrôle complet, dépendant du code applicatif absent de l'ancienne version) ; corrigé par `scripts/release/financial_fingerprint.php` (commit 62ae084), CI et déploiement verts. Garde : test_deploy_modes.
- Étape 7 : routes de portefeuille → `app/services/portfolios.php` ; cycle PHP `secondary_metadata` ↔ `secondary_filters` supprimé ; tests de structure (fonctions uniques, require explicites, couches). Aucun formateur PHP dans le projet : formatage non touché (décision documentée).
- Étape 8 : modules déplacés (scores_specs, scores_profiles → scoring ; universe_verdicts → explorer ; strategy_docs → admin ; conversion V3 → explorer/legacy_upgrade), nouveaux modules score_cache, ranking_support, shared/units ; réexports retirés ; `ops/deploy.sh` mis à jour (chemin de universe_verdicts, exclusion du hash moteur). Le premier déploiement recalculera donc les données dérivées (chemins du moteur changés).
- Reste à l'étape 8 : fonctions longues.

## Journal — étape 9 (2026-11-14)

- Audit : 48 tables InnoDB, 33 clés étrangères, aucune FK sans index ; seule `account_attempts` n'a pas de clé primaire (journal purgé quotidiennement, schéma inchangé faute de besoin démontré).
- Migrations : reprise après DDL partiel (erreurs « existe déjà » tolérées et journalisées, autres erreurs bloquantes) ; rejeu des vraies migrations sur schéma neuf testé.
- SQL dynamique : liste blanche ajoutée à `_count` ; autres interpolations vérifiées (constantes).
- N+1 : mesurés (`test_query_counts.py`), aucun par transaction.
- `suivi` : réglages de plan illisibles signalés (`plan_rules_unavailable`) au lieu d'être masqués.
- Aucune migration de schéma ajoutée.

## Journal — étape 10 (2026-11-14)

- Banc : `scripts/perf_probe.py` (9 600 titres × 400 séances, base jetable séparée) et `scripts/perf_browser.cjs`. Résultats et limites : docs/PERFORMANCE.md.
- Problème mesuré : classement = 10,1 Mo de JSON. Correction : gzip des réponses > 64 Ko (÷ 8,8, 94 ms CPU). Pas de pagination, cache, worker ni bundler (non justifiés).
- Observabilité : en-tête `Server-Timing` (app, slot, engine, decode, gzip), journal des requêtes > 3 s avec identifiant.
- Garde-fous : tests d'assets (références, orphelins, doublons, plafond 450 Ko), comptage des requêtes SQL.

## Journal — étape 11 (2026-11-14)

- `scripts/release/engine_hash.sh` : empreinte du moteur définie une seule fois (avant/après transfert) ; testée (exclusions inactives, code et schéma actifs, exclusions existantes).
- `ops/deploy.sh` : la restauration remet aussi le venv sauvegardé si `requirements.txt` restauré ne correspond plus à `.requirements.sha`.
- `scripts/check_env.py` + README « Démarrage depuis zéro » ; venv neuf installé depuis `requirements.txt` : conforme.
- CI : ruff, prettier, règles Halo dans les contrôles courts ; `check_env.py` après installation ; échec si un test est sauté (rapides et intégration).
- `docs/DELIVERY.md` : chaîne de validation, restauration, recalcul, sauvegardes, limites.
- Ouvert : transfert non atomique ; sous-dépendances non figées ; essai isolé Hostinger (secret serveur absent) ; restauration des dépendances non testée sur l'hébergement réel.

## Journal — répétition de déploiement (2026-11-15)

- `scripts/rehearse_deploy.sh` : vrai `ops/deploy.sh` contre un faux serveur local et une copie jetable de la base de développement.
- Défaut trouvé et corrigé : contrôles `cmd && echo ok` sans effet sous `set -e` (moteur importable, `private/env`, venv, dump). Test de garde ajouté.
- Restant pour l'étape 11 : transfert rsync non atomique, sous-dépendances non figées, restauration non essayée sur Hostinger même.

## Journal — 2026-11-15 (suite)

- Transfert `rsync --delay-updates --delete-delay` ; `check_env.py` exécuté sur le serveur après installation ; répétition locale `ok` et `fail-deps` rejouée : verte.
- `ruff format` appliqué (commit de formatage seul) ; fast 707, e2e, integ 350, visual verts avant et après.
- F08 laissé ouvert : 53 valeurs fixes distinctes dans `data-style` ; les convertir en classes change la spécificité CSS (le style en ligne l'emporte toujours) et ne peut pas être jugé sans recette visuelle humaine des pages réelles.

## Journal — F08 (2026-11-15)

- 65 présentations fixes de `data-style` converties en classes atomiques `u-…` (`base.css`), `.is-off` pour `#runbar`, `#as-cur`, `#as-dot` (réaffichés par script : `classList` à la place de `style.display`).
- Gardes : test_frontend_policy.py ; sonde de parité en navigateur (0 écart sur 347 vérifications).
- La recette visuelle « Visuel ok » précède cette conversion : un nouveau coup d'œil sur admin, aide, fiche titre et stratégies est recommandé.

## Journal — harmonisation CSS (2026-11-15)

- Constat : les étapes 1 à 3 avaient été closes sans que « espacements partagés » le soit ; mesure avant : 138 marges, 177 paddings, 71 tailles de texte, 26 points de rupture, 31 rayons distincts dans les déclarations.
- `scripts/css_scale.py` (échelles, conversion, contrôle) ; test `tests/fast/test_css_scale.py` ; jetons dans `halo.css` ; doc `docs/DESIGN_HALO.md` (échelles et rythme vertical).
- Rythme vertical : l'écart entre blocs d'une page vient du conteneur (grid gap 16 px) ; marges locales des enfants neutralisées ; `mt-*`/`margin` retirés de `titre.js` et `mes-strategies.js` aux niveaux de page.
- Doublons `base.css`/`halo.css` (`.btn`, `.card`, `h1`, `h2`, `th`) fusionnés dans `halo.css`.
- Seuils JavaScript alignés sur les points de rupture (960 → 900, 700 → 760).
- Mesure après (`scripts/probe_layout.sh`, 60 vues) : valeurs rendues distinctes espacements 38 → 22, tailles 43 → 18, interlignages 14 → 8, rayons 16 → 6 ; aucune page à défilement horizontal ; tous les écarts entre blocs de page à 16 px ; il reste des écarts intérieurs aux cartes (8 à 12 px) non unifiés.
- Effet visible : rayons 9 → 8 px, boutons 36 → 38 px de haut, titres de section 19 → 20 px, pages 0 à 50 px plus hautes ; référence `tests/visual/galerie.json` régénérée.

## Journal — reprise de clôture C15 (2026-11-15)

Voir `CLOTURE_REFONTE.md` pour les changements et la distinction entre preuves
historiques, contrôles rejoués et limites. Les cases ont été réconciliées
seulement quand une preuve identifiable existe ; aucune suppression de critère
pour afficher artificiellement « zéro restant ».

La revue des captures a découvert une régression non signalée : la classe
utilitaire `u-grid-template-columns-v3 !important` empêchait la fiche titre de
passer en une colonne sur mobile. Remplacée par `.title-layout` responsive CSS ;
suppression du style JS et de l'utilitaire devenu inutile. La sonde utilitaire
vérifie désormais aussi les styles dynamiques éventuellement bloqués.

Le compteur de classes est calculé depuis le CSS courant : 64 avant cette
correction, 63 après. Les anciens nombres « 45/66 » décrivent un état antérieur.

Les critères de recette C15 incluent désormais le tactile émulé : sélection de
stratégie sans recherche automatique, un seul appel au clic, chargement explicite
et défilement horizontal du tableau dans les deux thèmes (`keyboard.cjs`). Les
captures initiales de l’audit et les résultats historiques ne sont pas rebaptisés
captures de la dernière main ; les versions sont indiquées. Les vérifications
externes non réalisées restent les trois cases de `CLOTURE_REFONTE.md`.

Résultats de clôture C15 : lint/format/syntaxe et garde-fous OK ; 714 tests
rapides, 351 tests d’intégration ; e2e financier/stratégies/compte, clavier,
tactile émulé et fiche responsive OK ; galerie 4 contextes, 196 contrastes,
63 utilitaires (756 contrats + 326 comparaisons sur pages), sans écart. 120 vues
mesurées, puis 36 vues fiche/aide revérifiées : aucun débordement de page.
Contrôles financiers et catalogue secondaire conformes. Voir RECETTE_FINALE.md.
