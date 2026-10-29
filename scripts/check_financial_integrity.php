<?php
// CLI only, SELECT only. Reports issues without changing or disclosing transaction amounts.
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/../app/lib/db.php';
$db = db();
$db->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
$db->exec('START TRANSACTION READ ONLY');
try {
    $rows = q('SELECT * FROM portfolio_transactions ORDER BY portfolio_id, trade_at, id')->fetchAll();
    $holdings = []; $issues = []; $fingerprint = hash('sha256', json_encode($rows));
    foreach ($rows as $t) {
        $key = $t['portfolio_id'] . ':' . ($t['listing_id'] ? 'L'.$t['listing_id'] : 'S'.strtoupper($t['symbol']));
        $held = $holdings[$key] ?? 0; $qty = (float)$t['quantity'];
        if ($t['side'] === 'sell' && $qty > $held + 1e-9) $issues[] = ['id' => (int)$t['id'], 'code' => 'oversold_at_trade_date'];
        $holdings[$key] = $held + ($t['side'] === 'buy' ? $qty : -$qty);
        if (($t['fx_to_eur'] === null && $t['currency'] !== 'EUR') || ($t['fx_to_eur'] !== null && (float)$t['fx_to_eur'] <= 0))
            $issues[] = ['id' => (int)$t['id'], 'code' => 'historical_fx_unconfirmed'];
        if ($t['currency'] === 'GBP' && $t['listing_id']) {
            $p = q('SELECT currency FROM latest_prices WHERE listing_id = ?', [$t['listing_id']])->fetch();
            if ($p && in_array($p['currency'], ['GBp','GBX'], true)) $issues[] = ['id' => (int)$t['id'], 'code' => 'confirm_historical_price_unit_GBP_vs_pence'];
        }
    }
    $count = (int)q('SELECT COUNT(*) FROM portfolios')->fetchColumn();
    echo json_encode(['at_utc' => gmdate('c'), 'portfolios' => $count, 'transactions' => count($rows), 'fingerprint' => $fingerprint, 'issues' => $issues], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
} finally { $db->rollBack(); }
