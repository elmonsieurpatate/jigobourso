<?php
// Point d'entrée unique de l'API : /api.php?r=<route>
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
set_error_handler(function ($no, $str, $file, $line) { throw new ErrorException($str, 0, $no, $file, $line); });
try {
    $routes = [];
    foreach (['auth', 'explore', 'portfolios', 'admin', 'cron'] as $group) $routes += require __DIR__ . '/../routes/' . $group . '.php';
    $route = (string)($_GET['r'] ?? '');
    if (!isset($routes[$route])) throw new ApiError('Route inconnue', 404);
    out($routes[$route]());
} catch (ApiError $e) {
    out(['error' => $e->getMessage()], $e->status);
} catch (Throwable $e) {
    error_log('api ' . ($_GET['r'] ?? '?') . ': ' . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine());
    out(['error' => 'Erreur interne'], 500);
}
