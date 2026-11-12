<?php
// Requêtes vers le moteur pour le classement et la simulation de scores : une seule construction, partagée par l'administration
// (sans $userId : réglages officiels) et par l'utilisateur (avec $userId : réglages personnels, références officielles jamais modifiées).
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/ct_strategies.php';

function scores_ranking_request(array $actor, array $b, ?int $userId = null): array {
    $specs = []; foreach ((ct_all((int)$actor['id'])['items'] ?? []) as $it) if (is_array($it['config'] ?? null)) $specs[$it['id']] = $it['config'];
    $req = ['strategy' => str_in($b, 'strategy', 40), 'ct_specs' => (object)$specs, 'sort' => is_array($b['sort'] ?? null) ? array_slice($b['sort'], 0, 3) : [],
        'verdict' => in_array($b['verdict'] ?? '', ['retained', 'excluded', 'undetermined'], true) ? $b['verdict'] : 'all', 'draft' => is_array($b['draft'] ?? null) ? $b['draft'] : null,
        'which' => ($b['which'] ?? '') === 'complex' ? 'complex' : 'simple', 'category' => isset($b['category']) && is_string($b['category']) ? mb_substr($b['category'], 0, 60) : null,
        'offset' => max(0, (int)($b['offset'] ?? 0)), 'limit' => max(1, min(100, (int)($b['limit'] ?? 25)))];
    return $userId === null ? $req : ['user_id' => $userId] + $req;
}
function scores_simulate_request(array $b, ?int $userId = null): array {
    $req = ['strategy' => str_in($b, 'strategy', 40), 'q' => isset($b['q']) ? mb_substr((string)$b['q'], 0, 80) : '',
        'listing_id' => isset($b['listing_id']) ? (int)$b['listing_id'] : null, 'draft' => is_array($b['draft'] ?? null) ? $b['draft'] : null];
    return $userId === null ? $req : ['user_id' => $userId] + $req;
}
