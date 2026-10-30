"""Moteur Jigobourso. Hébergement mutualisé : une seule thread par bibliothèque de calcul (OpenBLAS tente sinon d'en créer des dizaines et l'hébergeur refuse).
Ce réglage est posé ici, avant tout chargement de numpy, quel que soit le point d'entrée (cron, déploiement, scripts, tests)."""
import os

for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
