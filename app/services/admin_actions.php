<?php
// Cas d’usage admin : entrées explicites, autorisations métier conservées.
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/config.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/settings.php';
require_once __DIR__ . '/admin.php';

function admin_list_users(): array {
    return ['users' => q('SELECT id, username, email, is_admin, active, created_at, last_login, (SELECT COUNT(*) FROM portfolios p WHERE p.user_id = users.id) AS portfolios FROM users ORDER BY username')->fetchAll()];
}

function admin_update_user(array $me, array $b): array {
    $id = (int)($b['id'] ?? 0);
    $u = q('SELECT * FROM users WHERE id = ?', [$id])->fetch();
    if (!$u) throw new ApiError('Utilisateur introuvable', 404);
    $flag = function ($v) { return filter_var($v, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE); };   // "false" / "0" / false → faux (et non vrai)
    $active = isset($b['active']) ? $flag($b['active']) : null;
    $isAdmin = isset($b['is_admin']) ? $flag($b['is_admin']) : null;
    if ((isset($b['active']) && $active === null) || (isset($b['is_admin']) && $isAdmin === null)) throw new ApiError('Valeur booléenne attendue', 422);
    if ($id === (int)$me['id'] && ($active === false || $isAdmin === false)) throw new ApiError('Vous ne pouvez pas retirer vos propres droits', 422);
    if ($active !== null) q('UPDATE users SET active = ? WHERE id = ?', [$active ? 1 : 0, $id]);
    if ($isAdmin !== null) q('UPDATE users SET is_admin = ? WHERE id = ?', [$isAdmin ? 1 : 0, $id]);
    if (!empty($b['password'])) { valid_password((string)$b['password']); q('UPDATE users SET pass_hash = ? WHERE id = ?', [password_hash((string)$b['password'], PASSWORD_DEFAULT), $id]); q('DELETE FROM sessions WHERE user_id = ?', [$id]); }
    if ($active === false) q('DELETE FROM sessions WHERE user_id = ?', [$id]);
    return ['ok' => true];
}

function admin_system_state(): array {
    $jobs = q('SELECT id, job_type, trigger_by, status, started_at, finished_at, items_ok, items_error, summary FROM jobs ORDER BY id DESC LIMIT 40')->fetchAll();
    $logs = q("SELECT l.level, l.message, l.logged_at, j.job_type FROM job_logs l JOIN jobs j ON j.id = l.job_id ORDER BY l.id DESC LIMIT 40")->fetchAll();
    $sizes = q("SELECT table_name AS name, table_rows AS `rows`, ROUND((data_length + index_length) / 1048576, 1) AS mb FROM information_schema.tables WHERE " .
        "table_schema = DATABASE() AND table_type = 'BASE TABLE' ORDER BY (data_length + index_length) DESC")->fetchAll();
    $freshness = q("SELECT l.mic, COUNT(*) AS followed, MAX(s.last_close_date) AS last_close, SUM(s.quality = 'stale') AS stale, SUM(s.quality = 'insufficient') AS " .
        "insufficient, SUM(s.quality = 'break') AS broken
                    FROM v_collect_set c JOIN listings l ON l.id = c.listing_id LEFT JOIN " .
        "series_state s ON s.listing_id = l.id GROUP BY l.mic ORDER BY l.mic")->fetchAll();
    $intraday = q('SELECT l.mic, MAX(p.price_time) AS last_price FROM latest_prices p JOIN listings l ON l.id = p.listing_id JOIN v_collect_set c ON c.listing_id = l.id GROUP BY l.mic')->fetchAll(PDO::FETCH_KEY_PAIR);
    foreach ($freshness as &$f) $f['last_price'] = $intraday[$f['mic']] ?? null;
    $gaps = q("SELECT state, COUNT(*) n FROM price_gaps GROUP BY state")->fetchAll(PDO::FETCH_KEY_PAIR);
    $settings = [];
    foreach (q('SELECT name, value_json FROM settings')->fetchAll() as $s) $settings[$s['name']] = json_decode($s['value_json'], true);
    if (!empty($settings['invite_code']) && is_string($settings['invite_code'])) {        // le mot d'invitation n'est jamais renvoyé en clair (il reste modifiable) : première lettre et longueur seulement
        $code = $settings['invite_code'];
        $settings['invite_code'] = mb_substr($code, 0, 1) . str_repeat('•', max(0, mb_strlen($code) - 1));
    }
    $catalogue = q('SELECT source_commit, loaded_at, rows_read, rows_kept FROM catalogue_loads ORDER BY id DESC LIMIT 1')->fetch();
    return ['counts' => system_counts(), 'jobs' => $jobs, 'logs' => $logs, 'tables' => $sizes, 'total_mb' => round(array_sum(array_column($sizes, 'mb')), 1),
            'freshness' => $freshness, 'gaps' => $gaps, 'settings' => $settings, 'catalogue' => $catalogue ?: null];
}

function admin_catalogue_search(array $query): array {
    $term = mb_strtolower(trim((string)($query['q'] ?? '')));
    $where = []; $args = [];
    if ($term !== '') { $like = '%' . str_replace(['%', '_'], '', $term) . '%'; $where[] = '(LOWER(l.symbol) LIKE ? OR LOWER(i.name) LIKE ? OR LOWER(i.isin) LIKE ?)'; array_push($args, $like, $like, $like); }
    foreach (['kind' => 'i.kind', 'mic' => 'l.mic', 'status' => 'l.status'] as $k => $col) if (($query[$k] ?? '') !== '') { $where[] = "$col = ?"; $args[] = (string)$query[$k]; }
    if (($query['primary'] ?? '') === '1') $where[] = 'l.is_primary = 1';
    $w = $where ? ' WHERE ' . implode(' AND ', $where) : '';
    $size = 50; $page = min(100000, max(1, (int)($query['page'] ?? 1)));   // page bornée ; LIMIT/OFFSET liés en paramètres
    $total = (int)q("SELECT COUNT(*) FROM listings l JOIN instruments i ON i.id = l.instrument_id$w", $args)->fetchColumn();
    $rows = q("SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, l.primary_reason, i.name, i.isin, i.kind, i.country, i.category, p.price, p.price_time, s.last_close_date, s.closes_count, s.quality
               FROM listings l JOIN instruments i ON i.id = l.instrument_id LEFT JOIN latest_prices p ON p.listing_id = l.id LEFT JOIN series_state s ON s.listing_id = l.id$w ORDER BY i.name, l.mic LIMIT ? OFFSET ?",
        array_merge($args, [$size, ($page - 1) * $size]))->fetchAll();
    $reasons = q("SELECT excluded_reason r, COUNT(*) n FROM listings WHERE status = 'excluded' GROUP BY excluded_reason ORDER BY n DESC LIMIT 25")->fetchAll();
    $mics = q('SELECT DISTINCT mic FROM listings ORDER BY mic')->fetchAll(PDO::FETCH_COLUMN);
    $load = q('SELECT source_commit, loaded_at, rows_read, rows_kept, rules_json FROM catalogue_loads ORDER BY id DESC LIMIT 1')->fetch();
    return ['total' => $total, 'page' => $page, 'pages' => max(1, (int)ceil($total / $size)), 'rows' => $rows, 'exclusion_reasons' => $reasons, 'mics' => $mics,
            'rules' => $load && $load['rules_json'] ? json_decode($load['rules_json'], true) : null, 'load' => $load ? ['commit' => substr($load['source_commit'], 0, 8), 'loaded_at' => $load['loaded_at'],
                'rows_read' => (int)$load['rows_read'], 'rows_kept' => (int)$load['rows_kept']] : null];
}

function admin_save_setting(array $b): array {
    $name = str_in($b, 'name', 64); $v = $b['value'] ?? null;
    $rules = [
        'intraday_retention_sessions' => function ($v) { if (!is_numeric($v) || $v < 5 || $v > 60) throw new ApiError('Rétention : 5 à 60 séances'); return (int)$v; },
        'invite_code' => function ($v) { $v = trim((string)$v); if ($v !== '' && !preg_match('/^[\p{L}\p{N} _.-]{4,60}$/u', $v)) throw new ApiError('Mot d’invitation : 4 à 60 caractères'); return $v; },
    ];
    if (!isset($rules[$name])) throw new ApiError('Réglage inconnu');
    $val = $rules[$name]($v);
    q('INSERT INTO settings(name, value_json, updated_at) VALUES (?,?,?) ON DUPLICATE KEY UPDATE value_json = VALUES(value_json), updated_at = VALUES(updated_at)', [$name, json_encode($val), now_utc()]);
    return ['ok' => true];
}
