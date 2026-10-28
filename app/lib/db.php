<?php
require_once __DIR__ . '/config.php';

function db(): PDO {
    static $pdo = null;
    if ($pdo) return $pdo;
    $dsn = 'mysql:host=' . cfg('JIGO_DB_HOST', '127.0.0.1') . ';port=' . cfg('JIGO_DB_PORT', '3306') . ';dbname=' . cfg('JIGO_DB_NAME', '') . ';charset=utf8mb4';
    $pdo = new PDO($dsn, cfg('JIGO_DB_USER', ''), cfg('JIGO_DB_PASSWORD', ''), [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    $pdo->exec("SET time_zone = '+00:00'");
    return $pdo;
}
function q(string $sql, array $args = []): PDOStatement {
    $st = db()->prepare($sql);
    $st->execute($args);
    return $st;
}
function now_utc(): string { return gmdate('Y-m-d H:i:s'); }
