# Publication de releases : étude et critères de bascule

Statut : proposition, **non implémentée et non validée sur Hostinger**. Le rsync
actuel et les sauvegardes appariées restent le mécanisme en place. Les versions
Python directes/transitives sont verrouillées ; cela ne rend pas les fichiers atomiques.

## Choix à départager avec une mesure réelle

| Option | Gain | Limite / coût |
|---|---|---|
| rsync différé actuel | peu de changements, retour arrière connu | série de renommages et mélange possible de versions ; fenêtre réelle inconnue |
| pause de maintenance autour du transfert | masque une partie de la transition aux nouvelles requêtes | indisponibilité, drainage des requêtes et tâches indispensable ; pas une atomicité de répertoire |
| répertoires immuables et lien current | bascule de code par un seul renommage de lien | migration initiale des chemins, venv par release, assets immuables, compatibilité des migrations et tâches anciennes |

Une simple modification de lien public ne suffit pas : PHP/Python, crons et assets
pourraient encore lire des racines différentes. Ne pas annoncer une release atomique
sur la seule réussite d’une page HTTP après livraison.

## Contrat proposé si la mesure justifie la bascule

1. Inventorier en lecture seule les cibles hPanel/cron, public_html/v2, la racine
   moteur, les propriétaires/droits et l’espace disponible. Conserver une preuve
   des liens et chemins ; aucun déplacement de private/data/logs à cette étape.
2. Préparer une release indépendante, son manifeste et son environnement Python.
   Ne pas partager un site-packages modifiable avec la release précédente ni utiliser
   des liens physiques suivis d’une installation pip en place.
3. Résoudre une seule racine physique par requête et par tâche. Vérifier notamment
   les valeurs JIGO_ENGINE_ROOT/JIGO_PYTHON provenant de private/env : une ancienne
   requête ne doit pas commencer en PHP ancien puis lancer Python nouveau.
4. Publier les assets sous un chemin immuable par version et conserver ceux des
   pages déjà ouvertes. Le seul paramètre ?v ne conserve pas un ancien fichier.
5. Appliquer uniquement des migrations compatibles avec les deux releases pendant
   le chevauchement ; les contrôles « migration additive » ne prouvent pas à eux
   seuls la compatibilité des vues ou des requêtes d’un ancien traitement.
6. Vérifier la nouvelle release par une cible isolée, y compris registre, comptes,
   recherche et courriels factices. Garder les contrôles financiers avant/après.
7. Sur une installation déjà organisée ainsi, préparer current.next puis remplacer
   current par renommage atomique. La première conversion d’un répertoire existant
   exige une fenêtre de maintenance et un plan de retour à la topologie initiale.
8. Conserver l’ancienne release tant qu’une requête/tâche l’utilise. Le retour arrière
   repointe vers cette release et son propre venv ; il n’annule pas une migration SQL
   destructrice (qui reste interdite dans ce protocole).

## Preuves requises avant mise en production

- Requêtes lentes et appels concurrents traversant la bascule ; aucune combinaison
  PHP/Python/asset incohérente, aucun 404/500 masqué par un retry de test.
- Tâche de fond active, heartbeat/verrouillage conservés, pas de deuxième exécution.
- Échec avant bascule et après bascule, restauration vérifiée avec la bonne paire
  de code/dépendances, ancien navigateur encore utilisable.
- Données financières et comptes identiques avant/après ; permissions multi-comptes.
- Mesure de la fenêtre actuelle et comparaison à la nouvelle stratégie, sur la cible
  d’hébergement réelle. Une répétition locale reste identifiée comme telle.

Aucune opération de migration de la topologie n’a été lancée dans ce lot d’audit.
