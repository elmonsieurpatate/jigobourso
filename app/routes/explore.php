<?php
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/ledger.php';
require_once __DIR__ . '/../services/explorer_library.php';
require_once __DIR__ . '/../services/ct_strategies.php';

return [
    'explorer/library' => function () { $u=require_user();return explorer_library_list((int)$u['id']); },
    'explorer/library/save' => function () { need_post();$u=require_user();return explorer_library_save((int)$u['id'],body()); },
    'explorer/library/delete' => function () { need_post();$u=require_user();q('DELETE FROM explorer_saved WHERE id=? AND user_id=?',[(int)(body()['id']??0),$u['id']]);return ['ok'=>true]; },
    'explorer/detail' => function () { need_post();$u=require_user();$b=body();$view=clean_view($b['view']??
        []);$view['owned_ids']=held_listing_ids((int)$u['id']);return engine_call('sheet',['listing_id'=>(int)($b['id']??0),'config'=>$b['config']??'regular','view'=>$view,'fetch_profile'=>false]);
        },
    'classement-test/categories' => function () {
        require_user();
        // Compatibility URL; the shared settings service is now the sole live source.
        require_once __DIR__ . '/../services/secondary_filters.php';
        return secondary_read();
    },
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
    'ranking/criteria' => function () { require_user(); return engine_call('ranking-criteria', []); },   // critères de recherche historiques des stratégies intégrées (source : V4_STRATEGIES)
    'ranking/table' => function () {          // une seule lecture pour les notes ET les statuts des réglages appliqués
        $u = require_user();
        $b = [];
        if ($_SERVER['REQUEST_METHOD'] === 'POST') { need_post(); $b = body(); }
        $ct = (string)($b['strategy'] ?? $_GET['strategy'] ?? '');
        $ct = preg_match('/^[a-z0-9-]{1,40}$/', $ct) ? $ct : 'fast';
        $saved = ct_saved((int)$u['id'], $ct);
        $spec = is_array($b['config'] ?? null) ? $b['config'] : ($saved['config'] ?? null);
        $res = engine_call('ranking-table', ['ct_id' => $ct, 'user_id' => (int)$u['id'], 'spec' => $spec, 'include_curves' => ($b['include_curves'] ?? true) !== false]);
        $held = array_fill_keys(held_listing_ids((int)$u['id']), true);
        foreach ($res['rows'] as &$r) $r['held'] = isset($held[$r['id']]);
        unset($r);
        return $res;
    },
    'ranking/curves' => function () {         // courbes de la page visible seulement ; aucun calcul de notes
        need_post(); require_user(); $b = body();
        return engine_call('ranking-curves', ['ids' => $b['ids'] ?? []]);
    },
    'ranking/verdicts' => function () {       // statuts de stratégie (retenue / exclue / indéterminée) pour des critères en cours de modification : mêmes règles que le tableau et la fiche
        need_post(); $u = require_user(); $b = body();
        $ct = (string)($b['strategy'] ?? '');
        $ct = preg_match('/^[a-z0-9-]{1,40}$/', $ct) ? $ct : 'fast';
        return engine_call('ranking-verdicts', ['ct_id' => $ct, 'user_id' => (int)$u['id'], 'spec' => is_array($b['config'] ?? null) ? $b['config'] : null]);
    },
    'data/overview' => function () { require_admin(); return engine_call('overview', []); },
    'suivi' => function () { require_user(); return engine_call('suivi', []); },
    'bars15' => function () {                   // barres de 15 min stockées des 7 derniers jours (vue « 1 semaine » d'un graphique)
        require_user();
        $id = (int)($_GET['id'] ?? 0);
        $rows = q('SELECT slot_start, close_px FROM intraday_prices WHERE listing_id = ? AND slot_start >= (SELECT DATE_SUB(DATE(MAX(slot_start)), INTERVAL 7 DAY) FROM intraday_prices WHERE listing_id = ?) ORDER BY slot_start',
            [$id, $id])->fetchAll();
        return ['bars' => array_map(function ($r) { return [str_replace(' ', 'T', $r['slot_start']), (float)$r['close_px']]; }, $rows)];
    },
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
    },
    'listings/search' => function () {
        require_user();
        $term = mb_strtolower(trim((string)($_GET['q'] ?? '')));
        if (mb_strlen($term) < 2) return ['results' => []];
        $like = '%' . str_replace(['%', '_'], '', $term) . '%';
        $rows = q("SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, i.name, i.isin, i.kind, p.price, p.currency AS price_currency
   " .
            "                FROM listings l JOIN instruments i ON i.id = l.instrument_id LEFT JOIN latest_prices p ON p.listing_id = l.id
                   " .
            "WHERE LOWER(l.symbol) LIKE ? OR LOWER(i.name) LIKE ? OR LOWER(i.isin) LIKE ?
                   ORDER BY (LOWER(l.symbol) = ?) DESC, l.is_primary " .
            "DESC, l.status = 'excluded', i.name LIMIT 20", [$like, $like, $like, $term])->fetchAll();
        return ['results' => $rows];
    },
];
