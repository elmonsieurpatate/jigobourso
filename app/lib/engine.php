<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/http.php';

// Appelle le moteur Python (python -m engine.cli <commande>) : JSON sur stdin, JSON sur stdout.
function engine_call(string $command, array $request) {
    $env = [];
    foreach (['JIGO_DB_HOST', 'JIGO_DB_PORT', 'JIGO_DB_NAME', 'JIGO_DB_USER', 'JIGO_DB_PASSWORD', 'PATH', 'HOME'] as $k) {
        $v = cfg($k);
        if ($v !== null) $env[$k] = $v;
    }
    $env['PYTHONPATH'] = engine_root();
    $proc = proc_open([python_bin(), '-m', 'engine.cli', $command], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, engine_root(), $env + ['PYTHONPATH' => engine_root()]);
    if (!is_resource($proc)) throw new ApiError('Moteur d’analyse indisponible', 503);
    fwrite($pipes[0], json_encode($request, JSON_UNESCAPED_UNICODE));
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    $code = proc_close($proc);
    $data = json_decode($stdout, true);
    if ($code === 2 && is_array($data) && isset($data['error'])) throw new ApiError($data['error'], 422);
    if ($code !== 0 || !is_array($data)) {
        error_log('engine ' . $command . ' code ' . $code . ': ' . substr($stderr, -400));
        throw new ApiError('Le moteur d’analyse n’a pas répondu', 503);
    }
    return $data;
}

// Lance le moteur en tâche de fond (le cron web ne doit pas attendre la fin du tick). Renvoie le PID.
function engine_spawn(string $command, string $log, array $args = []): int {
    if (!function_exists('proc_open')) throw new ApiError('proc_open indisponible sur cet hébergement', 503);
    $sh = 'nohup ' . escapeshellarg(python_bin()) . ' -m engine.cli ' . escapeshellarg($command) . implode('', array_map(fn($a) => ' ' . escapeshellarg((string)$a), $args)) . ' >> ' . escapeshellarg($log) . ' 2>&1 < /dev/null & echo $!';
    $env = [];
    foreach (['JIGO_DB_HOST', 'JIGO_DB_PORT', 'JIGO_DB_NAME', 'JIGO_DB_USER', 'JIGO_DB_PASSWORD', 'JIGO_DATA_DIR', 'PATH', 'HOME'] as $k) {
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
