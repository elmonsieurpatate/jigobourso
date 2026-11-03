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
    $events = split_events(array_map(function ($t) { return $t['listing_id'] ?? null; }, $rows));      // les quantités suivent les splits confirmés, comme la valorisation
    $freeBuys = free_buy_dates($rows);
    $held = []; $cursor = [];
    foreach ($rows as $t) {
        $k = transaction_key($t); $qty = (float)$t['quantity'];
        $have = $held[$k] ?? 0.0;
        $lid = !empty($t['listing_id']) ? (int)$t['listing_id'] : 0;
        if ($lid && isset($events[$lid])) {
            $c = $cursor[$k] ?? '';
            $have *= pending_split_ratio($events[$lid], $freeBuys[$lid] ?? [], $c, substr($t['trade_at'], 0, 10));
            $cursor[$k] = $c;
        }
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
// Achats encore (au moins en partie) détenus : les ventes consomment les achats les plus anciens d'abord (FIFO), quantités suivies à travers les splits
// confirmés comme dans validate_transaction_history. Renvoie [{tx (ligne d'achat), remaining}] dans l'ordre chronologique. Sert aux alertes, pas au prix de revient.
function open_lots(array $rows): array {
    usort($rows, function ($a, $b) { return [$a['trade_at'], (int)$a['id']] <=> [$b['trade_at'], (int)$b['id']]; });
    $events = split_events(array_map(function ($t) { return $t['listing_id'] ?? null; }, $rows));
    $freeBuys = free_buy_dates($rows);
    $lots = []; $cursor = [];
    foreach ($rows as $t) {
        $k = transaction_key($t); $qty = (float)$t['quantity'];
        $lid = !empty($t['listing_id']) ? (int)$t['listing_id'] : 0;
        if ($lid && isset($events[$lid]) && !empty($lots[$k])) {
            $c = $cursor[$k] ?? '';
            $f = pending_split_ratio($events[$lid], $freeBuys[$lid] ?? [], $c, substr($t['trade_at'], 0, 10));
            $cursor[$k] = $c;
            foreach ($lots[$k] as &$l) $l['remaining'] *= $f;
            unset($l);
        } elseif ($lid) $cursor[$k] = max($cursor[$k] ?? '', substr($t['trade_at'], 0, 10));
        if ($t['side'] === 'buy') { $lots[$k][] = ['tx' => $t, 'remaining' => $qty]; continue; }
        if (empty($lots[$k])) continue;                  // vente sans achat connu : refusée ailleurs par validate_transaction_history
        foreach ($lots[$k] as &$l) {
            if ($qty <= 1e-12) break;
            $take = min($l['remaining'], $qty); $l['remaining'] -= $take; $qty -= $take;
        }
        unset($l);
    }
    $out = [];
    // Même frontière que la valorisation : appliquer aussi les événements sans opération ultérieure.
    $today = gmdate('Y-m-d');
    foreach ($lots as $key => $list) {
        $lid = (int)($list[0]['tx']['listing_id'] ?? 0);
        $c = $cursor[$key] ?? '';
        $factor = $lid && isset($events[$lid]) ? pending_split_ratio($events[$lid], $freeBuys[$lid] ?? [], $c, $today) : 1.0;
        foreach ($list as $l) {
            $l['remaining'] *= $factor;
            if ($l['remaining'] > 1e-9) $out[] = $l;
        }
    }
    usort($out, function ($a, $b) { return [$a['tx']['trade_at'], (int)$a['tx']['id']] <=> [$b['tx']['trade_at'], (int)$b['tx']['id']]; });
    return $out;
}
