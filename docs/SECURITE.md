# Sécurité : audit du 29/10/2026 et suites

## Corrigé dans le code
| Sujet | Correctif |
|---|---|
| Montants hors limites tronqués en silence | Session MariaDB en mode strict (`app/lib/db.php`) ; `num_in` borne les valeurs à 1e12. |
| Verrouillage du compte admin par n'importe qui | Limite par couple compte + IP (5 en 15 min), par IP seule (20), et verrou global du compte seulement à 30 échecs (donc plusieurs IP). |
| Clé de limitation d'inscription tronquée en IPv6 | Clés hachées de 26 caractères (`attempt_key`). |
| `auth/recover` révélait l'existence d'une adresse (503 si l'envoi échoue, durée différente) | Réponse identique ; l'envoi se fait après la réponse (`out_then`). |
| Aucun avis lors d'un changement sensible | E-mail envoyé à l'adresse enregistrée après changement ou réinitialisation du mot de passe, et à l'ancienne adresse après remplacement. |
| Verrou SQL tenu pendant l'envoi d'un e-mail | Jeton enregistré, transaction validée, puis envoi (`update_account`). |
| Blocage PHP ↔ Python (stderr plein), pas de délai maximal, processus illimités | `engine_call` : stderr dans un fichier, délai de 90 s (`JIGO_ENGINE_TIMEOUT`), 4 appels simultanés au plus. |
| `cron-rejets.log` sans limite | Archivé au-delà de 256 Ko. La clé du cron peut passer par l'en-tête `X-Cron-Key`. |
| CSP `script-src 'unsafe-inline'`, pas de HSTS | Scripts déplacés dans `assets/bilan.js` et `assets/register.js` ; CSP stricte, HSTS (180 jours), `Permissions-Policy`, `X-Powered-By` retiré. |
| Codes de place non échappés | `J.esc` dans `admin.js` et `explorer.js`. |
| Export CSV interprété comme formule | Préfixe `'` pour `= + - @`. |
| `tx/add` en 500 si `currency` n'est pas du texte ; lignes mortes ; `portfolio/default` sans rollback ; booléens d'`admin/user/update` | Corrigés. |
| Deux traitements du même type en parallèle | `GET_LOCK` autour de « vérifier puis créer » (`engine/jobs/runner.py`). |
| Tables qui grossissent sans fin | `housekeeping` (tentatives, sessions et jetons périmés, anciens traitements) pendant la maintenance. |
| Pas de sauvegarde régulière des comptes et portefeuilles | `backup_user_data` : un dump gzip par jour (droits 600, 14 exemplaires) dans `$JIGO_DATA_DIR/backups`. |
| Messages d'erreur internes renvoyés au client | `KeyError` / `TypeError` : message générique, détail dans stderr. |
| Journal et artefacts de déploiement publics | `ops/public-log.sh` ne garde que les titres d'étapes et les verdicts ; artefacts conservés 1 jour. |
| Workflows qui utilisaient les secrets de production depuis des branches de travail | `account-checks.yml` et `financial-checks.yml` supprimés. |

## À faire hors du code
1. **GitHub › Settings › Environments › production** : limiter les branches de déploiement à `main`, activer les relecteurs requis. Supprimer les branches `feat/navigation-account` et `fix/financial-integrity` (leurs anciens workflows y restent exécutables avec les secrets).
2. **Clé SSH de déploiement** : n'accepter que cette clé (pas de mot de passe SSH dans hPanel) ; idéalement une clé dédiée limitée aux commandes de déploiement.
3. **Copie hors du serveur** des sauvegardes `backups/userdata-*.sql.gz` (le serveur seul n'est pas une sauvegarde).
4. **Cron hPanel** : passer la clé dans l'en-tête (`wget -q -O /dev/null --header='X-Cron-Key: …' https://jigobourso.turnjoy.dev/api/cron`) puis changer la clé (`private/cron.key`) : l'ancienne a pu apparaître dans des journaux d'accès.
5. **DNS** : ajouter un enregistrement DMARC pour `turnjoy.dev` (et DKIM si Hostinger le propose) pour la délivrabilité des liens de récupération.
6. **Python 3.9 est en fin de vie** (octobre 2025) : passer à 3.11 ou plus si l'hébergeur le permet.
7. **Ménage de l'ancien site** (après la période d'observation) : `.jigobourso-backups`, `.jigobourso-runtime`, `public_html` de la v1, `.jigobourso-db.env` ; puis changer le mot de passe de la base.
8. **Historique de `deployment-status`** : d'anciens journaux sont dans l'historique de la branche publique. Pour les retirer, recréer la branche (`git checkout --orphan`, push forcé).
9. **Données** : confirmer le taux de change de la transaction n° 14 (GBP) : tant qu'elle est incomplète, le bilan masque coût et plus-values.

## Limites connues
- Taux de change : une cotation Yahoo par jour, pas un cours de référence : suffisant pour le suivi, pas pour une déclaration fiscale.
- Les données Yahoo sont obtenues par des points d'accès non officiels ; vérifier les conditions d'utilisation avant d'ouvrir le site à d'autres personnes.
- Les écritures de réglages JSON partagés (`last_stats`, `cron_heartbeat`) ne sont pas verrouillées ; les passages ne se chevauchent plus (verrou de traitement), le risque restant est négligeable.
