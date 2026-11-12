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
    if ($currency === 'GBp' || strtoupper($currency) === 'GBX') return isset($rates['GBP']) ? $rates['GBP'] / 100 : null;
    if ($currency === 'ZAc' || strtoupper($currency) === 'ZAC') return isset($rates['ZAR']) ? $rates['ZAR'] / 100 : null;        // cents du rand (Johannesburg)
    if (strtoupper($currency) === 'ILA') return isset($rates['ILS']) ? $rates['ILS'] / 100 : null;                              // agorot (Tel-Aviv)
    return $rates[strtoupper($currency)] ?? null;
}

// Splits et regroupements confirmés par le fournisseur (market/splits.py : l'historique de cours a été ajusté par Yahoo) : le registre en tient compte
// tout seul, la quantité détenue est multipliée par le ratio (parts nouvelles / anciennes) à la date de l'événement, le coût total ne change pas.
// Un utilisateur qui avait déjà corrigé à la main (achat à prix 0 à partir de la date de l'événement) n'est pas corrigé deux fois.
function split_events(array $listingIds): array {
    $ids = array_values(array_unique(array_filter(array_map('intval', $listingIds))));
    if (!$ids) return [];
    try {
        $in = implode(',', array_fill(0, count($ids), '?'));
        $out = [];
        foreach (q("SELECT listing_id, event_date, ratio FROM split_log WHERE status = 'confirmed' AND listing_id IN ($in) ORDER BY event_date", $ids)->fetchAll() as $s)
            $out[(int)$s['listing_id']][] = ['date' => (string)$s['event_date'], 'ratio' => (float)$s['ratio']];
        return $out;
    } catch (Throwable $e) {
        return [];                                     // table absente tant que la migration n'est pas passée
    }
}
function free_buy_dates(array $rows): array {
    $out = [];
    foreach ($rows as $t) if ($t['listing_id'] && $t['side'] === 'buy' && (float)$t['unit_price'] == 0.0) $out[(int)$t['listing_id']][] = substr($t['trade_at'], 0, 10);
    return $out;
}
// Produit des ratios des événements dans ]$cursor, $upTo] non déjà corrigés à la main ; fait avancer $cursor.
function pending_split_ratio(array $events, array $freeDates, string &$cursor, string $upTo): float {
    $f = 1.0;
    foreach ($events as $e) {
        if ($e['date'] > $cursor && $e['date'] <= $upTo) {
            $handled = false;
            foreach ($freeDates as $d) if ($d >= $e['date']) $handled = true;
            if (!$handled) $f *= $e['ratio'];
        }
    }
    if ($upTo > $cursor) $cursor = $upTo;
    return $f;
}

function portfolio_valuation(int $portfolioId, ?array $transactions = null, ?string $asOf = null): array {
    $rates = fx_rates();
    $tx = $transactions ?? q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id', [$portfolioId])->fetchAll();
    usort($tx, fn($a, $b) => [$a['trade_at'], (int)$a['id']] <=> [$b['trade_at'], (int)$b['id']]);
    $events = split_events(array_map(function ($t) { return $t['listing_id']; }, $tx));
    $freeBuys = free_buy_dates($tx);
    $pos = [];
    $feesTotal = 0.0; $periods = []; $active = [];
    $issues = []; $uncertain = []; $sales = [];
    foreach ($tx as $t) {
        $key = $t['listing_id'] ? 'L' . $t['listing_id'] : 'S' . strtoupper($t['symbol']);
        if (!isset($pos[$key])) $pos[$key] = ['key' => $key, 'listing_id' => $t['listing_id'] ? (int)$t['listing_id'] : null, 'symbol' => $t['symbol'], 'name' => $t['name'],
                                                 'isin' => $t['isin'], 'currency' => $t['currency'], 'qty' => 0.0, 'cost' => 0.0, 'realized' => 0.0, 'first_buy' => null, 'last_trade' => null, 'fees' => 0.0,
                                                 'invested' => 0.0, 'proceeds' => 0.0, 'by_year' => [], 'cursor' => '', 'splits_applied' => []];
        $p = &$pos[$key];
        $day = substr($t['trade_at'], 0, 10);
        if ($p['listing_id'] && isset($events[$p['listing_id']])) {
            $r = pending_split_ratio($events[$p['listing_id']], $freeBuys[$p['listing_id']] ?? [], $p['cursor'], $day);
            if ($r != 1.0 && $p['qty'] > 0) { $p['qty'] *= $r; $p['splits_applied'][] = ['until' => $day, 'ratio' => $r]; }
        }
        $fx = $t['fx_to_eur'] !== null ? (float)$t['fx_to_eur'] : (strtoupper($t['currency'] ?? '') === 'EUR' ? 1.0 : null);
        if ($fx === null || $fx <= 0) {
            $issues[] = ['transaction_id' => (int)$t['id'], 'code' => 'historical_fx_missing', 'message' => 'Taux historique non enregistré : prix de revient et plus-value de ce titre non calculables. Corrigez explicitement cette transaction.'];
            $uncertain[$key] = true; $fx = 0.0; // placeholder interne : toutes les sorties monétaires de CE titre sont supprimées plus bas
        }
        $qty = (float)$t['quantity']; $gross = $qty * (float)$t['unit_price'] * $fx; $fees = (float)($t['fees'] ?? 0);
        $feesTotal += $fees; $p['fees'] += $fees; $p['last_trade'] = $t['trade_at'];
        if ($t['side'] === 'buy') {
            if ($p['qty'] <= 1e-9) $active[$key] = ['start' => $t['trade_at'], 'end' => null, 'invested' => 0.0, 'proceeds' => 0.0, 'fees' => 0.0, 'realized' => 0.0];
            $active[$key]['invested'] += $gross + $fees;
            $p['qty'] += $qty; $p['cost'] += $gross + $fees; $p['invested'] += $gross + $fees;
            if (!$p['first_buy']) $p['first_buy'] = $t['trade_at'];
        } else {
            if ($qty > $p['qty'] + 1e-9) {
                $issues[] = ['transaction_id' => (int)$t['id'], 'code' => 'oversold', 'message' => 'Vente sans quantité suffisante à sa date : registre à corriger explicitement.'];
                $uncertain[$key] = true;
            }
            $sold = min($qty, $p['qty']);
            $avg = $p['qty'] > 0 ? $p['cost'] / $p['qty'] : 0.0;
            $out = $avg * $sold; $net = $gross - $fees;
            $gain = $net - $out;
            $p['qty'] -= $sold; $p['cost'] -= $out; $p['realized'] += $gain; $p['proceeds'] += $net;
            if (isset($active[$key])) { $active[$key]['proceeds'] += $net; $active[$key]['realized'] += $gain; }
            $year = substr($t['trade_at'], 0, 4);
            $p['by_year'][$year] = ($p['by_year'][$year] ?? 0.0) + $gain;
            $sales[] = ['tx_id' => (int)$t['id'], 'key' => $key, 'listing_id' => $p['listing_id'], 'symbol' => $p['symbol'], 'name' => $p['name'], 'trade_at' => $t['trade_at'],
                        'quantity' => $sold, 'proceeds' => $net, 'cost' => $out, 'gain' => $gain, 'gain_pct' => $out > 0 ? 100 * $gain / $out : null];   // historique des ventes (prix de revient moyen)
            if ($p['qty'] < 1e-9) { $p['qty'] = 0.0; $p['cost'] = 0.0; }
        }
        if (isset($active[$key])) {
            $active[$key]['fees'] += $fees;
            if ($p['qty'] <= 1e-9) { $active[$key]['end'] = $t['trade_at']; $periods[$key][] = $active[$key]; unset($active[$key]); }
        }
        unset($p);
    }
    // Événements postérieurs à la dernière opération (jusqu'à aujourd'hui) sur les positions encore ouvertes.
    $today = $asOf ?? gmdate('Y-m-d');
    foreach ($pos as $key => &$p) {
        if ($p['listing_id'] && isset($events[$p['listing_id']]) && $p['qty'] > 0) {
            $r = pending_split_ratio($events[$p['listing_id']], $freeBuys[$p['listing_id']] ?? [], $p['cursor'], $today);
            if ($r != 1.0) { $p['qty'] *= $r; $p['splits_applied'][] = ['until' => $today, 'ratio' => $r]; }
        }
    }
    unset($p);
    $ids = array_values(array_filter(array_map(function ($p) { return $p['listing_id']; }, $pos)));
    $info = [];
    if ($ids) {
        $in = implode(',', array_fill(0, count($ids), '?'));
        // Même observation finale que l'historique : la plus récente entre quote et clôture.
        $useQuote = "p.price IS NOT NULL AND (d.price_date IS NULL OR DATE(p.price_time) >= d.price_date)";
        foreach (q("SELECT l.id, l.symbol, l.mic, l.status, l.excluded_reason, l.is_primary, i.name, i.kind,
                    CASE WHEN $useQuote THEN p.price ELSE d.close_px END AS price,
                    CASE WHEN $useQuote THEN p.price_time ELSE CAST(d.price_date AS DATETIME) END AS price_time,
                    CASE WHEN $useQuote THEN p.source ELSE 'daily' END AS source, p.currency AS price_currency, l.currency
                    FROM listings l JOIN instruments i ON i.id = l.instrument_id
                    LEFT JOIN latest_prices p ON p.listing_id = l.id
                    LEFT JOIN daily_prices d ON d.listing_id = l.id AND d.price_date =
                        (SELECT MAX(last_d.price_date) FROM daily_prices last_d WHERE last_d.listing_id = l.id)
                    WHERE l.id IN ($in)", $ids)->fetchAll() as $r) $info[(int)$r['id']] = $r;
    }
    // Les totaux ne portent que sur les positions calculables : une transaction incomplète n'efface pas les résultats des autres titres ni des autres portefeuilles.
    $open = []; $closed = []; $value = 0.0; $valueCertain = 0.0; $costCertain = 0.0;
    $investedTotal = 0.0; $proceedsTotal = 0.0; $realizedTotal = 0.0; $byYear = []; $excluded = [];
    foreach ($pos as $p) {
        $isUncertain = isset($uncertain[$p['key']]);
        if (!$isUncertain) {
            $investedTotal += $p['invested']; $proceedsTotal += $p['proceeds']; $realizedTotal += $p['realized'];
            foreach ($p['by_year'] as $y => $g) $byYear[$y] = ($byYear[$y] ?? 0.0) + $g;
        } else {
            $excluded[] = $p['name'] ?: $p['symbol'];
        }
        $i = $p['listing_id'] ? ($info[$p['listing_id']] ?? null) : null;
        $row = $p + ['name_catalogue' => $i['name'] ?? null, 'kind' => $i['kind'] ?? null, 'mic' => $i['mic'] ?? null, 'catalogue_status' => $i['status'] ?? null,
                     'excluded_reason' => $i['excluded_reason'] ?? null, 'price' => null, 'price_eur' => null, 'price_time' => null, 'price_source' => null,
                     'value' => null, 'unrealized' => null, 'unrealized_pct' => null, 'avg_cost' => null, 'linked' => $i !== null, 'price_currency' => $i ? ($i['price_currency'] ?: $i['currency']) : null];
        $row['holding_periods'] = array_merge($periods[$p['key']] ?? [], isset($active[$p['key']]) ? [$active[$p['key']]] : []);
        if ($isUncertain) $row['holding_periods'] = [];
        unset($row['cursor'], $row['by_year'], $row['invested'], $row['proceeds']);
        if ($isUncertain) { $row['cost'] = null; $row['realized'] = null; $row['financial_incomplete'] = true; }
        if ($row['qty'] > 0) {
            $row['avg_cost'] = $row['cost'] === null ? null : $row['cost'] / $row['qty'];
            if (!$isUncertain) $costCertain += $row['cost'];
            if ($i && $i['price'] !== null) {
                $f = eur_factor($i['price_currency'] ?: $i['currency'], $rates);
                if ($f !== null) {
                    $row['price'] = (float)$i['price']; $row['price_eur'] = $row['price'] * $f; $row['price_time'] = $i['price_time']; $row['price_source'] = $i['source'];
                    $row['value'] = $row['qty'] * $row['price_eur']; $row['unrealized'] = $row['cost'] === null ? null : $row['value'] - $row['cost'];
                    $row['unrealized_pct'] = $row['cost'] > 0 ? 100 * $row['unrealized'] / $row['cost'] : null;
                    $value += $row['value'];
                    if (!$isUncertain) { $valueCertain += $row['value']; }
                }
            }
            $open[] = $row;
        } else {
            $closed[] = $row;
        }
    }
    $unpriced = count(array_filter($open, function ($o) { return $o['value'] === null; }));
    foreach ($open as &$o) $o['weight'] = (!$unpriced && $value > 0 && $o['value'] !== null) ? 100 * $o['value'] / $value : null;
    unset($o);
    usort($open, function ($a, $b) { return ($b['value'] ?? -1) <=> ($a['value'] ?? -1); });
    $computable = !$uncertain || count($pos) > count($uncertain);          // rien de calculable seulement si TOUS les titres sont incomplets
    $unrealized = $valueCertain - $costCertain;
    return ['integrity' => ['ok' => !$issues, 'issues' => $issues], 'positions' => $open, 'closed' => $closed,
            'totals' => ['value' => $unpriced ? null : $value, 'cost' => $computable ? $costCertain : null, 'unrealized' => $computable && !$unpriced ? $unrealized : null, 'unrealized_pct' => $computable && !$unpriced && $costCertain > 0 ? 100 * $unrealized / $costCertain : null,
                         'realized' => $computable ? $realizedTotal : null, 'fees' => $feesTotal, 'invested_total' => $computable ? $investedTotal : null, 'proceeds_total' => $computable ? $proceedsTotal : null,
                         'total_gain' => $computable && !$unpriced ? $unrealized + $realizedTotal : null, 'unpriced' => $unpriced,
                         'partial' => (bool)$uncertain, 'excluded' => $excluded],
            'realized_by_year' => $computable ? $byYear : [], 'transactions' => count($tx),
            'sales' => array_values(array_filter(array_reverse($sales), function ($s) use ($uncertain) { return !isset($uncertain[$s['key']]); }))];
}

function held_listing_ids(int $userId): array {
    // Quantité nette > 0, splits confirmés compris (même règle que la valorisation des portefeuilles).
    $rows = q("SELECT t.listing_id, t.side, t.quantity, t.unit_price, t.trade_at, t.id FROM portfolio_transactions t JOIN portfolios p ON p.id = t.portfolio_id
               WHERE p.user_id = ? AND t.listing_id IS NOT NULL ORDER BY t.trade_at, t.id", [$userId])->fetchAll();
    $events = split_events(array_map(function ($t) { return $t['listing_id']; }, $rows));
    $freeBuys = free_buy_dates($rows);
    $qty = []; $cursor = [];
    foreach ($rows as $t) {
        $lid = (int)$t['listing_id'];
        $c = $cursor[$lid] ?? '';
        $qty[$lid] = ($qty[$lid] ?? 0.0) * (isset($events[$lid]) ? pending_split_ratio($events[$lid], $freeBuys[$lid] ?? [], $c, substr($t['trade_at'], 0, 10)) : 1.0);
        $cursor[$lid] = $c;
        $qty[$lid] += $t['side'] === 'buy' ? (float)$t['quantity'] : -(float)$t['quantity'];
    }
    $today = gmdate('Y-m-d');
    foreach ($qty as $lid => $q) if ($q > 0 && isset($events[$lid])) { $c = $cursor[$lid]; $qty[$lid] = $q * pending_split_ratio($events[$lid], $freeBuys[$lid] ?? [], $c, $today); }
    return array_values(array_map('intval', array_keys(array_filter($qty, function ($q) { return $q > 0.000000001; }))));
}
