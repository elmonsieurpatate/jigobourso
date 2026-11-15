<?php
// Plan de suivi des positions : tendance, risque, protection indicative et conseil (moteur : engine/analytics/portfolio/position_plan.py).
// Lecture seule pour les données financières : rien n'est vendu, aucun niveau personnel n'est modifié, aucune transaction n'est touchée.
// Écritures, toujours à la demande explicite de l'utilisateur et sur UNE position : stratégie de surveillance (position_watch), filet de protection et objectif personnels (position_levels),
// réglage des règles (position_plan_rules : activation, seuil de recul personnalisé). Jamais les transactions, les lots, ni les anciennes règles d'alerte (alert_rules).
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/transactions.php';
require_once __DIR__ . '/../services/ct_strategies.php';
require_once __DIR__ . '/../services/portfolio_access.php';
require_once __DIR__ . '/../services/ledger.php';
require_once __DIR__ . '/../services/tracking.php';

return [
    'tracking/state' => function () { return tracking_state(require_user(), (int)($_GET['portfolio'] ?? 0)); },
    // Réglage d'UNE règle d'UNE position : mode automatique (valeur calculée par le moteur) ou personnalisé, activation. Ne touche jamais aux autres règles.
    //   stop : valeur = filet de protection personnel (devise de cotation, position_levels.stop_px) ; auto = repasse au calcul automatique
    //   target : valeur = objectif de gain personnel facultatif (position_levels.target_px) ; auto = aucun objectif
    //   recul : valeur = seuil personnel de recul depuis le sommet, en % (0 à 100 exclus) ; auto = seuil calculé
    //   trend, risk : activation seulement
    'tracking/rules' => function () { need_post(); $u = require_user(); return tracking_rules($u, body()); },
    // Change la stratégie de surveillance d'UNE position (jamais les achats, leurs stratégies d'origine, ni les protections personnelles).
    'tracking/strategy' => function () { need_post(); $u = require_user(); return tracking_strategy($u, body()); },
];
