<?php
require_once __DIR__ . '/http.php';

/** Échange non bloquant : la même deadline couvre stdin, stdout et la sortie.
 * Le propriétaire ferme toujours les tubes et récolte le processus, y compris
 * lorsqu'un moteur ferme stdout avant de s'arrêter ou ne lit jamais son entrée.
 */
function engine_exchange($proc, array $pipes, string $payload, float $deadline): array {
    $stdout = ''; $offset = 0; $exitCode = null;
    stream_set_blocking($pipes[0], false);
    stream_set_blocking($pipes[1], false);
    try {
        while (true) {
            $status = proc_get_status($proc);
            if (!$status['running'] && $status['exitcode'] >= 0) $exitCode = $status['exitcode'];
            if (is_resource($pipes[0]) && ($offset === strlen($payload) || !$status['running'])) fclose($pipes[0]);
            if (is_resource($pipes[1]) && feof($pipes[1])) fclose($pipes[1]);
            if (!$status['running'] && !is_resource($pipes[1])) break;
            $left = $deadline - microtime(true);
            if ($left <= 0) throw new ApiError('Le moteur d’analyse a mis trop de temps à répondre.', 503);
            $read = is_resource($pipes[1]) ? [$pipes[1]] : [];
            $write = is_resource($pipes[0]) ? [$pipes[0]] : [];
            $except = null;
            if (!$read && !$write) { usleep((int)min(10000, $left * 1e6)); continue; }
            if (stream_select($read, $write, $except, 0, (int)min(100000, $left * 1e6)) === false)
                throw new ApiError('Échange avec le moteur d’analyse interrompu.', 503);
            if ($read) {
                $chunk = fread($pipes[1], 65536);
                if ($chunk === false) throw new ApiError('Réponse du moteur d’analyse interrompue.', 503);
                $stdout .= $chunk;
            }
            if ($write) {
                $n = fwrite($pipes[0], substr($payload, $offset, 65536));
                if ($n === false) throw new ApiError('Entrée du moteur d’analyse interrompue.', 503);
                $offset += $n;
            }
        }
        // proc_get_status récolte le code sur PHP 8.1/8.2 ; proc_close peut alors
        // retourner -1. Garder le code observé avant de fermer la ressource.
        return [$stdout, $exitCode];
    } catch (ApiError $e) {
        throw $e;
    } catch (Throwable $e) {
        error_log('engine exchange [' . request_id() . ']: ' . get_class($e));
        throw new ApiError('Échange avec le moteur d’analyse interrompu.', 503);
    } finally {
        foreach ($pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
        if (is_resource($proc)) {
            if (proc_get_status($proc)['running']) proc_terminate($proc, 9);
            proc_close($proc);
        }
    }
}
