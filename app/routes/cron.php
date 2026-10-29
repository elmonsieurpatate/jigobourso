<?php
require_once __DIR__ . '/../lib/engine.php';

// Appelé par la tâche planifiée de l'hébergeur (wget/curl) : https://…/api/cron?k=<clé>.
// La clé est lue dans un fichier hors de la racine web (JIGO_CRON_KEY_FILE) ; l'ancien nom d'URL reste accepté.
// Avec wget : wget -q -O /dev/null --header='X-Cron-Key: <clé>' https://…/api/cron (la forme ?k=<clé> reste valable).
// Appel refusé : noté dans logs/cron-rejets.log (visible dans l'administration, page Cron) pour qu'une mauvaise clé ou une clé absente ne passe pas inaperçue.
const CRON_REJECT_LOG_MAX = 262144;     // octets : au-delà, le journal est archivé (un seul .1 conservé), pour qu'un tiers ne puisse pas le faire grossir sans limite
function cron_reject(string $why, int $code): void {
    $dir = cfg('JIGO_LOG_DIR', engine_root() . '/logs');
    if (!is_dir($dir)) @mkdir($dir, 0700, true);
    $file = $dir . '/cron-rejets.log';
    clearstatcache(true, $file);
    if (is_file($file) && filesize($file) > CRON_REJECT_LOG_MAX) @rename($file, $file . '.1');
    @file_put_contents($file, gmdate('Y-m-d H:i:s') . ' UTC · ' . $why . ' · ' . substr((string)($_SERVER['REMOTE_ADDR'] ?? '?'), 0, 45) . "\n", FILE_APPEND | LOCK_EX);
    throw new ApiError($why, $code);
}
// La clé peut être fournie dans l'en-tête X-Cron-Key (préférable : elle n'apparaît pas dans les journaux d'accès) ou, comme avant, dans ?k=.
function cron_presented_key(): string {
    $h = (string)($_SERVER['HTTP_X_CRON_KEY'] ?? '');
    return $h !== '' ? $h : (string)($_GET['k'] ?? '');
}

function cron_tick(): array {
    if ($_SERVER['REQUEST_METHOD'] !== 'GET') cron_reject('Méthode refusée (le cron doit appeler en GET)', 405);
    $file = cfg('JIGO_CRON_KEY_FILE', '');
    $key = ($file !== '' && is_file($file)) ? trim((string)file_get_contents($file)) : '';
    if ($key === '') cron_reject('Clé cron absente sur le serveur', 503);
    if (!hash_equals($key, cron_presented_key())) cron_reject('Clé invalide', 403);
    $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/cron.log';
    if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
    return ['ok' => true, 'message' => 'Tick détaché ; le résultat est enregistré dans la table jobs.', 'pid' => engine_spawn('tick', $log)];
}

return ['cron' => 'cron_tick', 'yahoo-history-cron' => 'cron_tick'];
