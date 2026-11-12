<?php
require_once __DIR__ . '/../lib/auth.php';

function own_portfolio(int $id, array $user): array {
    $p = q('SELECT * FROM portfolios WHERE id = ? AND user_id = ?', [$id, $user['id']])->fetch();
    if (!$p) throw new ApiError('Portefeuille introuvable', 404);
    return $p;
}
