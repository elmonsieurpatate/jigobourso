<?php
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/ledger.php';
require_once __DIR__ . '/../services/explorer_library.php';
require_once __DIR__ . '/../services/ct_strategies.php';

require_once __DIR__ . '/../services/explore_actions.php';

return [
    'explorer/library' => function () { $u=require_user();return explorer_library_list((int)$u['id']); },
    'explorer/library/save' => function () { need_post();$u=require_user();return explorer_library_save((int)$u['id'],body()); },
    'explorer/library/delete' => function () { need_post(); $u = require_user(); return explorer_delete_saved($u, body()); },
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
    'explore' => function () { need_post(); $u = require_user(); return explorer_run($u, body()); },
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
    'bars15' => function () { require_user(); return explorer_intraday_bars($_GET); },
    'intraday' => function () {
        require_user();
        return engine_call('intraday', ['listing_id' => (int)($_GET['id'] ?? 0), 'fetch' => ($_GET['fetch'] ?? '1') !== '0']);
    },
    'sheet' => function () { $u = require_user(); return explorer_sheet($u, $_SERVER['REQUEST_METHOD'] === 'POST' ? body() : [], $_GET); },
    'listings/search' => function () { require_user(); return listings_search($_GET); },
];
