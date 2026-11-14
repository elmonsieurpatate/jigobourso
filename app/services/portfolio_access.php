<?php
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';

function own_portfolio(int $id, array $user): array {
    $p = q('SELECT * FROM portfolios WHERE id = ? AND user_id = ?', [$id, $user['id']])->fetch();
    if (!$p) throw new ApiError('Portefeuille introuvable', 404);
    return $p;
}
// Transaction appartenant à un portefeuille de l'utilisateur (id et portefeuille) ; 404 sinon, sans distinguer « absente » de « à un autre ».
function own_transaction(int $id, array $user): array {
    $t = q('SELECT t.id, t.portfolio_id FROM portfolio_transactions t JOIN portfolios p ON p.id = t.portfolio_id WHERE t.id = ? AND p.user_id = ?', [$id, $user['id']])->fetch();
    if (!$t) throw new ApiError('Transaction introuvable', 404);
    return $t;
}
