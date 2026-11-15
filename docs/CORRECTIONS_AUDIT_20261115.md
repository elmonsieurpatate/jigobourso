# Corrections de l'audit de main — 15 novembre 2026

Base : `2bb2cec`. Référence : `AUDIT_MAIN_20261115.md`.
Une case n'est cochée qu'avec une modification et une vérification identifiées.
Les mesures nécessitant l'hébergement ou un appareil réel restent distinguées des
corrections locales.

- [x] A01 — Délai global du moteur, échanges non bloquants et nettoyage.
- [x] A02 — Restaurations liées à leur manifeste, échec explicite si incohérentes.
- [ ] A03 — Aperçus automatiques : erreurs visibles et reprise possible.
- [ ] A04 — Séparation effective structure / composants / mise en page métier.
- [ ] A05 — Garde-fou CSS structurel et tests négatifs.
- [ ] A06 — Cas d'usage PHP hors des routes, contrats et garde-fous communs.
- [ ] A07 — Contrôleurs JS séparés par responsabilité.
- [ ] A08 — Validation commune PR/main sans secret de production côté PR.
- [ ] A09 — Runner des parcours actifs, scénarios historiques classés.
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
