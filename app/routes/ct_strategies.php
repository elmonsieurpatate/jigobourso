<?php
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../services/ct_strategies.php';
return [
    'classement-test/strategies' => function () { $u = require_user(); return ct_read((int)$u['id']); },
    'classement-test/strategies/save' => function () { need_post(); $u = require_user(); return ct_write((int)$u['id'], body()); },
    // statut de chaque stratégie du compte : Officielle / Adaptée / Personnelle, critères et scores jugés séparément
    'strategies/status' => function () {
        $u = require_user();
        $items = []; foreach ((ct_all((int)$u['id'])['items'] ?? []) as $it) $items[] = ['id' => $it['id'], 'name' => $it['name'] ?? $it['id'], 'builtin' => !empty($it['builtin']), 'config' => $it['config'] ?? null];
        return engine_call('strategies-status', ['user_id' => (int)$u['id'], 'ct_items' => $items]);
    },
    // faits des sept stratégies lus dans le moteur (aucune valeur recopiée) : alimentent les fiches d'aide
    'help/facts' => function () { require_user(); return engine_call('help-facts', []); },
    'my/scores' => function () { $u = require_user(); return engine_call('scores-user-state', ['user_id' => (int)$u['id']]); },
    'my/scores/save' => function () {
        need_post(); $u = require_user(); $b = body();
        $req = ['user_id' => (int)$u['id']];
        foreach (['reset', 'name', 'profile'] as $k) if (array_key_exists($k, $b)) $req[$k] = $b[$k];
        return engine_call('scores-user-save', $req);
    },
    'my/scores/preview' => function () {
        need_post(); $u = require_user(); $b = body();
        return engine_call('scores-preview', ['user_id' => (int)$u['id'], 'kappa' => $b['kappa'] ?? null, 'periods' => is_array($b['periods'] ?? null) ? $b['periods'] : []]);
    },
    'my/scores/simulate' => function () {
        need_post(); $u = require_user(); $b = body();
        return engine_call('scores-simulate', ['user_id' => (int)$u['id'], 'strategy' => str_in($b, 'strategy', 40), 'q' => isset($b['q']) ? mb_substr((string)$b['q'], 0, 80) : '',
            'listing_id' => isset($b['listing_id']) ? (int)$b['listing_id'] : null, 'draft' => is_array($b['draft'] ?? null) ? $b['draft'] : null]);
    },
    'my/scores/ranking' => function () { need_post(); $u = require_user(); return engine_call('scores-ranking', my_ranking_request($u, body())); },
];
