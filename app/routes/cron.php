<?php
require_once __DIR__ . '/../lib/engine.php';

// Appelé par la tâche planifiée de l'hébergeur (wget/curl) : https://…/api/cron?k=<clé>.
// La clé est lue dans un fichier hors de la racine web (JIGO_CRON_KEY_FILE) ; l'ancien nom d'URL reste accepté.
// Appel refusé : noté dans logs/cron-rejets.log (visible dans l'administration, page Cron) pour qu'une mauvaise clé ou une clé absente ne passe pas inaperçue.
function cron_reject(string $why, int $code): void {
    $dir = cfg('JIGO_LOG_DIR', engine_root() . '/logs');
    if (!is_dir($dir)) @mkdir($dir, 0700, true);
    @file_put_contents($dir . '/cron-rejets.log', gmdate('Y-m-d H:i:s') . ' UTC · ' . $why . ' · ' . substr((string)($_SERVER['REMOTE_ADDR'] ?? '?'), 0, 45) . "\n", FILE_APPEND | LOCK_EX);
    throw new ApiError($why, $code);
}

function cron_tick(): array {
    if ($_SERVER['REQUEST_METHOD'] !== 'GET') cron_reject('Méthode refusée (le cron doit appeler en GET)', 405);
    $file = cfg('JIGO_CRON_KEY_FILE', '');
    $key = ($file !== '' && is_file($file)) ? trim((string)file_get_contents($file)) : '';
    if ($key === '') cron_reject('Clé cron absente sur le serveur', 503);
    if (!hash_equals($key, (string)($_GET['k'] ?? ''))) cron_reject('Clé invalide', 403);
    $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/cron.log';
    if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
    return ['ok' => true, 'message' => 'Tick détaché ; le résultat est enregistré dans la table jobs.', 'pid' => engine_spawn('tick', $log)];
}

return ['cron' => 'cron_tick', 'yahoo-history-cron' => 'cron_tick'];
