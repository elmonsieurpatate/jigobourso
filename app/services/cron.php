<?php
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/config.php';
require_once __DIR__ . '/../lib/engine.php';

// Appelé par la tâche planifiée de l'hébergeur : wget -q -O /dev/null --header='X-Cron-Key: <clé>' https://…/api/cron
// La clé est lue dans un fichier hors de la racine web (JIGO_CRON_KEY_FILE) et ne passe que par l'en-tête (jamais dans l'URL, donc jamais dans les journaux d'accès).
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
function cron_presented_key(): string {
    return (string)($_SERVER['HTTP_X_CRON_KEY'] ?? '');
}

function cron_tick(): array {
    if ($_SERVER['REQUEST_METHOD'] !== 'GET') cron_reject('Méthode refusée (le cron doit appeler en GET)', 405);
    $file = cfg('JIGO_CRON_KEY_FILE', '');
    $key = ($file !== '' && is_file($file)) ? trim((string)file_get_contents($file)) : '';
    if ($key === '') cron_reject('Clé cron absente sur le serveur', 503);
    if (!hash_equals($key, cron_presented_key())) cron_reject('Clé invalide', 403);
    $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/cron.log';
    if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
    // Plus d'e-mails d'alertes : l'ancien moteur est désactivé (le Plan de suivi n'envoie aucune notification).
    return ['ok' => true, 'message' => 'Tick détaché ; le résultat est enregistré dans la table jobs.', 'pid' => engine_spawn('tick', $log)];
}
