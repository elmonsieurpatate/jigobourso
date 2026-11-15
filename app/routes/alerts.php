<?php
// Centre d'alertes : règles par position (héritées d'une stratégie ou personnelles), historique, stratégie d'origine des achats, stratégie de surveillance.
// Chaque requête est bornée à l'utilisateur connecté et à ses portefeuilles. Aucune vente automatique : une règle ne fait que signaler.
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/alerts.php';
require_once __DIR__ . '/../services/ct_strategies.php';
require_once __DIR__ . '/../services/portfolio_access.php';
require_once __DIR__ . '/../services/ledger.php';

require_once __DIR__ . '/../services/alerts_actions.php';

return [
    'alerts/state' => function () { $u = require_user(); return alerts_state($u, $_GET); },
    'alerts/rule-save' => function () { need_post(); $u = require_user(); return alerts_rule_save($u, body()); },
    'alerts/rule-toggle' => function () { need_post(); $u = require_user(); return alerts_rule_toggle($u, body()); },
    'alerts/rule-delete' => function () { need_post(); $u = require_user(); return alerts_rule_delete($u, body()); },
    'alerts/rule-ack' => function () { need_post(); $u = require_user(); return alerts_rule_ack($u, body()); },
    'alerts/rule-rearm' => function () { need_post(); $u = require_user(); return alerts_rule_rearm($u, body()); },
    'alerts/rule-restore' => function () { need_post(); $u = require_user(); return alerts_rule_restore($u, body()); },
    // Modèle de surveillance d'une stratégie appliqué à une position : ajoute les règles manquantes ; en mode « sync », met à jour les règles héritées non modifiées et conserve les personnalisées.
    'alerts/apply-template' => function () { need_post(); $u = require_user(); return alerts_apply_template($u, body()); },
    // Stratégie d'origine d'un achat, renseignée à la main quand elle est inconnue (jamais inventée, jamais réécrite si déjà connue par l'achat).
    'alerts/origin' => function () { need_post(); $u = require_user(); return alerts_origin($u, body()); },
    'alerts/refresh' => function () {
        need_post(); require_user();
        return ['disabled' => true, 'rules' => 0, 'triggered' => 0];   // ancien moteur désactivé : aucune évaluation
    },
    'alerts/prefs' => function () { need_post(); $u = require_user(); return alerts_prefs($u, body()); },
];
