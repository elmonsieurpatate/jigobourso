<?php
// Plan de suivi : libellés des stratégies et correspondance avec les modèles du moteur.
require_once __DIR__ . '/ct_strategies.php';

// identifiants de la page Classement -> modèles du moteur (mêmes sept stratégies)
const TRACK_PRESET = ['fast' => 'fast', 'regular' => 'regular', 'calm' => 'low_volatility', 'rebound' => 'recovery', 'mom6' => 'momentum', 'mom12' => 'momentum12', 'momrisk' => 'momentum_risk'];
const TRACK_RULES = ['stop', 'recul', 'trend', 'risk', 'target'];
const TRACK_LABEL = ['fast' => 'Croissance rapide', 'regular' => 'Croissance régulière', 'calm' => 'Hausse calme', 'rebound' => 'Rebond', 'mom6' => 'Momentum 6 mois', 'mom12' => 'Momentum 12 mois', 'momrisk' => 'Momentum ajusté au risque'];

function track_custom_names(int $uid): array {
    $out = [];
    foreach ((ct_all($uid)['items'] ?? []) as $it) if (empty($it['builtin'])) $out[$it['id']] = $it['name'] ?? $it['id'];
    return $out;
}
function track_label(string $key, array $custom): string { return TRACK_LABEL[$key] ?? ($custom[$key] ?? $key); }
