<?php
// Entrées/sorties HTTP de l'API : JSON uniquement.
class ApiError extends Exception {
    public $status;
    public function __construct(string $message, int $status = 400) { parent::__construct($message); $this->status = $status; }
}
// Identifiant de requête : renvoyé dans l'en-tête X-Request-Id et dans les erreurs 500 (champ « ref »), repris dans les journaux serveur.
function request_id(): string {
    static $id = null;
    return $id ??= bin2hex(random_bytes(4));
}
// Encode la réponse AVANT d'envoyer statut et en-têtes : une donnée inencodable ne doit jamais partir avec un code de succès.
// UTF-8 invalide remplacé (jamais de sortie tronquée en silence) ; toute autre erreur d'encodage donne un 500 explicite ($status modifié).
function json_text($data, int &$status = 200): string {
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    if ($json === false) {
        error_log('json_text [' . request_id() . '] : ' . json_last_error_msg());
        $status = 500;
        return '{"error":"Réponse illisible (erreur d\'encodage)","ref":"' . request_id() . '"}';
    }
    return $json;
}
function json_headers(int $status): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Request-Id: ' . request_id());
}
function out($data, int $status = 200): void {
    $json = json_text($data, $status);
    json_headers($status);
    echo $json;
    exit;
}
// Envoie la réponse, puis exécute $after sans faire attendre le client (travail lent : e-mail). Sans fin de requête anticipée
// (serveur de développement, tests), $after s'exécute avant la réponse pour que le comportement reste déterministe.
function out_then($data, callable $after, int $status = 200): void {
    ignore_user_abort(true);
    $finish = function_exists('fastcgi_finish_request') ? 'fastcgi_finish_request' : (function_exists('litespeed_finish_request') ? 'litespeed_finish_request' : null);
    $run = function () use ($after) { try { $after(); } catch (Throwable $e) { error_log('after-response: ' . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine()); } };
    if (!$finish) { $run(); out($data, $status); }
    $json = json_text($data, $status);
    json_headers($status);
    header('Content-Length: ' . strlen($json));
    echo $json;
    $finish();
    $run();
    exit;
}
const BODY_MAX = 2 * 1024 * 1024;
function body(): array {
    static $b = null;
    if ($b !== null) return $b;
    // Taille bornée avant toute lecture : au-delà, 413 (aucune route ne reçoit plus de BODY_MAX octets).
    if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > BODY_MAX) throw new ApiError('Requête trop volumineuse', 413);
    $raw = file_get_contents('php://input', false, null, 0, BODY_MAX + 1);
    if ($raw === '' || $raw === false) return $b = [];
    if (strlen($raw) > BODY_MAX) throw new ApiError('Requête trop volumineuse', 413);
    // Corps JSON obligatoire : un formulaire HTML classique (text/plain, x-www-form-urlencoded) ne peut pas atteindre l'API depuis un autre site sans pré-vérification CORS.
    if (stripos((string)($_SERVER['CONTENT_TYPE'] ?? $_SERVER['HTTP_CONTENT_TYPE'] ?? ''), 'application/json') !== 0) throw new ApiError('Content-Type application/json requis', 415);
    $d = json_decode($raw, true);
    if (!is_array($d)) throw new ApiError('Corps JSON invalide');
    return $b = $d;
}
function need_post(): void {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') throw new ApiError('Méthode POST requise', 405);
    // Contrôle d'origine : une écriture doit venir de ce site.
    // Origin sinon Referer (certains navigateurs omettent Origin) ; ni l'un ni l'autre : refus, un navigateur envoie toujours l'un des deux sur un POST.
    $source = ($_SERVER['HTTP_ORIGIN'] ?? '') !== '' ? $_SERVER['HTTP_ORIGIN'] : ($_SERVER['HTTP_REFERER'] ?? '');
    if ($source === '') throw new ApiError('Origine absente', 403);
    $port = parse_url($source, PHP_URL_PORT);
    $host = parse_url($source, PHP_URL_HOST) . ($port ? ':' . $port : '');
    if (strcasecmp($host, $_SERVER['HTTP_HOST'] ?? '') !== 0) throw new ApiError('Origine refusée', 403);
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
