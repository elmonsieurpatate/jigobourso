<?php
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/ledger.php';

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

return [
    'strategy/presets' => function () { require_user(); return engine_call('presets', []); },
    'strategy/validate' => function () { need_post(); require_user(); return ['config' => engine_call('validate-config', body())]; },
    'explore' => function () {
        need_post();
        $u = require_user();
        $b = body();
        $config = $b['config'] ?? null;
        if (!empty($b['portfolio_id']) && $config === null) {
            $p = q('SELECT strategy_config FROM portfolios WHERE id = ? AND user_id = ?', [(int)$b['portfolio_id'], $u['id']])->fetch();
            if ($p && $p['strategy_config']) $config = json_decode($p['strategy_config'], true);
        }
        $held = held_listing_ids((int)$u['id']);
        $view = is_array($b['view'] ?? null) ? $b['view'] : [];
        $view['owned_ids'] = $held;
        $res = engine_call('explore', ['config' => $config ?: ($b['preset'] ?? 'regular'), 'view' => $view]);
        foreach ($res['rows'] as &$r) $r['held'] = in_array($r['id'], $held, true);
        return $res;
    },
    'data/overview' => function () { require_user(); return engine_call('overview', []); },
    'suivi' => function () { require_user(); return engine_call('suivi', []); },
    'intraday' => function () {
        require_user();
        return engine_call('intraday', ['listing_id' => (int)($_GET['id'] ?? 0), 'fetch' => ($_GET['fetch'] ?? '1') !== '0']);
    },
    'sheet' => function () {
        $u = require_user();
        $b = $_SERVER['REQUEST_METHOD'] === 'POST' ? body() : [];
        $id = (int)($b['id'] ?? $_GET['id'] ?? 0);
        $cfg = is_array($b['config'] ?? null) ? $b['config'] : null;      // configuration de l'Explorer (ou d'un préréglage) transmise telle quelle
        $source = (string)($b['source'] ?? '');
        $pf = (int)($b['portfolio'] ?? $_GET['portfolio'] ?? 0);
        if ($cfg === null && $pf) {
            $p = q('SELECT name, strategy_config FROM portfolios WHERE id = ? AND user_id = ?', [$pf, $u['id']])->fetch();
            if ($p && $p['strategy_config']) { $cfg = json_decode($p['strategy_config'], true); $source = 'Portefeuille « ' . $p['name'] . ' »'; }
        }
        $view = is_array($b['view'] ?? null) ? $b['view'] : [];
        $view['owned_ids'] = held_listing_ids((int)$u['id']);
        $sheet = engine_call('sheet', ['listing_id' => $id, 'config' => $cfg ?: 'regular', 'view' => $view, 'source' => $cfg ? $source : 'Croissance régulière (réglage par défaut)', 'fetch_profile' => true]);
        $sheet['holdings'] = [];
        foreach (q('SELECT p.id, p.name FROM portfolios p WHERE p.user_id = ? ORDER BY p.is_default DESC, p.name', [$u['id']])->fetchAll() as $p) {
            $v = portfolio_valuation((int)$p['id']);
            foreach ($v['positions'] as $pos) if ($pos['listing_id'] === $id) $sheet['holdings'][] = ['portfolio_id' => (int)$p['id'], 'portfolio' => $p['name'], 'qty' => $pos['qty'], 'avg_cost' => $pos['avg_cost'], 'value' => $pos['value'], 'unrealized' => $pos['unrealized'], 'unrealized_pct' => $pos['unrealized_pct']];
        }
        return $sheet;
    },
    'searches' => function () {
        $u = require_user();
        $rows = q('SELECT id, name, config, view, updated_at FROM saved_searches WHERE user_id = ? ORDER BY name', [$u['id']])->fetchAll();
        foreach ($rows as &$r) { $r['config'] = json_decode($r['config'], true); $r['view'] = json_decode($r['view'], true) ?: new stdClass(); }
        return ['searches' => $rows];
    },
    'search/save' => function () {
        need_post(); $u = require_user(); $b = body();
        $name = str_in($b, 'name', 80);
        $config = engine_call('validate-config', is_array($b['config'] ?? null) ? $b['config'] : []);
        $view = [];
        foreach (['kind', 'market', 'country', 'category', 'budget', 'min_price', 'max_price', 'min_score', 'max_volatility', 'max_drawdown', 'min_volume', 'pea', 'owned_only', 'open_now', 'fresh_only', 'sort', 'dir'] as $k)
            if (isset($b['view'][$k]) && is_scalar($b['view'][$k]) && $b['view'][$k] !== '' && $b['view'][$k] !== false) $view[$k] = $b['view'][$k];
        if (!q('SELECT 1 FROM saved_searches WHERE user_id = ? AND name = ?', [$u['id'], $name])->fetch() && (int)q('SELECT COUNT(*) FROM saved_searches WHERE user_id = ?', [$u['id']])->fetchColumn() >= 50) throw new ApiError('50 recherches enregistrées au maximum', 422);
        q('INSERT INTO saved_searches(user_id, name, config, view, created_at, updated_at) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE config = VALUES(config), view = VALUES(view), updated_at = VALUES(updated_at)',
          [$u['id'], $name, json_encode($config), json_encode($view ?: new stdClass()), now_utc(), now_utc()]);
        return ['ok' => true];
    },
    'search/delete' => function () {
        need_post(); $u = require_user();
        q('DELETE FROM saved_searches WHERE id = ? AND user_id = ?', [(int)(body()['id'] ?? 0), $u['id']]);
        return ['ok' => true];
    },
    'listings/search' => function () {
        require_user();
        $term = mb_strtolower(trim((string)($_GET['q'] ?? '')));
        if (mb_strlen($term) < 2) return ['results' => []];
        $like = '%' . str_replace(['%', '_'], '', $term) . '%';
        $rows = q("SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, i.name, i.isin, i.kind, p.price, p.currency AS price_currency
                   FROM listings l JOIN instruments i ON i.id = l.instrument_id LEFT JOIN latest_prices p ON p.listing_id = l.id
                   WHERE LOWER(l.symbol) LIKE ? OR LOWER(i.name) LIKE ? OR LOWER(i.isin) LIKE ?
                   ORDER BY (LOWER(l.symbol) = ?) DESC, l.is_primary DESC, l.status = 'excluded', i.name LIMIT 20", [$like, $like, $like, $term])->fetchAll();
        return ['results' => $rows];
    },
];
