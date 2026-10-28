<?php
require_once __DIR__ . '/../lib/engine.php';

// Appelé par la tâche planifiée de l'hébergeur (wget/curl) : https://…/api/cron?k=<clé>.
// La clé est lue dans un fichier hors de la racine web (JIGO_CRON_KEY_FILE) ; l'ancien nom d'URL reste accepté.
function cron_tick(): array {
    if ($_SERVER['REQUEST_METHOD'] !== 'GET') throw new ApiError('Méthode inconnue', 405);
    $file = cfg('JIGO_CRON_KEY_FILE', '');
    $key = ($file !== '' && is_file($file)) ? trim((string)file_get_contents($file)) : '';
    if ($key === '') throw new ApiError('Clé cron absente sur le serveur', 503);
    if (!hash_equals($key, (string)($_GET['k'] ?? ''))) throw new ApiError('Clé invalide', 403);
    $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/cron.log';
    if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
    return ['ok' => true, 'message' => 'Tick détaché ; le résultat est enregistré dans la table jobs.', 'pid' => engine_spawn('tick', $log)];
}

return ['cron' => 'cron_tick', 'yahoo-history-cron' => 'cron_tick'];
