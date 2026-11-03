<?php
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/transactions.php';

const LOT_STRATEGIES = ['regular', 'fast', 'recovery', 'low_volatility', 'momentum', 'momentum12', 'momentum_risk', 'prudent'];   // engine/analytics/alerts.py STRATEGIES

function own_portfolio(int $id, array $user): array {
    $p = q('SELECT * FROM portfolios WHERE id = ? AND user_id = ?', [$id, $user['id']])->fetch();
    if (!$p) throw new ApiError('Portefeuille introuvable', 404);
    return $p;
}
function tx_fields(array $b): array {
    $side = str_in($b, 'side', 4);
    if (!in_array($side, ['buy', 'sell'], true)) throw new ApiError('Sens invalide (buy ou sell)');
    $qty = num_in($b, 'quantity', true, 0.00000001);
    $price = num_in($b, 'unit_price', true, 0);
    $fees = num_in($b, 'fees', false, 0, 1e11) ?? 0.0;   // colonne DECIMAL(20,8) : 12 chiffres avant la virgule
    $fx = num_in($b, 'fx_to_eur', false, 0);
    $when = str_in($b, 'trade_at', 25);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/', $when)) throw new ApiError('Date invalide', 422);
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', substr($when, 0, 10), new DateTimeZone('UTC'));
    if (!$date || $date->format('Y-m-d') !== substr($when, 0, 10)) throw new ApiError('Date invalide', 422);
    $ts = strtotime($when . (strlen($when) <= 10 ? ' 12:00:00' : '') . ' UTC');
    if ($ts === false || $ts > time() + 86400) throw new ApiError('Date invalide');
    return [$side, $qty, $price, $fees, $fx, gmdate('Y-m-d H:i:s', $ts)];
}

return [
    'portfolios' => function () {
        $u = require_user();
        $rows = q('SELECT id, name, is_default, strategy_config IS NOT NULL AS has_strategy, created_at FROM portfolios WHERE user_id = ? ORDER BY is_default DESC, name', [$u['id']])->fetchAll();
        foreach ($rows as &$r) { $r['is_default'] = (bool)$r['is_default']; $r['totals'] = portfolio_valuation((int)$r['id'])['totals']; }
        return ['portfolios' => $rows];
    },
    'portfolio' => function () {
        $u = require_user();
        $p = own_portfolio((int)($_GET['id'] ?? 0), $u);
        $v = portfolio_valuation((int)$p['id']);
        $levels = [];
        foreach (q('SELECT listing_id, stop_px, target_px FROM position_levels WHERE portfolio_id = ?', [$p['id']])->fetchAll() as $l) $levels[(int)$l['listing_id']] = ['stop' => $l['stop_px'] !== null ? (float)$l['stop_px'] : null, 'target' => $l['target_px'] !== null ? (float)$l['target_px'] : null];
        foreach ($v['positions'] as &$pos) $pos['levels'] = $pos['listing_id'] ? ($levels[$pos['listing_id']] ?? null) : null;
        unset($pos);
        $tx = q('SELECT id, listing_id, symbol, name, isin, side, quantity, unit_price, currency, fx_to_eur, fees, trade_at, note FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at DESC, id DESC', [$p['id']])->fetchAll();
        $v['etf_analysis'] = engine_call('etf-portfolio', ['positions' => array_map(function ($x) { return array_intersect_key($x, array_flip(['listing_id', 'kind', 'symbol', 'value'])); }, $v['positions'])]);
        $t = q('SELECT us_pct, eu_pct, emerging_pct FROM portfolio_targets WHERE portfolio_id = ?', [$p['id']])->fetch();
        $target = $t ? ['us' => (float)$t['us_pct'], 'eu' => (float)$t['eu_pct'], 'emerging' => (float)$t['emerging_pct']] : null;
        $lots = open_lots(q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ?', [$p['id']])->fetchAll());
        $settings = [];
        foreach (q('SELECT s.* FROM lot_settings s JOIN portfolio_transactions t ON t.id = s.transaction_id WHERE t.portfolio_id = ?', [$p['id']])->fetchAll() as $r) $settings[(int)$r['transaction_id']] = $r;
        $pfCfg = $p['strategy_config'] ? json_decode($p['strategy_config'], true) : null;
        $req = ['portfolio_strategy' => $pfCfg ? ['name' => $pfCfg['name'] ?? null, 'config' => $pfCfg] : null, 'lots' => []];
        foreach ($lots as $l) {
            $t = $l['tx']; $s = $settings[(int)$t['id']] ?? [];
            $req['lots'][] = ['tx_id' => (int)$t['id'], 'listing_id' => $t['listing_id'] ? (int)$t['listing_id'] : null, 'trade_date' => substr($t['trade_at'], 0, 10),
                'strategy' => $s['strategy'] ?? null, 'alert_days' => isset($s['alert_days']) ? (int)$s['alert_days'] : null,
                'alert_drop_pct' => isset($s['alert_drop_pct']) ? (float)$s['alert_drop_pct'] : null, 'alerts_off' => !empty($s['alerts_off'])];
        }
        $alerts = $req['lots'] ? engine_call('lot-alerts', $req) : ['lots' => [], 'strategies' => null];
        $v['lots'] = array_map(function ($l) use ($alerts, $settings) {
            $t = $l['tx']; $s = $settings[(int)$t['id']] ?? null;
            return ['tx_id' => (int)$t['id'], 'listing_id' => $t['listing_id'] ? (int)$t['listing_id'] : null, 'symbol' => $t['symbol'], 'name' => $t['name'], 'trade_at' => $t['trade_at'],
                    'quantity' => (float)$t['quantity'], 'remaining' => $l['remaining'], 'unit_price' => (float)$t['unit_price'], 'currency' => $t['currency'],
                    'settings' => $s ? ['strategy' => $s['strategy'], 'alert_days' => $s['alert_days'] !== null ? (int)$s['alert_days'] : null,
                                        'alert_drop_pct' => $s['alert_drop_pct'] !== null ? (float)$s['alert_drop_pct'] : null, 'alerts_off' => (bool)$s['alerts_off']] : null,
                    'alert' => $alerts['lots'][(string)$t['id']] ?? null];
        }, $lots);
        $v['lot_strategies'] = $alerts['strategies'] ?? null;
        $v['curves'] = $alerts['curves'] ?? (object)[];
        $v['allocation'] = engine_call('allocation', ['target' => $target, 'positions' => array_map(function ($x) { return array_intersect_key($x, array_flip(['listing_id', 'kind', 'value'])); }, $v['positions'])]);
        return $v + ['portfolio' => ['id' => (int)$p['id'], 'name' => $p['name'], 'is_default' => (bool)$p['is_default'], 'strategy' => $p['strategy_config'] ? json_decode($p['strategy_config'], true) : null], 'transactions_list' => $tx];
    },
    'portfolio/history' => function () {
        $u = require_user();
        $p = own_portfolio((int)($_GET['id'] ?? 0), $u);
        $tx = q('SELECT id, listing_id, symbol, name, side, quantity, unit_price, currency, fx_to_eur, fees, trade_at FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id', [$p['id']])->fetchAll();
        return engine_call('portfolio-history', ['transactions' => $tx]);
    },
    'position/levels' => function () {
        need_post(); $u = require_user(); $b = body();
        $p = own_portfolio((int)($b['portfolio_id'] ?? 0), $u);
        $lid = (int)($b['listing_id'] ?? 0);
        if (!q('SELECT 1 FROM portfolio_transactions WHERE portfolio_id = ? AND listing_id = ?', [$p['id'], $lid])->fetch()) throw new ApiError('Ce titre n’est pas dans ce portefeuille', 404);
        $v = [];
        foreach (['stop', 'target'] as $k) {
            $x = $b[$k] ?? null;
            if ($x === null || $x === '') { $v[$k] = null; continue; }
            if (!is_numeric($x) || $x <= 0 || $x > 1e9) throw new ApiError('Prix invalide');
            $v[$k] = (float)$x;
        }
        if ($v['stop'] !== null && $v['target'] !== null && $v['stop'] >= $v['target']) throw new ApiError('Le filet de sécurité doit être inférieur à l’objectif', 422);
        if ($v['stop'] === null && $v['target'] === null) q('DELETE FROM position_levels WHERE portfolio_id = ? AND listing_id = ?', [$p['id'], $lid]);
        else q('INSERT INTO position_levels(portfolio_id, listing_id, stop_px, target_px, updated_at) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE stop_px = VALUES(stop_px), target_px = VALUES(target_px), updated_at = VALUES(updated_at)', [$p['id'], $lid, $v['stop'], $v['target'], now_utc()]);
        return ['ok' => true];
    },
    'portfolio/target' => function () {
        need_post(); $u = require_user(); $b = body();
        $p = own_portfolio((int)($b['id'] ?? 0), $u);
        if (empty($b['target'])) { q('DELETE FROM portfolio_targets WHERE portfolio_id = ?', [$p['id']]); return ['target' => null]; }
        $t = $b['target'];
        if (!is_array($t)) throw new ApiError('Répartition invalide', 422);
        $v = [];
        foreach (['us', 'eu', 'emerging'] as $k) {
            $x = $t[$k] ?? null;
            if (!is_numeric($x) || $x < 0 || $x > 100) throw new ApiError('Chaque part doit être comprise entre 0 et 100 %', 422);
            $v[$k] = round((float)$x, 2);
        }
        if (abs(array_sum($v) - 100) > 0.01) throw new ApiError('Les trois parts doivent faire 100 %', 422);
        q('INSERT INTO portfolio_targets(portfolio_id, us_pct, eu_pct, emerging_pct, updated_at) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE us_pct = VALUES(us_pct), eu_pct = VALUES(eu_pct), emerging_pct = VALUES(emerging_pct), updated_at = VALUES(updated_at)',
          [$p['id'], $v['us'], $v['eu'], $v['emerging'], now_utc()]);
        return ['target' => $v];
    },
    'lot/settings' => function () {
        need_post(); $u = require_user(); $b = body();
        $t = q("SELECT t.id FROM portfolio_transactions t JOIN portfolios p ON p.id = t.portfolio_id WHERE t.id = ? AND p.user_id = ? AND t.side = 'buy'", [(int)($b['tx_id'] ?? 0), $u['id']])->fetch();
        if (!$t) throw new ApiError('Achat introuvable', 404);
        $strategy = $b['strategy'] ?? null;
        if ($strategy === '' ) $strategy = null;
        if ($strategy !== null && !in_array($strategy, LOT_STRATEGIES, true)) throw new ApiError('Stratégie inconnue', 422);
        $days = $b['alert_days'] ?? null; $drop = $b['alert_drop_pct'] ?? null;
        if ($days === '') $days = null; if ($drop === '') $drop = null;
        if ($days !== null && (!is_numeric($days) || (int)$days < 1 || (int)$days > 3650)) throw new ApiError('Durée invalide (1 à 3 650 jours)', 422);
        if ($drop !== null && (!is_numeric($drop) || $drop <= 0 || $drop >= 100)) throw new ApiError('Seuil de chute invalide (entre 0 et 100 %)', 422);
        $off = !empty($b['alerts_off']) ? 1 : 0;
        if ($strategy === null && $days === null && $drop === null && !$off) q('DELETE FROM lot_settings WHERE transaction_id = ?', [$t['id']]);
        else q('INSERT INTO lot_settings(transaction_id, strategy, alert_days, alert_drop_pct, alerts_off, updated_at) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE strategy = VALUES(strategy), alert_days = VALUES(alert_days), alert_drop_pct = VALUES(alert_drop_pct), alerts_off = VALUES(alerts_off), updated_at = VALUES(updated_at)',
               [$t['id'], $strategy, $days === null ? null : (int)$days, $drop === null ? null : round((float)$drop, 2), $off, now_utc()]);
        return ['ok' => true];
    },
    'portfolio/create' => function () {
        need_post(); $u = require_user();
        $name = str_in(body(), 'name', 100);
        if (q('SELECT 1 FROM portfolios WHERE user_id = ? AND name = ?', [$u['id'], $name])->fetch()) throw new ApiError('Ce nom existe déjà', 409);
        $first = !q('SELECT 1 FROM portfolios WHERE user_id = ?', [$u['id']])->fetch();
        q('INSERT INTO portfolios(user_id, name, is_default, created_at, updated_at) VALUES (?,?,?,?,?)', [$u['id'], $name, $first ? 1 : 0, now_utc(), now_utc()]);
        return ['id' => (int)db()->lastInsertId()];
    },
    'portfolio/rename' => function () {
        need_post(); $u = require_user(); $b = body();
        $p = own_portfolio((int)($b['id'] ?? 0), $u);
        $name = str_in($b, 'name', 100);
        if (q('SELECT 1 FROM portfolios WHERE user_id = ? AND name = ? AND id <> ?', [$u['id'], $name, $p['id']])->fetch()) throw new ApiError('Ce nom existe déjà', 409);
        q('UPDATE portfolios SET name = ?, updated_at = ? WHERE id = ?', [$name, now_utc(), $p['id']]);
        return ['ok' => true];
    },
    'portfolio/default' => function () {
        need_post(); $u = require_user();
        $p = own_portfolio((int)(body()['id'] ?? 0), $u);
        $db = db(); $db->beginTransaction();
        try {
            q('UPDATE portfolios SET is_default = 0 WHERE user_id = ?', [$u['id']]);
            q('UPDATE portfolios SET is_default = 1 WHERE id = ?', [$p['id']]);
            $db->commit();
        } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); throw $e; }
        return ['ok' => true];
    },
    'portfolio/delete' => function () {
        need_post(); $u = require_user();
        $b = body();
        $p = own_portfolio((int)($b['id'] ?? 0), $u);
        $n = (int)q('SELECT COUNT(*) FROM portfolio_transactions WHERE portfolio_id = ?', [$p['id']])->fetchColumn();
        if ($n > 0 && ($b['confirm'] ?? '') !== $p['name']) throw new ApiError("Ce portefeuille contient $n transactions : tapez son nom pour confirmer la suppression", 422);
        q('DELETE FROM portfolios WHERE id = ?', [$p['id']]);
        if ($p['is_default']) q('UPDATE portfolios SET is_default = 1 WHERE user_id = ? ORDER BY id LIMIT 1', [$u['id']]);
        return ['ok' => true];
    },
    'portfolio/strategy' => function () {
        need_post(); $u = require_user(); $b = body();
        $p = own_portfolio((int)($b['id'] ?? 0), $u);
        $cfg = null;
        if (!empty($b['config'])) $cfg = engine_call('validate-config', $b['config']);
        q('UPDATE portfolios SET strategy_config = ?, updated_at = ? WHERE id = ?', [$cfg ? json_encode($cfg) : null, now_utc(), $p['id']]);
        return ['config' => $cfg];
    },
    'tx/add' => function () {
        need_post(); $u = require_user(); $b = body();
        $p = own_portfolio((int)($b['portfolio_id'] ?? 0), $u);
        list($side, $qty, $price, $fees, $fx, $when) = tx_fields($b);
        $listing = null;
        if (!empty($b['listing_id'])) {
            $listing = q('SELECT l.id, l.symbol, l.currency, i.name, i.isin FROM listings l JOIN instruments i ON i.id = l.instrument_id WHERE l.id = ?', [(int)$b['listing_id']])->fetch();
            if (!$listing) throw new ApiError('Titre introuvable', 404);
        }
        $symbol = $listing ? $listing['symbol'] : strtoupper(str_in($b, 'symbol', 32));
        $currency = price_unit($b['currency'] ?? ($listing['currency'] ?? null));
        if ($listing && empty($b['currency'])) {
            $quote = q('SELECT currency FROM latest_prices WHERE listing_id = ?', [$listing['id']])->fetch();
            $currency = price_unit($quote['currency'] ?? $currency);
        }
        $fx = historical_fx($currency, $when, $fx);
        return write_transaction((int)$u['id'], (int)$p['id'], function ($rows) use ($p, $listing, $symbol, $b, $side, $qty, $price, $currency, $fx, $fees, $when) {
        q('INSERT INTO portfolio_transactions(portfolio_id, listing_id, symbol, name, isin, side, quantity, unit_price, currency, fx_to_eur, fees, trade_at, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
          [$p['id'], $listing ? $listing['id'] : null, $symbol, $listing ? $listing['name'] : (str_in($b, 'name', 120, false) ?: null), $listing ? $listing['isin'] : null, $side, $qty, $price,
           $currency, $fx, $fees, $when, str_in($b, 'note', 500, false) ?: null, now_utc()]);
        return ['id' => (int)db()->lastInsertId()];
        });
    },
    'tx/delete' => function () {
        need_post(); $u = require_user();
        $t = q('SELECT t.id, t.portfolio_id FROM portfolio_transactions t JOIN portfolios p ON p.id = t.portfolio_id WHERE t.id = ? AND p.user_id = ?', [(int)(body()['id'] ?? 0), $u['id']])->fetch();
        if (!$t) throw new ApiError('Transaction introuvable', 404);
        return write_transaction((int)$u['id'], (int)$t['portfolio_id'], function ($rows) use ($t) {
            if (!array_filter($rows, function ($r) use ($t) { return $r['id'] == $t['id']; })) throw new ApiError('Transaction introuvable', 404);
            q('DELETE FROM portfolio_transactions WHERE id = ?', [$t['id']]);
            return ['ok' => true];
        });
    },
    'tx/update' => function () {
        need_post(); $u = require_user(); $b = body();
        $t = q('SELECT t.id, t.portfolio_id FROM portfolio_transactions t JOIN portfolios p ON p.id = t.portfolio_id WHERE t.id = ? AND p.user_id = ?', [(int)($b['id'] ?? 0), $u['id']])->fetch();
        if (!$t) throw new ApiError('Transaction introuvable', 404);
        return write_transaction((int)$u['id'], (int)$t['portfolio_id'], function ($rows) use ($b, $t) {
            $found = array_values(array_filter($rows, function ($r) use ($t) { return $r['id'] == $t['id']; }));
            if (!$found) throw new ApiError('Transaction introuvable', 404);
            $old = $found[0];
            list($side, $qty, $price, $fees, $fx, $when) = tx_fields($b);
            $currency = price_unit($b['currency'] ?? $old['currency']);
            // Unchanged date/unit retains the immutable historical rate when the client leaves it blank.
            if ($fx === null && substr($when, 0, 10) === substr($old['trade_at'], 0, 10) && $currency === price_unit($old['currency']))
                $fx = $old['fx_to_eur'] === null ? null : (float)$old['fx_to_eur'];
            $fx = historical_fx($currency, $when, $fx);
            q('UPDATE portfolio_transactions SET side = ?, quantity = ?, unit_price = ?, currency = ?, fees = ?, fx_to_eur = ?, trade_at = ?, note = ? WHERE id = ?',
              [$side, $qty, $price, $currency, $fees, $fx, $when, str_in($b, 'note', 500, false) ?: null, $old['id']]);
            return ['ok' => true];
        });
    },
    'bilan' => function () {
        $u = require_user();
        $list = q('SELECT id, name, is_default FROM portfolios WHERE user_id = ? ORDER BY is_default DESC, name', [$u['id']])->fetchAll();
        $all = ['value' => 0.0, 'cost' => 0.0, 'unrealized' => 0.0, 'realized' => 0.0, 'fees' => 0.0, 'invested_total' => 0.0, 'unpriced' => 0];
        $years = []; $rows = []; $issues = []; $excluded = [];
        foreach ($list as $p) {
            $v = portfolio_valuation((int)$p['id']);
            $issues = array_merge($issues, $v['integrity']['issues']);
            $rows[] = ['id' => (int)$p['id'], 'name' => $p['name'], 'totals' => $v['totals'], 'positions' => count($v['positions'])];
            // Les résultats calculables de chaque portefeuille comptent toujours ; seules les positions incomplètes en sont exclues (et signalées).
            foreach (['value', 'fees', 'unpriced'] as $k) $all[$k] += $v['totals'][$k];
            foreach (['cost', 'unrealized', 'realized', 'invested_total'] as $k) $all[$k] += $v['totals'][$k] ?? 0.0;
            foreach ($v['realized_by_year'] as $y => $g) $years[$y] = ($years[$y] ?? 0.0) + $g;
            foreach ($v['totals']['excluded'] as $name) $excluded[] = $p['name'] . ' · ' . $name;
        }
        ksort($years);
        if ($all['unpriced']) { $all['value'] = null; $all['unrealized'] = null; }
        $all['total_gain'] = $all['unrealized'] === null ? null : $all['unrealized'] + $all['realized'];
        $all['unrealized_pct'] = $all['unrealized'] !== null && $all['cost'] > 0 ? 100 * $all['unrealized'] / $all['cost'] : null;
        $all['partial'] = (bool)$excluded;
        $all['excluded'] = $excluded;
        return ['integrity' => ['ok' => !$issues, 'issues' => $issues], 'portfolios' => $rows, 'totals' => $all, 'realized_by_year' => $years];
    },
    'export' => function () {
        $u = require_user();
        $p = own_portfolio((int)($_GET['id'] ?? 0), $u);
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="transactions-' . preg_replace('/[^A-Za-z0-9_-]+/', '_', $p['name']) . '.csv"');
        $f = fopen('php://output', 'w');
        // Un texte qui commence par = + - @ (ou tabulation / retour) serait interprété comme une formule par un tableur : on le préfixe d'une apostrophe.
        $cell = function ($v) { return is_string($v) && $v !== '' && strpbrk($v[0], "=+-@\t\r") !== false ? "'" . $v : $v; };
        fputcsv($f, ['date', 'sens', 'symbole', 'nom', 'isin', 'quantite', 'prix_unitaire', 'devise', 'change_eur', 'frais', 'note'], ',', '"', '');
        foreach (q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id', [$p['id']])->fetchAll() as $t)
            fputcsv($f, [$t['trade_at'], $t['side'], $cell($t['symbol']), $cell($t['name']), $cell($t['isin']), $t['quantity'], $t['unit_price'], $t['currency'], $t['fx_to_eur'], $t['fees'], $cell($t['note'])], ',', '"', '');
        exit;
    },
];
