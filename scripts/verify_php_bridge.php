<?php
// Contrôle (lecture seule) du pont PHP → moteur d'analyse, tel que l'API l'utilise : profils, Explorer, fiche et Suivi pour les deux stratégies Momentum.
// Usage : JIGO_DB_* dans l'environnement ; JIGO_ENGINE_ROOT et JIGO_PYTHON si besoin.   php scripts/verify_php_bridge.php   (code de sortie 0 = tout est cohérent)
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require_once __DIR__ . '/../app/lib/config.php';
require_once __DIR__ . '/../app/lib/engine.php';
$problems = [];
function check(bool $ok, string $what, array &$problems): void { echo ($ok ? 'ok     ' : 'ÉCHEC  ') . $what . "\n"; if (!$ok) $problems[] = $what; }
try {
    $p = engine_call('presets', []);
    check(array_keys($p['presets']) === ['regular', 'fast', 'recovery', 'low_volatility', 'momentum', 'momentum12'] && $p['experimental'] === ['momentum', 'momentum12'], 'presets : six stratégies, deux momentums à l\'essai', $problems);
    $first = null;
    foreach (['momentum', 'momentum12', 'regular'] as $name) {
        $r = engine_call('explore', ['config' => $name, 'view' => ['status' => 'retained', 'kind' => 'equity', 'page_size' => 20]]);
        $rows = $r['rows'] ?? [];
        check(($r['config']['name'] ?? '') === $name && count($rows) > 0, "Explorer $name : " . ($r['total'] ?? '?') . ' retenus, premier ' . ($rows[0]['symbol'] ?? '—') . (isset($rows[0]['momentum']) ? ' (' . round($rows[0]['momentum']) . ' %)' : ''), $problems);
        if ($name === 'momentum12' && $rows) $first = $rows[0]['id'];
    }
    if ($first) {
        $s = engine_call('sheet', ['id' => $first, 'config' => $p['presets']['momentum12']]);
        check(($s['strategy']['experimental'] ?? false) === true && ($s['strategy']['ranking'] ?? '') === 'momentum12' && isset($s['state']['momentum_12m']) && isset($s['state']['momentum_6m']), 'fiche : deux momentums exposés, profil à l\'essai', $problems);
    }
    $t = engine_call('suivi', []);
    check(($t['horizons'] ?? []) === [1, 3, 5, 21, 63], 'Suivi : horizons 1, 3, 5, 21 et 63 séances', $problems);
} catch (Throwable $e) {
    $problems[] = get_class($e) . ' : ' . $e->getMessage();
    echo 'ÉCHEC  ' . $e->getMessage() . "\n";
}
echo $problems ? 'PONT PHP : ' . count($problems) . " problème(s)\n" : "PONT PHP : tout est cohérent\n";
exit($problems ? 1 : 0);
