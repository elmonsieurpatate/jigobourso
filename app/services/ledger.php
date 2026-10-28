<?php
require_once __DIR__ . '/../lib/db.php';

// Valorisation d'un portefeuille à partir du registre de transactions (méthode du prix de revient moyen pondéré, en euros).
// Achat : le coût (prix × quantité × change + frais) s'ajoute au stock. Vente : le coût moyen de la quantité vendue sort du stock,
// la plus-value réalisée = produit net (prix × quantité × change − frais) − coût sorti.

function fx_rates(): array {
    $rows = q('SELECT f.currency, f.to_eur FROM fx_rates f JOIN (SELECT currency, MAX(rate_date) d FROM fx_rates GROUP BY currency) m ON m.currency = f.currency AND m.d = f.rate_date')->fetchAll();
    $out = ['EUR' => 1.0];
    foreach ($rows as $r) $out[strtoupper($r['currency'])] = (float)$r['to_eur'];
    return $out;
}
function eur_factor(?string $currency, array $rates): ?float {
    if (!$currency) return null;
    if ($currency === 'GBp') return isset($rates['GBP']) ? $rates['GBP'] / 100 : null;
    return $rates[strtoupper($currency)] ?? null;
}

function portfolio_valuation(int $portfolioId): array {
    $rates = fx_rates();
    $tx = q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id', [$portfolioId])->fetchAll();
    $pos = [];
    $realizedTotal = 0.0; $feesTotal = 0.0; $investedTotal = 0.0; $proceedsTotal = 0.0;
    $byYear = [];
    foreach ($tx as $t) {
        $key = $t['listing_id'] ? 'L' . $t['listing_id'] : 'S' . strtoupper($t['symbol']);
        if (!isset($pos[$key])) $pos[$key] = ['key' => $key, 'listing_id' => $t['listing_id'] ? (int)$t['listing_id'] : null, 'symbol' => $t['symbol'], 'name' => $t['name'],
                                                 'isin' => $t['isin'], 'currency' => $t['currency'], 'qty' => 0.0, 'cost' => 0.0, 'realized' => 0.0, 'first_buy' => null, 'last_trade' => null, 'fees' => 0.0];
        $p = &$pos[$key];
        $fx = $t['fx_to_eur'] !== null ? (float)$t['fx_to_eur'] : (eur_factor($t['currency'], $rates) ?? 1.0);
        $qty = (float)$t['quantity']; $gross = $qty * (float)$t['unit_price'] * $fx; $fees = (float)($t['fees'] ?? 0);
        $feesTotal += $fees; $p['fees'] += $fees; $p['last_trade'] = $t['trade_at'];
        if ($t['side'] === 'buy') {
            $p['qty'] += $qty; $p['cost'] += $gross + $fees; $investedTotal += $gross + $fees;
            if (!$p['first_buy']) $p['first_buy'] = $t['trade_at'];
        } else {
            $sold = min($qty, $p['qty']);
            $avg = $p['qty'] > 0 ? $p['cost'] / $p['qty'] : 0.0;
            $out = $avg * $sold; $net = $gross - $fees;
            $gain = $net - $out;
            $p['qty'] -= $sold; $p['cost'] -= $out; $p['realized'] += $gain; $realizedTotal += $gain; $proceedsTotal += $net;
            $year = substr($t['trade_at'], 0, 4);
            $byYear[$year] = ($byYear[$year] ?? 0.0) + $gain;
            if ($p['qty'] < 1e-9) { $p['qty'] = 0.0; $p['cost'] = 0.0; }
        }
        unset($p);
    }
    $ids = array_values(array_filter(array_map(function ($p) { return $p['listing_id']; }, $pos)));
    $info = [];
    if ($ids) {
        $in = implode(',', array_fill(0, count($ids), '?'));
        foreach (q("SELECT l.id, l.symbol, l.mic, l.status, l.excluded_reason, l.is_primary, i.name, i.kind, p.price, p.price_time, p.source, p.currency AS price_currency, l.currency
                    FROM listings l JOIN instruments i ON i.id = l.instrument_id LEFT JOIN latest_prices p ON p.listing_id = l.id WHERE l.id IN ($in)", $ids)->fetchAll() as $r) $info[(int)$r['id']] = $r;
    }
    $open = []; $closed = []; $value = 0.0; $costOpen = 0.0;
    foreach ($pos as $p) {
        $i = $p['listing_id'] ? ($info[$p['listing_id']] ?? null) : null;
        $row = $p + ['name_catalogue' => $i['name'] ?? null, 'kind' => $i['kind'] ?? null, 'mic' => $i['mic'] ?? null, 'catalogue_status' => $i['status'] ?? null,
                     'excluded_reason' => $i['excluded_reason'] ?? null, 'price' => null, 'price_eur' => null, 'price_time' => null, 'price_source' => null,
                     'value' => null, 'unrealized' => null, 'unrealized_pct' => null, 'avg_cost' => null, 'linked' => $i !== null, 'price_currency' => $i ? ($i['price_currency'] ?: $i['currency']) : null];
        if ($row['qty'] > 0) {
            $row['avg_cost'] = $row['cost'] / $row['qty'];
            if ($i && $i['price'] !== null) {
                $f = eur_factor($i['price_currency'] ?: $i['currency'], $rates);
                if ($f !== null) {
                    $row['price'] = (float)$i['price']; $row['price_eur'] = $row['price'] * $f; $row['price_time'] = $i['price_time']; $row['price_source'] = $i['source'];
                    $row['value'] = $row['qty'] * $row['price_eur']; $row['unrealized'] = $row['value'] - $row['cost'];
                    $row['unrealized_pct'] = $row['cost'] > 0 ? 100 * $row['unrealized'] / $row['cost'] : null;
                    $value += $row['value']; $costOpen += $row['cost'];
                }
            }
            $open[] = $row;
        } else {
            $closed[] = $row;
        }
    }
    foreach ($open as &$o) $o['weight'] = ($value > 0 && $o['value'] !== null) ? 100 * $o['value'] / $value : null;
    unset($o);
    usort($open, function ($a, $b) { return ($b['value'] ?? -1) <=> ($a['value'] ?? -1); });
    $unrealized = $value - $costOpen;
    return ['positions' => $open, 'closed' => $closed,
            'totals' => ['value' => $value, 'cost' => $costOpen, 'unrealized' => $unrealized, 'unrealized_pct' => $costOpen > 0 ? 100 * $unrealized / $costOpen : null,
                         'realized' => $realizedTotal, 'fees' => $feesTotal, 'invested_total' => $investedTotal, 'proceeds_total' => $proceedsTotal,
                         'total_gain' => $unrealized + $realizedTotal, 'unpriced' => count(array_filter($open, function ($o) { return $o['value'] === null; }))],
            'realized_by_year' => $byYear, 'transactions' => count($tx)];
}
