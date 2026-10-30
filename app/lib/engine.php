<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/http.php';

const ENGINE_TIMEOUT = 90;     // secondes : au-delà, le processus est arrêté et l'appel échoue proprement
const ENGINE_SLOTS = 4;        // appels simultanés au plus (hébergement mutualisé) ; les suivants attendent quelques secondes puis reçoivent un 503

// Réserve l'un des ENGINE_SLOTS emplacements (verrou fichier, libéré à la fin du processus PHP ou par engine_release).
function engine_acquire(float $wait = 8.0) {
    $dir = cfg('JIGO_DATA_DIR', sys_get_temp_dir());
    if (!is_dir($dir) || !is_writable($dir)) $dir = sys_get_temp_dir();
    $deadline = microtime(true) + $wait;
    do {
        for ($i = 0; $i < ENGINE_SLOTS; $i++) {
            $fh = @fopen($dir . '/.engine-slot-' . $i . '.lock', 'c');
            if ($fh && flock($fh, LOCK_EX | LOCK_NB)) return $fh;
            if ($fh) fclose($fh);
        }
        usleep(100000);
    } while (microtime(true) < $deadline);
    throw new ApiError('Le moteur d’analyse est occupé : réessayez dans un instant.', 503);
}
function engine_release($fh): void { if (is_resource($fh)) { flock($fh, LOCK_UN); fclose($fh); } }

// Appelle le moteur Python (python -m engine.cli <commande>) : JSON sur stdin, JSON sur stdout, délai maximal ENGINE_TIMEOUT.
// stderr va dans un fichier temporaire (jamais dans un tube : un tube plein bloquerait les deux processus).
function engine_call(string $command, array $request) {
    $env = [];
    foreach (['JIGO_DB_HOST', 'JIGO_DB_PORT', 'JIGO_DB_SOCKET', 'JIGO_DB_NAME', 'JIGO_DB_USER', 'JIGO_DB_PASSWORD', 'PATH', 'HOME'] as $k) {
        $v = cfg($k);
        if ($v !== null) $env[$k] = $v;
    }
    $env['PYTHONPATH'] = engine_root();
    $slot = engine_acquire();
    $errFile = tempnam(sys_get_temp_dir(), 'jigo-eng-');
    try {
        $proc = proc_open([python_bin(), '-m', 'engine.cli', $command], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['file', $errFile, 'w']], $pipes, engine_root(), $env + ['PYTHONPATH' => engine_root()]);
        if (!is_resource($proc)) throw new ApiError('Moteur d’analyse indisponible', 503);
        // La requête est petite ; l'écriture ne bloque pas (tube de 64 Ko) sauf requête énorme, bornée par body() côté PHP.
        fwrite($pipes[0], json_encode($request, JSON_UNESCAPED_UNICODE));
        fclose($pipes[0]);
        stream_set_blocking($pipes[1], false);
        $stdout = '';
        $deadline = microtime(true) + (float)cfg('JIGO_ENGINE_TIMEOUT', ENGINE_TIMEOUT);
        $timedOut = false;
        while (true) {
            $r = [$pipes[1]]; $w = $e = null;
            $left = $deadline - microtime(true);
            if ($left <= 0) { $timedOut = true; break; }
            if (stream_select($r, $w, $e, 0, (int)min(500000, $left * 1e6)) === false) break;
            $chunk = fread($pipes[1], 65536);
            if ($chunk !== false && $chunk !== '') $stdout .= $chunk;
            if (feof($pipes[1])) break;
        }
        fclose($pipes[1]);
        if ($timedOut) { proc_terminate($proc, 9); proc_close($proc); error_log('engine ' . $command . ': délai dépassé'); throw new ApiError('Le moteur d’analyse a mis trop de temps à répondre.', 503); }
        $code = proc_close($proc);
        $stderr = (string)@file_get_contents($errFile, false, null, max(0, (int)@filesize($errFile) - 400));
    } finally {
        @unlink($errFile);
        engine_release($slot);
    }
    $data = json_decode($stdout, true);
    if ($code === 2 && is_array($data) && isset($data['error'])) throw new ApiError($data['error'], 422);
    if ($code !== 0 || !is_array($data)) {
        error_log('engine ' . $command . ' code ' . $code . ': ' . $stderr);
        throw new ApiError('Le moteur d’analyse n’a pas répondu', 503);
    }
    return $data;
}

// Lance le moteur en tâche de fond (le cron web ne doit pas attendre la fin du tick). Renvoie le PID.
function engine_spawn(string $command, string $log, array $args = []): int {
    if (!function_exists('proc_open')) throw new ApiError('proc_open indisponible sur cet hébergement', 503);
    $sh = 'nohup ' . escapeshellarg(python_bin()) . ' -m engine.cli ' . escapeshellarg($command) . implode('', array_map(fn($a) => ' ' . escapeshellarg((string)$a), $args)) . ' >> ' . escapeshellarg($log) . ' 2>&1 < /dev/null & echo $!';
    $env = [];
    foreach (['JIGO_DB_HOST', 'JIGO_DB_PORT', 'JIGO_DB_SOCKET', 'JIGO_DB_NAME', 'JIGO_DB_USER', 'JIGO_DB_PASSWORD', 'JIGO_DATA_DIR', 'JIGO_BACKUP_DIR', 'JIGO_FDB_REF', 'PATH', 'HOME'] as $k) {
        $v = cfg($k);
        if ($v !== null) $env[$k] = $v;
    }
    $env['PYTHONPATH'] = engine_root();
    $proc = @proc_open(['/bin/sh', '-c', $sh], [0 => ['file', '/dev/null', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, engine_root(), $env, ['bypass_shell' => true]);
    if (!is_resource($proc)) throw new ApiError('Impossible de démarrer le moteur', 503);
    $pid = trim((string)stream_get_contents($pipes[1]));
    fclose($pipes[1]); fclose($pipes[2]);
    $code = proc_close($proc);
    if ($code !== 0 || !preg_match('/^[1-9][0-9]*$/', $pid)) throw new ApiError('Le moteur ne s’est pas lancé correctement', 503);
    return (int)$pid;
}
