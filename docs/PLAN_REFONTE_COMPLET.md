# Plan complet de refonte — Jigobourso

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

### État courant au 13 novembre 2026

- Référence retenue : `design-demos/terminal-ultraviolet.html`, variante Halo,
  en clair et sombre.
- Refonte CSS locale enregistrée dans `024768e` sur `main`. Les composants
  communs, leurs dimensions et la palette sont dans `app/public/assets/halo.css` ;
  `base.css` porte la structure et les utilitaires. Les feuilles de page
  conservent les dispositions et éléments propres à leur fonction.
- `tokens.css` et `components.css` ont été supprimées. Les 19 pages HTML
  chargent `halo.css` en dernier.
- La page Aide ne charge plus `strategies-ui.css` ni `strategies-ui.js` : ses
  tableaux utilisent les classes `h-table` et `h-table-scroll` de `help.css`.
- `python3 scripts/check_halo_css.py` passe sur l'état courant. Ce contrôle
  vérifie les feuilles et les jetons ; il ne valide pas le rendu des états
  dynamiques ou tous les parcours authentifiés.
- Les étapes 1 à 3 restent ouvertes dans leur ensemble : recette visuelle et
  fonctionnelle complète, états dynamiques, accessibilité et vérification des
  exceptions CSS restent à faire. F08 et les étapes 4 à 12 restent ouvertes.

---

## Règles pour Codex, Claude ou le développeur

- [ ] Lire les instructions du dépôt, ce plan et le dernier journal de reprise.
- [ ] Vérifier l'état Git et préserver toutes les modifications préexistantes.
- [ ] Identifier la révision de départ et le lot demandé.
- [ ] Réutiliser les connaissances et preuves existantes ; ne pas recommencer
      un audit global à chaque reprise.
- [ ] Exécuter seulement l'étape ou le sous-lot demandé.
- [ ] Résoudre les choix techniques courants sans demander confirmation
      à chaque détail.
- [ ] Ne pas inventer la direction graphique pendant la préparation des maquettes.
- [ ] Ne pas pousser, fusionner ou déployer sans instruction de l'utilisateur.
- [ ] Ne pas modifier les données réelles pour faciliter une refonte ou un test.
- [ ] Utiliser une base jetable clairement identifiée pour les tests destructifs.
- [ ] Ne pas modifier les dépendances de .venv ou les bibliothèques tierces.
- [ ] Ne pas introduire de framework ou de bundler sans bénéfice concret justifié.
- [ ] Séparer les commits de formatage des corrections de comportement.
- [ ] Préserver les contrats API, les routes et les règles métier pendant
      les déplacements de code.
- [ ] Supprimer les anciennes implémentations effectivement remplacées.
- [ ] Ne pas supprimer un fichier ou sélecteur sur la seule absence de référence
      dans le HTML statique : vérifier les templates et chargements dynamiques.
- [ ] Exécuter les contrôles pertinents pendant le lot ; élargir la validation
      à sa clôture, sans tout relancer après chaque petite modification.
- [ ] Ne pas modifier un test uniquement pour le faire passer.
- [ ] Mettre à jour le suivi après chaque lot.
- [ ] Fournir un bilan court : changements, vérifications, limites et prochain lot.

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

- [ ] Étape 0 — Départ fiable et réception des maquettes.
- [ ] Étape 1 — Architecture CSS et composants de référence.
- [ ] Étape 2 — Migration et harmonisation de toutes les pages.
- [ ] Étape 3 — Validation et verrouillage du résultat CSS.
- [ ] Étape 4 — Lisibilité et architecture JavaScript.
- [ ] Étape 5 — Fiabilité des échanges et des contrôles.
- [ ] Étape 6 — Cohérence financière : splits, unités et intégrité.
- [ ] Étape 7 — Architecture et cas d'usage PHP.
- [ ] Étape 8 — Architecture et dépendances Python.
- [ ] Étape 9 — Données, migrations et accès SQL.
- [ ] Étape 10 — Performance et observabilité.
- [ ] Étape 11 — Installation, CI, livraison et restauration.
- [ ] Étape 12 — Nettoyage final, documentation et recette.

---

# Étape 0 — Départ fiable et réception des maquettes

## Version et références

- [ ] Identifier le main courant et les changements pertinents depuis l'audit.
- [ ] Vérifier les défauts encore présents sans rouvrir ceux déjà corrigés.
- [ ] Définir le mode Git du chantier en suivant l'instruction de l'utilisateur.
- [ ] Inventorier les pages actives, les redirections et les assets chargés.
- [ ] Repérer les composants générés par JavaScript et les dialogues.
- [ ] Identifier les commandes de démarrage et de vérification disponibles.
- [ ] Conserver les résultats de référence et les échecs préexistants éventuels.
- [ ] Capturer les pages importantes avant modification, mobile et desktop,
      clair et sombre si ces thèmes sont pris en charge.

Référence historique, à ne pas confondre avec une validation du code courant :
656 tests rapides réussis ; 336 cas d'intégration validés en deux exécutions
après correction d'un PATH ; trois parcours navigateur officiels réussis.

## Maquettes

- [ ] Recenser les maquettes, leur emplacement, leur version et leur couverture.
- [ ] Distinguer les propositions exploratoires de la direction retenue.
- [ ] Identifier la direction graphique retenue par l'utilisateur avant
      de figer couleurs, typographie, densité et géométrie.
- [ ] Extraire les règles communes, plutôt que créer une feuille par maquette.
- [ ] Identifier les états manquants : mobile, sombre, chargement, erreur,
      désactivation, vide, textes longs et grandes valeurs.
- [ ] Établir la correspondance entre maquettes et composants réutilisables.
- [ ] Documenter les choix ouverts sans inventer silencieusement leur réponse.

Tant que les maquettes sont en cours, avancer sur l'inventaire, les références,
le relevé des conflits et le formatage CSS sans changement visuel.
Ne pas figer prématurément le design final.

## Comportements à préserver

- [ ] Aucune recherche automatique lors d'une modification de réglages.
- [ ] Recherche déclenchée par « Appliquer les réglages », chargement explicite.
- [ ] Réglages personnels et isolation entre comptes.
- [ ] Sélection, sauvegarde et restauration des stratégies.
- [ ] Consultation et modification des transactions.
- [ ] Navigation, droits, tableaux et graphiques.

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

- [ ] Cartographier les définitions communes et les surcharges locales.
- [x] Identifier une source d'autorité par famille de composants. Preuve : halo.css, bloc « SOURCE UNIQUE ».
- [x] Fixer l'ordre de chargement et une spécificité maîtrisée. Preuve : `check_halo_css.py` (ordre des feuilles) ; composants à spécificité de classe.
- [ ] Définir des conventions de composants, variantes et états.
- [ ] Interdire les sélecteurs de page qui modifient arbitrairement
      l'apparence d'un composant commun.
- [ ] Ne pas ajouter une feuille « corrections finales » après toutes les autres.
- [ ] Prévoir la suppression des règles remplacées pendant la migration.

## Lisibilité CSS

- [ ] Choisir un formatage automatique et reproductible.
- [ ] Formater dans un commit distinct du changement de design.
- [ ] Vérifier l'absence de changement sémantique dû au formatage.
- [ ] Documenter les commandes de formatage et de contrôle.
- [ ] Rendre les règles et déclarations lisibles, sans lignes de milliers
      de caractères.

## Tokens issus des maquettes retenues

- [x] Palette sémantique : surfaces, texte, bordures, accent, information,
      succès, vigilance et danger. Preuve : `:root` clair et sombre de halo.css.
- [x] Couleurs de texte adaptées aux fonds, en clair et sombre. Preuve : mesures clair/sombre sur 14 pages.
- [x] Typographie : familles, tailles, graisses, interlignages et chiffres. Preuve : variables --h*, --*-size, tabular-nums.
- [ ] Espacements et densités réellement partagés.
- [x] Rayons, ombres, focus et transitions. Preuve : --control-radius, --panel-radius, --shadow*, :focus-visible.
- [ ] Niveaux de superposition des menus, en-têtes, fenêtres et notifications.
- [ ] Palettes de données séparées si nécessaires : catégories, séries, jauges.
- [ ] Contrastes et lisibilité des valeurs vérifiés.
- [ ] Pas de token artificiel pour chaque nombre isolé sans usage commun.

## Galerie de référence

- [ ] Créer une galerie ou un parcours de référence utilisant les composants réels.
- [ ] Présenter variantes et états.
- [ ] Inclure textes longs, gros montants, valeurs absentes et icônes.
- [ ] Utiliser les mêmes sources CSS que l'application.
- [ ] Identifier les références visuelles retenues.

## Boutons

- [x] Variantes : principal, secondaire, discret et destructif. Preuve : .btn, .primary, .ghost, .danger mesurés.
- [ ] Tailles : normale, compacte, icône ; comportement tactile commun.
- [ ] États : hover, focus, actif, désactivé et chargement.
- [ ] Cohérence entre liens d'action et boutons lorsque c'est intentionnel.
- [ ] Bonne sémantique HTML conservée.
- [ ] Icônes, spinner, libellés longs et retours à la ligne prévus.
- [ ] Variantes choisies explicitement, pas selon le nom de la page.

## Formulaires

- [x] Champs texte, recherche, nombres, e-mail, mot de passe et textarea. Preuve : mesures 35 px / 12 px sur 14 pages + 5 pages publiques.
- [x] Sélecteurs, radios, cases à cocher et interrupteurs. Preuve : cases 13 px mesurées ; interrupteur 46x26 conservé.
- [ ] Libellés, aides, unités, obligation, erreurs et désactivation.
- [x] Visibilité des mots de passe. Preuve : œil visible sur login/register (captures).
- [ ] Pas de débordement des options et libellés sur mobile.
- [x] Taille des textes adaptée au mobile et vérification du zoom. Preuve : champs 16 px en mobile (--control-size-mobile).
- [ ] Distinction fonctionnelle entre action et sélecteur à menu.

## Autres composants

- [ ] Cartes/panneaux : densité, sections, en-tête, pied, sous-panneau.
- [ ] Tableaux : tri, chiffres, sélection, vide, chargement et pagination.
- [ ] Défilement horizontal et colonnes fixes utilisables au toucher.
- [ ] Badges lisibles, sans information transmise uniquement par couleur.
- [ ] Onglets et segments : états et navigation clavier.
- [ ] Dialogues/panneaux : focus, fermeture et retour au déclencheur.
- [ ] Messages, notifications, erreurs et chargements communs.
- [ ] Menus et infobulles contenus dans le viewport.
- [ ] Primitives graphiques partagées lorsque leur fonction est identique.

Clôture : composants réels conformes à la direction retenue, variantes identifiées,
références vérifiées et aucune couche finale de surcharges nécessaire.

---

# Étape 2 — Migrer toutes les pages et supprimer les anciennes règles

## Méthode à répéter pour chaque page

- [ ] Identifier composants, états et templates dynamiques utilisés.
- [ ] Migrer le balisage vers les composants communs.
- [ ] Déplacer la présentation fixe hors du HTML et des templates JS.
- [ ] Conserver les styles réellement calculés près du composant concerné.
- [ ] Supprimer les anciennes règles, classes et composants remplacés.
- [ ] Vérifier les références et chargements dynamiques avant suppression.
- [ ] Préserver les fonctionnalités et les données affichées.
- [ ] Comparer aux maquettes et à la galerie commune.
- [ ] Vérifier mobile/desktop, clair/sombre et interactions importantes.
- [ ] Enregistrer les preuves et les limites.

Une page n'est pas terminée si seul son écran initial a été regardé alors que
ses formulaires, menus ou fenêtres ont changé.

## Pages à migrer

Pour chaque case, documenter : composants migrés, ancien CSS supprimé,
tailles/thèmes testés et interactions vérifiées.

- [ ] Connexion.
- [ ] Inscription.
- [ ] Récupération de compte.
- [ ] Nouveau mot de passe.
- [ ] Confirmation d'e-mail.
- [ ] Explorateur / classement.
- [ ] Mes stratégies.
- [ ] Mes paramètres de scores.
- [ ] Mes filtres et catégories.
- [ ] Mes colonnes et tris.
- [ ] Fiche d'un titre.
- [ ] Portefeuilles et transactions.
- [ ] Bilan.
- [ ] Suivi.
- [ ] Aide et simulateurs.
- [ ] Administration et toutes ses sections.
- [ ] Administration des filtres.
- [ ] Données et diagnostics.
- [ ] Revue des splits.
- [ ] Compte et dialogues transversaux.

Adapter cette liste aux pages réellement actives du dépôt courant.

## Points particuliers de l'Explorateur

- [x] Sélecteur de stratégie contenu sur petit écran. Preuve : menu à 25–365 px sur 390 px, clair et sombre (mesure + capture).
- [ ] Options et badges lisibles au clavier et au toucher.
- [ ] Modification d'une stratégie ou d'un filtre sans recherche automatique.
- [x] Application explicite et chargement perceptible. Preuve 2026-11-13 : « Recherche en cours… », spinner, #ct-apply désactivé (bureau/mobile, clair/sombre).
- [ ] États distincts : à jour, réglages modifiés, aucun résultat, erreur.
- [x] Tableau consultable sans élargir toute la page. Preuve 2026-11-13 : tableau défile dans .ct-table-wrap (1384 px dans 1010 px ; 966 dans 364 mobile), scrollWidth page = 390.
- [ ] Règles ET/OU, colonnes, tris et modes toujours utilisables.

## Points particuliers financiers

- [ ] Montants, signes, devises, décimales et dates inchangés.
- [ ] Valeur, résultat personnel et diagnostic visuellement distingués.
- [ ] Graphiques, légendes, jauges et niveaux conservent leur sens.
- [ ] Prévisualisation, ajout, modification et suppression de transaction vérifiés.
- [ ] Confirmations et erreurs restent compréhensibles.

Clôture : toutes les pages actives sont vérifiées ; les définitions locales
remplacées ont été retirées ; les exceptions sont explicites.

---

# Étape 3 — Valider et verrouiller le CSS

## Contrôles

- [x] Formatage CSS contrôlé automatiquement. Preuve 2026-11-13 : Prettier 3.3.3 (.prettierrc), `make css-format` / `make css-check`, commit e2a2ed4.
- [x] Règles adaptées contre les surcharges locales interdites. Preuve 2026-11-13 : check_halo_css.py : refus de toute surcharge visuelle d'un composant commun hors halo.css (test : .btn{padding} refusé).
- [x] Exceptions légitimes documentées. Preuve 2026-11-13 : 5 exceptions avec raison dans EXCEPTIONS de check_halo_css.py (colonnes figées, tableaux en cartes mobile).
- [x] Styles calculés comparés pour un même composant dans plusieurs pages. Preuve : script de mesure, 56 combinaisons page/thème/largeur.
- [ ] Références visuelles stables avec procédure de mise à jour.
- [x] Conservation des !important réellement justifiés. Preuve : 2 restants ([hidden], réduction des animations).
- [ ] Le remplacement style → data-style n'est pas accepté comme preuve
      de centralisation.

## Recette

- [x] 375/390 px, largeur intermédiaire et 1280 px. Preuve 2026-11-13 : 390, 768 et 1280 mesurés sur 19 pages.
- [x] 320 px pour les parcours qui doivent le supporter. Preuve 2026-11-13 : 320 mesuré sur 19 pages + fiche titre : aucun débordement.
- [ ] Thèmes, affichage initial et absence de flash.
- [ ] Clavier, ordre de tabulation, focus et retour des fenêtres.
- [ ] Contrastes, texte agrandi et réduction des animations.
- [ ] Vide, données absentes, erreur, chargement long et désactivation.
- [x] Absence de débordement ou d'action inaccessible. Preuve 2026-11-13 : 19 pages × 320/390/768/1280 × clair/sombre : aucun débordement après correction du tableau Données.
- [x] Absence d'erreur JS, ressource manquante ou violation CSP. Preuve 2026-11-13 : mêmes 19 pages : 0 erreur après correction de titre.js et ajout de favicon.svg (404 /favicon.ico).
- [ ] Distinguer émulation mobile et vérification sur appareil réel.

## Clôture

- [ ] Documentation du design mise à jour.
- [ ] Exceptions visuelles maintenues et justifiées.
- [ ] Couverture comparée à la liste des pages et aux maquettes.
- [x] Versions des assets cohérentes avec la convention du dépôt. Preuve 2026-11-13 : 19 pages utilisent ?v=__BUILD__.
- [ ] Bilan des styles supprimés, mutualisés et conservés.

Le CSS n'est terminé que lorsque les étapes 1, 2 et 3 sont validées.

---

# Étape 4 — Refaire l'organisation JavaScript

Constats : F09, F16, F19.

## Sources et contrats

- [ ] Formatage automatique JS dans un commit séparé.
- [ ] Interfaces publiques du noyau et des composants documentées.
- [ ] Source unique pour API, formats, échappement et stockage.
- [ ] Contrat clair entre texte à échapper et HTML volontairement produit.
- [ ] Dépendances et globals publics identifiés.
- [ ] Dépendances accidentelles à l'ordre des scripts éliminées.

## Séparation des fonctionnalités

Modèle : logique testable sans navigateur.
État : données et transitions possédées explicitement.
Vue : rendu sans réseau caché.
Contrôleur : événements, API et orchestration.

- [ ] Explorer : frontières modèle, rendu, état et persistance terminées.
- [ ] Stratégies : montage, mise à jour et destruction des composants.
- [ ] Portefeuilles : calculs de présentation, état, requêtes et templates séparés.
- [ ] Administration : fonctionnalités et vues clairement délimitées.
- [ ] Filtres, colonnes et scores : composants partagés sans fusionner
      des règles métier différentes.
- [ ] Graphiques : mutualisation des primitives réellement communes.

## Cycle de vie

- [ ] Corriger les écouteurs accumulés par le sélecteur.
- [ ] Nettoyer les écouteurs des fenêtres fermées par clic, Échap ou remplacement.
- [ ] Encadrer observateurs, minuteries et abonnements.
- [ ] Éviter qu'une réponse ancienne écrase une demande plus récente.
- [ ] Gérer chargement, erreurs et annulations sans action bloquée.
- [ ] Définir la fusion/remplacement des styles calculés, ou retirer le pont global
      devenu inutile.

Clôture : modèles testables sans DOM, composants remontables sans accumulation,
anciens chemins retirés et parcours préservés.

---

# Étape 5 — Fiabilité des échanges et des contrôles

Constats : F03, F04, F05, F15, F17.

- [ ] Reproduire l'échec masqué du contrôle lint-php.
- [ ] Corriger sa propagation d'erreur sans affaiblir la CI.
- [ ] Encoder la réponse avant son statut, ou lever une erreur correctement traitée.
- [ ] Vérifier qu'une erreur JSON n'est pas renvoyée en HTTP 200.
- [ ] Faire échouer explicitement le client API sur un JSON invalide.
- [ ] Définir et vérifier les contrats minimaux des réponses.
- [ ] Distinguer validation, absence de droits, conflit et panne interne.
- [ ] Borner les corps JSON selon les besoins et refuser explicitement
      les requêtes trop volumineuses.
- [ ] Journaliser les détails utiles sans exposer de secrets.
- [ ] Tester panne moteur, réponse tronquée et encodage impossible.

Clôture : plus de faux succès ni de null inexpliqué ; les garde-fous échouent
réellement en présence d'une erreur.

---

# Étape 6 — Cohérence financière

Constats : F01, F02, F06, F12.

Isoler les corrections métier des déplacements de code.
La refonte CSS n'autorise aucune modification des données financières.

## Splits et corrections

- [ ] Distinguer absence de split et échec de lecture.
- [ ] Corriger le catch trop large transformant l'erreur en liste vide.
- [ ] Définir une indisponibilité explicite lorsque les événements sont illisibles.
- [ ] Recenser les corrections historiques et achats au prix zéro.
- [ ] Définir un lien explicite entre correction manuelle et événement.
- [ ] Tester plusieurs splits, regroupements, opérations le même jour
      et corrections ultérieures.
- [ ] Aligner validation, valorisation, lots, historique et contrôle de release.
- [ ] Ne pas appliquer automatiquement un split sur un simple saut de cours.

## Unités et change

- [ ] Définir unités, devises de référence et multiplicateurs.
- [ ] Couvrir EUR, GBP, GBp/GBX, ZAc/ZAC, ILA et les autres unités supportées.
- [ ] Aligner les règles PHP et Python.
- [ ] Préserver les taux historiques enregistrés.
- [ ] Tester frais, ventes partielles, fractions, précision et données absentes.

## Intégrité

- [ ] Corriger le faux diagnostic de vente à découvert après un split valide.
- [ ] Partager les règles de quantités/événements ou tester leur parité.
- [ ] Comparer les résultats avant/après sur des cas de référence.
- [ ] Conserver transactions originales et piste d'audit.
- [ ] Ne pas effectuer de réparation automatique des données.
- [ ] Si une migration est nécessaire, définir séparément simulation, sauvegarde,
      validation et retour arrière.

Clôture : règles explicites, cas limites couverts et résultats compatibles
entre les différents chemins métier.

---

# Étape 7 — Architecture PHP

Constat : F10.

- [ ] Formatage PHP distinct des changements fonctionnels.
- [ ] Rôles clairs : HTTP/autorisation, cas d'usage, métier, accès aux données.
- [ ] Extraire les opérations encore composées dans les routes de portefeuille.
- [ ] Mutualiser la préparation entre prévisualisation et écriture
      lorsque leur contrat est identique.
- [ ] Regrouper les accès SQL réellement partagés.
- [ ] Définir les frontières transactionnelles et l'ordre des verrous.
- [ ] Préserver les contrôles de propriétaire sur tous les chemins d'appel.
- [ ] Rendre les dépendances explicites sans ordre accidentel de require.
- [ ] Vérifier les interfaces et collisions des fonctions globales.
- [ ] Clarifier le contrat PHP/Python : types, objets/listes vides, erreurs, délais.
- [ ] Retirer les fonctions et chemins remplacés.

Clôture : routes compréhensibles par responsabilité, cas d'usage testables
sans requête HTTP, permissions toujours vérifiées par les tests HTTP.

---

# Étape 8 — Architecture Python

Constat : F11.

- [ ] Formatage et contrôles compatibles avec la version supportée.
- [ ] Directions explicites entre calculs purs, cas d'usage, stockage/cache
      et fournisseurs.
- [ ] Sortir les spécifications et profils généraux du paquet admin.
- [ ] Sortir la sérialisation du cache des responsabilités d'administration.
- [ ] Examiner les cycles en incluant les imports différés.
- [ ] Résoudre classement/scoring ↔ administration.
- [ ] Résoudre fournisseur ETF ↔ présentation/normalisation.
- [ ] Clarifier collecte ↔ intraday.
- [ ] Clarifier planification ↔ rattrapage.
- [ ] Clarifier configuration des stratégies ↔ calcul des scores.
- [ ] Extraire les fonctions longues selon leurs responsabilités.
- [ ] Garder les calculs purs indépendants de la base, du réseau et de l'admin.
- [ ] Mutualiser les règles communes sans confondre des sémantiques différentes.
- [ ] Mettre à jour imports, CLI, tâches, scripts et tests.
- [ ] Retirer les anciens chemins et les shims devenus inutiles.
- [ ] Contrôler automatiquement les dépendances interdites et nouveaux cycles.

Clôture : dépendances orientées, calculs préservés et absence
d'implémentations parallèles abandonnées.

---

# Étape 9 — Données, migrations et SQL

- [ ] Vérifier clés étrangères, index et contraintes utiles.
- [ ] Vérifier les identifiants SQL dynamiques et leurs listes blanches.
- [ ] Rechercher et mesurer les N+1 avant correction.
- [ ] Distinguer base neuve et base ancienne migrée.
- [ ] Vérifier idempotence et reprise après DDL partiellement appliqué.
- [ ] Documenter l'état de migration requis.
- [ ] Éviter les comportements financiers silencieusement dégradés.
- [ ] Vérifier isolation, concurrence, révisions et conflits.
- [ ] Vérifier conservation/purge des sessions, tentatives, logs et caches.
- [ ] Expliciter types numériques et arrondis aux frontières.
- [ ] Ne changer le schéma que pour un besoin démontré.

Clôture : schéma, migrations, accès et tests décrivent le même contrat.

---

# Étape 10 — Performance et observabilité

- [ ] Définir des scénarios représentatifs : recherche, fiche, portefeuille,
      gros tableau, scores et traitements de fond.
- [ ] Mesurer sur un volume réaliste.
- [ ] Séparer attente de slot, démarrage Python, SQL, calcul/cache,
      sérialisation, transfert et rendu.
- [ ] Mesurer cache froid/chaud, mémoire et concurrence.
- [ ] Mesurer JSON transmis et coût du filtrage/tri client.
- [ ] Vérifier les assets chargés et leurs consommateurs.
- [ ] Ne pas ajouter cache, pagination serveur, worker ou bundler
      sans problème mesuré.
- [ ] Rendre les lenteurs et erreurs diagnostiquables.
- [ ] Préserver concurrence, heartbeat, verrouillage et reprise.
- [ ] Tester pannes fournisseur, données absentes et limitations de débit
      sans correction financière implicite.

Clôture : améliorations chiffrées, causes de timeout mesurées plutôt que supposées.

---

# Étape 11 — Installation, CI et livraison

Constats : F13, F14, F15, F18.

- [ ] Vérifier toutes les dépendances avant de déclarer le venv conforme.
- [ ] Définir des versions reproductibles compatibles avec l'hébergement.
- [ ] Documenter et tester le démarrage local depuis un environnement neuf.
- [ ] Exécuter les contrôles de qualité retenus en CI, pas seulement la syntaxe.
- [ ] Conserver intégration et navigateur dans un environnement jetable.
- [ ] Distinguer validation complète et déploiement rapide.
- [ ] Ne jamais présenter un test sauté comme réussi.
- [ ] Préparer une release cohérente avant activation, ou une maintenance maîtrisée.
- [ ] Éviter les mélanges de versions pendant le transfert.
- [ ] Garantir la cohérence HTML, JS, CSS et versions des assets.
- [ ] Restaurer code ET dépendances compatibles.
- [ ] Définir invalidation de cache, recalcul des verdicts et recalcul des mesures.
- [ ] Tester ces décisions, notamment les exclusions du hash moteur.
- [ ] Vérifier sauvegardes et conservation des données.
- [ ] Tester la procédure sur une cible isolée avant toute livraison autorisée.

Clôture : installation, activation et restauration reproductibles et cohérentes.

---

# Étape 12 — Recette finale et suppression des anciennes couches

- [ ] Vérifier les parcours de bout en bout sur une base locale représentative.
- [ ] Rejouer les suites rapides, intégration, navigateur et release pertinentes.
- [ ] Refaire la recette visuelle après les derniers changements de code.
- [ ] Vérifier les cas financiers et permissions multi-utilisateurs.
- [ ] Supprimer les anciennes fonctions, règles, classes et fichiers remplacés.
- [ ] Vérifier références dynamiques, imports et compatibilités avant suppression.
- [ ] Retirer les adaptateurs transitoires devenus inutiles.
- [ ] Documenter les exceptions restantes et leur raison.
- [ ] Mettre à jour README, architecture, design, conventions et commandes.
- [ ] Indiquer les limites de couverture : navigateurs, appareils, données,
      volumes et hébergement non testés.
- [ ] Revoir chaque case cochée et sa preuve.
- [ ] Fournir une synthèse : conservé, remplacé, supprimé, vérifié, différé.

Terminé signifie : une architecture comprise et vérifiée, des composants
réellement partagés, et une seule implémentation maintenue des règles communes.
Aucun objectif artificiel de nombre de fichiers ou de lignes supprimées.

---

## Suivi des constats de l'audit

Pour chaque résolution, indiquer commit et test/preuve.

- [ ] F01 — Lecture des splits masquée. Étape 6. Preuve :
- [ ] F02 — Correction manuelle ambiguë. Étape 6. Preuve :
- [ ] F03 — Erreur JSON en HTTP 200. Étape 5. Preuve :
- [ ] F04 — Réponse API invalide acceptée. Étape 5. Preuve :
- [ ] F05 — Échec lint PHP masqué. Étape 5. Preuve :
- [ ] F06 — Contrôle financier ignorant les splits. Étape 6. Preuve :
- [ ] F07 — Composants surchargés par les pages. Étapes 1–3. Preuve partielle (reste ouvert : états dynamiques, recette étape 3) : 2026-11-13, règles de page retirées (components/base/explorer/filtres/pf/help/splits/strategies-ui/admin-*.css) ; styles calculés conformes à la référence Halo sur 14 pages connecté, clair/sombre, 1280/390 px ; limites ci-dessous.
- [ ] F08 — Présentation fixe dans data-style. Étapes 1–3. Preuve :
- [ ] F09 — Écouteurs accumulés. Étape 4. Preuve :
- [ ] F10 — Routes/services PHP incomplets. Étape 7. Preuve :
- [ ] F11 — Dépendances Python mal orientées. Étape 8. Preuve :
- [ ] F12 — Unités monétaires divergentes. Étape 6. Preuve :
- [ ] F13 — Activation/restauration de release. Étape 11. Preuve :
- [ ] F14 — Dépendances non complètement validées. Étape 11. Preuve :
- [ ] F15 — Garde-fous insuffisants. Étapes 3, 5, 11. Preuve :
- [ ] F16 — Sources condensées/formatage. Étapes 1, 4, 7, 8. Preuve :
- [ ] F17 — Taille des corps JSON. Étape 5. Preuve :
- [ ] F18 — Classification des changements/cache. Étape 11. Preuve :
- [ ] F19 — Fusion implicite des styles calculés. Étape 4. Preuve :

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
