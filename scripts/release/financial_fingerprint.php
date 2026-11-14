<?php
// CLI only, SELECT only. Empreinte des transactions AVANT livraison : ce script est envoyé sur le serveur par l'entrée standard (ops/deploy.sh) et ne dépend
// que de db.php, jamais du reste du code applicatif (qui est encore l'ancienne version à ce moment). Même empreinte et mêmes effectifs que
// check_financial_integrity.php, que la livraison compare ensuite (transactions et portefeuilles conservés).
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/../../app/lib/db.php';
$db = db();
$db->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
$db->exec('START TRANSACTION READ ONLY');
try {
    $rows = q('SELECT * FROM portfolio_transactions ORDER BY portfolio_id, trade_at, id')->fetchAll();
    $count = (int)q('SELECT COUNT(*) FROM portfolios')->fetchColumn();
    echo json_encode(['at_utc' => gmdate('c'), 'portfolios' => $count, 'transactions' => count($rows), 'fingerprint' => hash('sha256', json_encode($rows)), 'issues' => []], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
} finally { $db->rollBack(); }
