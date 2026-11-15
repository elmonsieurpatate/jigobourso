# Corrections de l'audit de main — 15 novembre 2026

Base : `2bb2cec`. Référence : `AUDIT_MAIN_20261115.md`.
Une case n'est cochée qu'avec une modification et une vérification identifiées.
Les mesures nécessitant l'hébergement ou un appareil réel restent distinguées des
corrections locales.

- [x] A01 — Délai global du moteur, échanges non bloquants et nettoyage.
- [x] A02 — Restaurations liées à leur manifeste, échec explicite si incohérentes.
- [x] A03 — Aperçus automatiques : erreurs visibles et reprise possible.
- [x] A04 — Séparation effective structure / composants / mise en page métier.
- [x] A05 — Garde-fou CSS structurel et tests négatifs.
- [x] A06 — Cas d'usage PHP hors des routes, contrats et garde-fous communs.
- [x] A07 — Contrôleurs JS séparés par responsabilité.
- [x] A08 — Validation commune PR/main sans secret de production côté PR.
- [x] A09 — Runner des parcours actifs, scénarios historiques classés.
- [ ] A10 — Mesure reproductible et représentative, sans optimisation supposée.
- [ ] A11 — Releases cohérentes et dépendances reproductibles.
- [ ] A12 — Documentation courante, historique et preuves cohérents.

## Journal

Reprise : audit conservé sans changement ; application et données initiales intactes.

A01 : échanges stdin/stdout non bloquants, surveillance de la fin du processus et
deadline globale. 10 tests moteur et garde-fous PHP passent ; les régressions
128 Kio sans lecteur et stdout fermé avant la fin rendent 503 dans la borne.
A02 : snapshot d'environnement associé à chaque archive de code, manifeste,
interpréteur et checksum vérifiés avant restauration. Refus des anciennes
archives non associées. 18 tests d'environnement passent, dont choix explicite
d'une ancienne archive et refus d'une archive corrompue sans toucher le venv actif.

A03 : cache asynchrone à états explicites, erreur affichée et action de reprise
pour les aperçus ; les demandes identiques sont dédupliquées et une réponse
périmée après effacement ne peut pas relancer le rendu. Régressions exercées
par le test Node du noyau, réussi. Le parcours navigateur avec panne simulée
sera ajouté au runner commun de recette (A09).

A04/A05 : sources CSS lisibles dans app/styles (thème, composants, apparences
métier, mises en page), manifeste explicite, sorties publiques générées et
vérifiées sans renommer les classes. 19 déclarations strictement identiques
supprimées ; couleurs résiduelles nommées dans le thème. Compression des seuls
espaces pour respecter le budget existant des assets, sans relever son plafond.
Garde-fou syntaxique : couleurs, :is/:where, règles conditionnelles, animations
et imports contrôlés. 31 tests ciblés réussis ; galerie inchangée dans 4 contextes.
Comparaison des styles calculés avant/après sur le même DOM : 56 pages/contextes,
zéro écart. Sonde de disposition : 120 pages/contextes, aucun défilement horizontal
de page ; 22 contextes contiennent des éléments internes hors fenêtre (à distinguer
d'une page débordante). Suite rapide : 736 réussites. Qualité Python/JS/CSS/PHP valide.

A06 : cas d’usage du suivi, des alertes, de l’administration, de la recherche,
de la fiche et du compte extraits en services à paramètres explicites. Les routes
gardent authentification, méthode et sortie HTTP (dont mails après réponse et CSV).
Le contrôle de propriété reste dans les services ; aucune règle financière modifiée.
Les routes de ces six domaines ne contiennent plus de SQL ; tests de frontière
et de dépendances ajoutés. Après extraction : 351 tests d’intégration réussis.

A07 : restauration/migrations des préférences extraites dans explorer-session.js,
sans DOM, réseau ni stockage ; copies des entrées et choix par compte vérifiés
sous Node. Le contrôleur reste chargé de l’orchestration. Le rendu des colonnes
et cellules Scores est déplacé dans sa vue avec lecture explicite de l’état ;
les chargements, tris et événements restent dans le contrôleur. Les contrôles JS,
assets et sauvegardes passent ; les parcours actifs vérifient l’explorateur.

Compléments A04/A07 : fondations CSS réparties par familles cohérentes au lieu
d’un bloc hérité de 923 lignes ; sorties compilées strictement identiques.
Les vues Simulation et Suivi des calculs sont également extraites du contrôleur
Scores ; les appels réseau et les événements restent dans ce dernier.

A08/A09 : qualité, pytest sans tests sautés et recette navigateur regroupés dans
les mêmes trois scripts, appelés sur PR et main ; le workflow PR reste en lecture
seule et sans secret de production. Le runner entier réussit sur la base jetable :
galerie, contrastes, utilitaires, filtres personnels, aperçu en panne/reprise,
parcours financier, clavier, fiche, stratégies, comptes, suivi, splits et portefeuille.
Chaque groupe métier dispose d’un seed et de comptes explicites ; le README
classe les sondes Node et les anciennes recettes au lieu de les compter comme
couverture actuelle. Les sélecteurs historiques remplacés conservent les assertions
métier (badge de stratégie). Suivi : 320/390/768/1440 px ; portefeuille :
320/375/390/430/768/1024/1440 px ; splits : mobile/bureau, droits et idempotence.

A11, partie dépendances : manifestes runtime et développement verrouillés avec
leurs transitives, résolution Python 3.9 ; 739 tests rapides exécutés sous Python
3.9 sans saut. Le pip système doit correspondre au majeur/mineur du venv ;
20 tests d’environnement passent, dont refus avant installation si incompatible.
La réparation sait réutiliser une paire sans ancienne archive générique.
La publication atomique reste ouverte : voir RELEASE_ATOMICITY.md.
