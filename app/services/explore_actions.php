<?php
// Cas d’usage explore : entrées explicites, autorisations métier conservées.
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/ledger.php';
require_once __DIR__ . '/explorer_library.php';
require_once __DIR__ . '/ct_strategies.php';

function explorer_delete_saved(array $u, array $b): array {
    q('DELETE FROM explorer_saved WHERE id=? AND user_id=?',[(int)($b['id']??0),$u['id']]);return ['ok'=>true];
}

function explorer_run(array $u, array $b): array {
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
}

function explorer_intraday_bars(array $query): array {
    $id = (int)($query['id'] ?? 0);
    $rows = q('SELECT slot_start, close_px FROM intraday_prices WHERE listing_id = ? AND slot_start >= (SELECT DATE_SUB(DATE(MAX(slot_start)), INTERVAL 7 DAY) FROM intraday_prices WHERE listing_id = ?) ORDER BY slot_start',
        [$id, $id])->fetchAll();
    return ['bars' => array_map(function ($r) { return [str_replace(' ', 'T', $r['slot_start']), (float)$r['close_px']]; }, $rows)];
}

function explorer_sheet(array $u, array $b, array $query): array {
    $id = (int)($b['id'] ?? $query['id'] ?? 0);
    $cfg = is_array($b['config'] ?? null) ? $b['config'] : null;      // configuration de l'Explorer (ou d'un préréglage) transmise telle quelle
    $source = (string)($b['source'] ?? '');
    $pf = (int)($b['portfolio'] ?? $query['portfolio'] ?? 0);
    if ($cfg === null && $pf) {
        $p = q('SELECT name, strategy_config FROM portfolios WHERE id = ? AND user_id = ?', [$pf, $u['id']])->fetch();
        if ($p && $p['strategy_config']) { $cfg = json_decode($p['strategy_config'], true); $source = 'Portefeuille « ' . $p['name'] . ' »'; }
    }
    $view = is_array($b['view'] ?? null) ? $b['view'] : [];
    $view['owned_ids'] = held_listing_ids((int)$u['id']);
    // Contexte de stratégie du Classement : identifiant + réglages enregistrés (ou brouillon transmis par la page). Aucun contexte fiable ⇒ le moteur répond « indéterminée », jamais « retenue ».
    $ctIn = is_array($b['ct'] ?? null) ? $b['ct'] : [];
    $ctId = isset($ctIn['id']) && is_string($ctIn['id']) && preg_match('/^[a-z0-9-]{1,40}$/', $ctIn['id']) ? $ctIn['id'] : null;
    $ct = ['id' => null, 'state' => 'missing', 'spec' => null, 'label' => null, 'user_id' => (int)$u['id']];
    if ($ctId !== null) {
        $label = ct_label((int)$u['id'], $ctId);
        if ($label === null) { $ct['id'] = $ctId; }
        elseif (!empty($ctIn['draft_lost'])) { $ct = ['id' => $ctId, 'state' => 'draft_lost', 'spec' => null, 'label' => $label, 'user_id' => (int)$u['id']]; }
        elseif (is_array($ctIn['draft'] ?? null)) { $ct = ['id' => $ctId, 'state' => 'draft', 'spec' => $ctIn['draft'], 'label' => $label, 'user_id' => (int)$u['id']]; }
        else { $sv = ct_saved((int)$u['id'], $ctId); $ct = ['id' => $ctId, 'state' => ($sv && is_array($sv['config'])) ? 'saved' : (isset(CT_BUILTIN[$ctId]) ? 'default' : 'missing'), 'spec' => $sv['config'] ?? null,
            'label' => $label, 'user_id' => (int)$u['id']]; }
    }
    $sheet = engine_call('sheet', ['listing_id' => $id, 'ct' => $ct, 'config' => $cfg ?: 'regular', 'view' => $view, 'source' => $cfg ? $source : 'Croissance régulière (réglage par défaut)', 'fetch_profile' => true]);
    $sheet['holdings'] = [];
    foreach (q('SELECT p.id, p.name FROM portfolios p WHERE p.user_id = ? ORDER BY p.is_default DESC, p.name', [$u['id']])->fetchAll() as $p) {
        $v = portfolio_valuation((int)$p['id']);
        foreach ($v['positions'] as $pos) if ($pos['listing_id'] === $id) $sheet['holdings'][] = ['portfolio_id' => (int)$p['id'], 'portfolio' => $p['name'], 'qty' => $pos['qty'], 'avg_cost' => $pos['avg_cost'],
            'value' => $pos['value'], 'unrealized' => $pos['unrealized'], 'unrealized_pct' => $pos['unrealized_pct']];
    }
    return $sheet;
}

function listings_search(array $query): array {
    $term = mb_strtolower(trim((string)($query['q'] ?? '')));
    if (mb_strlen($term) < 2) return ['results' => []];
    $like = '%' . str_replace(['%', '_'], '', mb_substr($term, 0, 100)) . '%';
    // L'identité du produit vient du catalogue existant, jamais d'une ressemblance de nom.
    // Les symboles bruts restent recherchables même si leur place n'a pas été importée.
    $rows = q("SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary,
                      i.name, i.isin, i.kind, p.price, p.currency AS price_currency,
                      main.id AS primary_id, main.symbol AS primary_symbol, main.mic AS primary_mic,
                      main.status AS primary_status, main.primary_reason,
                      matches.matched_symbols
               FROM listings l JOIN instruments i ON i.id=l.instrument_id
               LEFT JOIN latest_prices p ON p.listing_id=l.id
               LEFT JOIN listings main ON main.instrument_id=i.id AND main.is_primary=1
               LEFT JOIN (SELECT group_key, GROUP_CONCAT(DISTINCT symbol ORDER BY symbol SEPARATOR ', ') AS matched_symbols
                          FROM catalogue_raw WHERE LOWER(symbol) LIKE ? GROUP BY group_key) matches ON matches.group_key=i.group_key
               WHERE LOWER(l.symbol) LIKE ? OR LOWER(i.name) LIKE ? OR LOWER(i.isin) LIKE ?
                  OR matches.group_key IS NOT NULL
                  OR i.id IN (SELECT instrument_id FROM listings WHERE LOWER(symbol) LIKE ?)
               ORDER BY (LOWER(l.symbol)=?) DESC, (l.status='selected' AND l.is_primary=1) DESC,
                        l.is_primary DESC, l.status='excluded', i.name, l.id LIMIT 20",
        [$like, $like, $like, $like, $like, $term])->fetchAll();
    foreach ($rows as &$row) {
        $row['in_catalogue'] = $row['status'] === 'selected' && (bool)$row['is_primary'];
        $row['primary'] = $row['primary_id'] === null ? null : [
            'id' => (int)$row['primary_id'], 'symbol' => $row['primary_symbol'], 'mic' => $row['primary_mic'],
            'in_catalogue' => $row['primary_status'] === 'selected', 'reason' => $row['primary_reason'],
        ];
        unset($row['primary_id'], $row['primary_symbol'], $row['primary_mic'], $row['primary_status'], $row['primary_reason']);
    }
    unset($row);
    return ['results' => $rows];
}
