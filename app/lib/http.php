<?php
// Entrées/sorties HTTP de l'API : JSON uniquement.
class ApiError extends Exception {
    public $status;
    public function __construct(string $message, int $status = 400) { parent::__construct($message); $this->status = $status; }
}
function out($data, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PARTIAL_OUTPUT_ON_ERROR);
    exit;
}
// Envoie la réponse, puis exécute $after sans faire attendre le client (travail lent : e-mail). Sans fin de requête anticipée
// (serveur de développement, tests), $after s'exécute avant la réponse pour que le comportement reste déterministe.
function out_then($data, callable $after, int $status = 200): void {
    ignore_user_abort(true);
    $finish = function_exists('fastcgi_finish_request') ? 'fastcgi_finish_request' : (function_exists('litespeed_finish_request') ? 'litespeed_finish_request' : null);
    $run = function () use ($after) { try { $after(); } catch (Throwable $e) { error_log('after-response: ' . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine()); } };
    if (!$finish) { $run(); out($data, $status); }
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PARTIAL_OUTPUT_ON_ERROR);
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('Content-Length: ' . strlen((string)$json));
    echo $json;
    $finish();
    $run();
    exit;
}
function body(): array {
    static $b = null;
    if ($b !== null) return $b;
    $raw = file_get_contents('php://input');
    if ($raw === '' || $raw === false) return $b = [];
    $d = json_decode($raw, true);
    if (!is_array($d)) throw new ApiError('Corps JSON invalide');
    return $b = $d;
}
function need_post(): void {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') throw new ApiError('Méthode POST requise', 405);
    // Contrôle d'origine : une écriture doit venir de ce site.
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($origin !== '') {
        $host = parse_url($origin, PHP_URL_HOST) . (parse_url($origin, PHP_URL_PORT) ? ':' . parse_url($origin, PHP_URL_PORT) : '');
        if (strcasecmp($host, $_SERVER['HTTP_HOST'] ?? '') !== 0) throw new ApiError('Origine refusée', 403);
    }
}
function str_in(array $a, string $k, int $max = 200, bool $required = true): string {
    $v = isset($a[$k]) && is_scalar($a[$k]) ? trim((string)$a[$k]) : '';
    if ($required && $v === '') throw new ApiError("Champ « $k » requis");
    if (mb_strlen($v) > $max) throw new ApiError("Champ « $k » trop long");
    return $v;
}
// Montants et quantités : borne haute commune, très en dessous de la capacité des colonnes DECIMAL(24,8).
const NUM_MAX = 1e12;
function num_in(array $a, string $k, bool $required = true, ?float $min = null, float $max = NUM_MAX) {
    if (!isset($a[$k]) || $a[$k] === '' || $a[$k] === null) {
        if ($required) throw new ApiError("Champ « $k » requis");
        return null;
    }
    $v = is_string($a[$k]) ? str_replace(',', '.', $a[$k]) : $a[$k];
    if (!is_numeric($v) || !is_finite((float)$v)) throw new ApiError("Champ « $k » numérique attendu");
    if ($min !== null && (float)$v < $min) throw new ApiError("Champ « $k » trop petit");
    if ((float)$v > $max) throw new ApiError("Champ « $k » trop grand");
    return (float)$v;
}
