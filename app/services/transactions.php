<?php
require_once __DIR__ . '/ledger.php';
require_once __DIR__ . '/../lib/http.php';

// A price is expressed in a unit, not just a currency. GBX is the canonical pence code.
function price_unit($unit): ?string {
    if ($unit !== null && !is_string($unit)) throw new ApiError('Devise invalide', 422);
    if ($unit === null || trim($unit) === '') return null;
    if ($unit === 'GBp' || strtoupper($unit) === 'GBX') return 'GBX';
    $unit = strtoupper(trim($unit));
    if (!preg_match('/^[A-Z]{3}$/', $unit)) throw new ApiError('Devise invalide', 422);
    return $unit;
}
function historical_fx(?string $unit, string $when, ?float $explicit): float {
    $unit = price_unit($unit);
    if ($explicit !== null) {
        if (!is_finite($explicit) || round($explicit, 10) <= 0 || $explicit >= 1e10) throw new ApiError('Le taux de change doit être strictement positif', 422);
        if ($unit === 'EUR' && abs($explicit - 1) > 1e-10) throw new ApiError('Le taux EUR doit être égal à 1', 422);
        return $explicit;
    }
    if ($unit === 'EUR') return 1.0;
    if (!$unit) throw new ApiError('Devise manquante : précisez la devise et le change historique', 422);
    $base = $unit === 'GBX' ? 'GBP' : $unit;
    $date = substr($when, 0, 10);
    $r = q('SELECT rate_date, to_eur FROM fx_rates WHERE currency = ? AND rate_date <= ? ORDER BY rate_date DESC LIMIT 1', [$base, $date])->fetch();
    // A weekend can use the preceding rate, but never a future rate or a remote historical guess.
    if (!$r || (strtotime($date) - strtotime($r['rate_date'])) > 7 * 86400 || (float)$r['to_eur'] <= 0)
        throw new ApiError('Taux historique indisponible à cette date : renseignez le taux vers l’euro (pour une unité du prix)', 422);
    return (float)$r['to_eur'] / ($unit === 'GBX' ? 100 : 1);
}
function transaction_key(array $t): string {
    return !empty($t['listing_id']) ? 'L' . $t['listing_id'] : 'S' . strtoupper($t['symbol']);
}
function validate_transaction_history(array $rows): void {
    usort($rows, function ($a, $b) { return [$a['trade_at'], (int)$a['id']] <=> [$b['trade_at'], (int)$b['id']]; });
    $held = [];
    foreach ($rows as $t) {
        $k = transaction_key($t); $qty = (float)$t['quantity'];
        $have = $held[$k] ?? 0.0;
        if ($t['side'] === 'sell' && $qty > $have + 1e-9)
            throw new ApiError('Vente supérieure à la quantité détenue à la date du ' . $t['trade_at'] . ' (' . $t['symbol'] . ')', 422);
        $held[$k] = $have + ($t['side'] === 'buy' ? $qty : -$qty);
    }
}
// All writers take the same portfolio row lock before reading the ledger: concurrent writes serialize.
function write_transaction(int $userId, int $portfolioId, callable $change): array {
    $db = db(); $db->beginTransaction();
    try {
        $p = q('SELECT id FROM portfolios WHERE id = ? AND user_id = ? FOR UPDATE', [$portfolioId, $userId])->fetch();
        if (!$p) throw new ApiError('Portefeuille introuvable', 404);
        $rows = q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id FOR UPDATE', [$portfolioId])->fetchAll();
        $result = $change($rows);
        $after = q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id', [$portfolioId])->fetchAll();
        validate_transaction_history($after);
        $db->commit(); return $result;
    } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); throw $e; }
}
