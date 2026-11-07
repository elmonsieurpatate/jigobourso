<?php
require_once __DIR__ . '/../services/ct_strategies.php';
/** Réglages de scores PERSONNELS : mêmes commandes du moteur que l'administration, mais toujours dans le compte de l'utilisateur connecté (références officielles jamais modifiées). */
function my_ranking_request(array $u, array $b): array {
    $specs = []; foreach ((ct_all((int)$u['id'])['items'] ?? []) as $it) if (is_array($it['config'] ?? null)) $specs[$it['id']] = $it['config'];
    return ['user_id' => (int)$u['id'], 'strategy' => str_in($b, 'strategy', 40), 'ct_specs' => (object)$specs, 'sort' => is_array($b['sort'] ?? null) ? array_slice($b['sort'], 0, 3) : [],
        'verdict' => in_array($b['verdict'] ?? '', ['retained', 'excluded', 'undetermined'], true) ? $b['verdict'] : 'all', 'draft' => is_array($b['draft'] ?? null) ? $b['draft'] : null,
        'which' => ($b['which'] ?? '') === 'complex' ? 'complex' : 'simple', 'category' => isset($b['category']) && is_string($b['category']) ? mb_substr($b['category'], 0, 60) : null,
        'offset' => max(0, (int)($b['offset'] ?? 0)), 'limit' => max(1, min(100, (int)($b['limit'] ?? 25)))];
}
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
