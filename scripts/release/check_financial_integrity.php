<?php
// CLI only, SELECT only. Reports issues without changing or disclosing transaction amounts.
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/../../app/lib/db.php';
require __DIR__ . '/../../app/services/ledger.php';
require __DIR__ . '/../../app/services/transactions.php';
$db = db();
$db->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
$db->exec('START TRANSACTION READ ONLY');
try {
    $rows = q('SELECT * FROM portfolio_transactions ORDER BY portfolio_id, trade_at, id')->fetchAll();
    $issues = []; $fingerprint = hash('sha256', json_encode($rows));
    // Quantités : même règle que la validation des écritures (splits confirmés compris), portefeuille par portefeuille.
    $byPortfolio = [];
    foreach ($rows as $t) $byPortfolio[$t['portfolio_id']][] = $t;
    foreach ($byPortfolio as $list) foreach (oversold_transactions($list) as $t) $issues[] = ['id' => (int)$t['id'], 'code' => 'oversold_at_trade_date'];
    // Recensement (lecture seule, aucune réparation) : achats à prix zéro = corrections manuelles de split ou dons à confirmer par l'utilisateur.
    foreach ($rows as $t) if ($t['side'] === 'buy' && $t['listing_id'] && (float)$t['unit_price'] == 0.0) $issues[] = ['id' => (int)$t['id'], 'code' => 'zero_price_buy_manual_split_or_gift'];
    // Parité PHP/Python : le registre lit split_log (confirmed), le moteur lit corporate_events ; un split confirmé sans événement correspondant ferait diverger les deux.
    foreach (q("SELECT s.listing_id, s.event_date FROM split_log s LEFT JOIN corporate_events e ON e.listing_id = s.listing_id AND e.event_date = s.event_date AND e.kind IN ('split','reverse_split') WHERE s.status = 'confirmed' AND e.listing_id IS NULL")->fetchAll() as $g)
        $issues[] = ['listing_id' => (int)$g['listing_id'], 'event_date' => $g['event_date'], 'code' => 'confirmed_split_without_corporate_event'];
    foreach ($rows as $t) {
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
