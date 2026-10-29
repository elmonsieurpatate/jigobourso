<?php
// Dernières lignes d'un journal (fin du fichier seulement), éventuellement filtrées par expression régulière ; chaque ligne est tronquée.
function log_tail(string $file, int $n, ?string $re): array {
    if (!is_file($file) || !is_readable($file)) return [];
    $size = filesize($file);
    $fh = @fopen($file, 'rb');
    if (!$fh) return [];
    if ($size > 65536) fseek($fh, -65536, SEEK_END);
    $lines = preg_split('/\r?\n/', (string)stream_get_contents($fh), -1, PREG_SPLIT_NO_EMPTY);
    fclose($fh);
    if ($re !== null) $lines = array_values(array_filter($lines, fn($l) => preg_match($re, $l)));
    return array_map(fn($l) => mb_substr($l, 0, 300), array_slice($lines, -$n));
}

require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';

function system_counts(): array {
    $c = [];
    foreach (q("SELECT i.kind, l.status, COUNT(*) n FROM listings l JOIN instruments i ON i.id = l.instrument_id GROUP BY i.kind, l.status")->fetchAll() as $r) $c['listings'][$r['kind']][$r['status']] = (int)$r['n'];
    $c['primary_selected'] = (int)q("SELECT COUNT(*) FROM listings WHERE status = 'selected' AND is_primary = 1")->fetchColumn();
    $c['held'] = (int)q('SELECT COUNT(DISTINCT listing_id) FROM portfolio_transactions WHERE listing_id IS NOT NULL')->fetchColumn();
    return $c;
}

return [
    'admin/users' => function () {
        require_admin();
        return ['users' => q('SELECT id, username, email, is_admin, active, created_at, last_login, (SELECT COUNT(*) FROM portfolios p WHERE p.user_id = users.id) AS portfolios FROM users ORDER BY username')->fetchAll()];
    },
    'admin/user/create' => function () {
        need_post(); require_admin(); $b = body();
        return ['id' => create_user(str_in($b, 'username', 30), str_in($b, 'password', 200), str_in($b, 'email', 190, false) ?: null, !empty($b['is_admin']))];
    },
    'admin/user/update' => function () {
        need_post(); $me = require_admin(); $b = body();
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
    },
    'admin/system' => function () {
        require_admin();
        $jobs = q('SELECT id, job_type, trigger_by, status, started_at, finished_at, items_ok, items_error, summary FROM jobs ORDER BY id DESC LIMIT 40')->fetchAll();
        $logs = q("SELECT l.level, l.message, l.logged_at, j.job_type FROM job_logs l JOIN jobs j ON j.id = l.job_id ORDER BY l.id DESC LIMIT 40")->fetchAll();
        $sizes = q("SELECT table_name AS name, table_rows AS `rows`, ROUND((data_length + index_length) / 1048576, 1) AS mb FROM information_schema.tables WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' ORDER BY (data_length + index_length) DESC")->fetchAll();
        $freshness = q("SELECT l.mic, COUNT(*) AS followed, MAX(s.last_close_date) AS last_close, SUM(s.quality = 'stale') AS stale, SUM(s.quality = 'insufficient') AS insufficient, SUM(s.quality = 'break') AS broken
                        FROM v_collect_set c JOIN listings l ON l.id = c.listing_id LEFT JOIN series_state s ON s.listing_id = l.id GROUP BY l.mic ORDER BY l.mic")->fetchAll();
        $intraday = q('SELECT l.mic, MAX(p.price_time) AS last_price FROM latest_prices p JOIN listings l ON l.id = p.listing_id JOIN v_collect_set c ON c.listing_id = l.id GROUP BY l.mic')->fetchAll(PDO::FETCH_KEY_PAIR);
        foreach ($freshness as &$f) $f['last_price'] = $intraday[$f['mic']] ?? null;
        $gaps = q("SELECT state, COUNT(*) n FROM price_gaps GROUP BY state")->fetchAll(PDO::FETCH_KEY_PAIR);
        $settings = [];
        foreach (q('SELECT name, value_json FROM settings')->fetchAll() as $s) $settings[$s['name']] = $s['name'] === 'invite_code' ? (json_decode($s['value_json'], true) ? '••••' : '') : json_decode($s['value_json'], true);
        $catalogue = q('SELECT source_commit, loaded_at, rows_read, rows_kept FROM catalogue_loads ORDER BY id DESC LIMIT 1')->fetch();
        return ['counts' => system_counts(), 'jobs' => $jobs, 'logs' => $logs, 'tables' => $sizes, 'total_mb' => round(array_sum(array_column($sizes, 'mb')), 1),
                'freshness' => $freshness, 'gaps' => $gaps, 'settings' => $settings, 'catalogue' => $catalogue ?: null];
    },
    'admin/catalogue' => function () {
        require_admin();
        $term = mb_strtolower(trim((string)($_GET['q'] ?? '')));
        $where = []; $args = [];
        if ($term !== '') { $like = '%' . str_replace(['%', '_'], '', $term) . '%'; $where[] = '(LOWER(l.symbol) LIKE ? OR LOWER(i.name) LIKE ? OR LOWER(i.isin) LIKE ?)'; array_push($args, $like, $like, $like); }
        foreach (['kind' => 'i.kind', 'mic' => 'l.mic', 'status' => 'l.status'] as $k => $col) if (($_GET[$k] ?? '') !== '') { $where[] = "$col = ?"; $args[] = (string)$_GET[$k]; }
        if (($_GET['primary'] ?? '') === '1') $where[] = 'l.is_primary = 1';
        $w = $where ? ' WHERE ' . implode(' AND ', $where) : '';
        $page = max(1, (int)($_GET['page'] ?? 1)); $size = 50;
        $total = (int)q("SELECT COUNT(*) FROM listings l JOIN instruments i ON i.id = l.instrument_id$w", $args)->fetchColumn();
        $rows = q("SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, l.primary_reason, i.name, i.isin, i.kind, i.country, i.category, p.price, p.price_time, s.last_close_date, s.closes_count, s.quality
                   FROM listings l JOIN instruments i ON i.id = l.instrument_id LEFT JOIN latest_prices p ON p.listing_id = l.id LEFT JOIN series_state s ON s.listing_id = l.id$w ORDER BY i.name, l.mic LIMIT $size OFFSET " . (($page - 1) * $size), $args)->fetchAll();
        $reasons = q("SELECT excluded_reason r, COUNT(*) n FROM listings WHERE status = 'excluded' GROUP BY excluded_reason ORDER BY n DESC LIMIT 25")->fetchAll();
        $mics = q('SELECT DISTINCT mic FROM listings ORDER BY mic')->fetchAll(PDO::FETCH_COLUMN);
        $load = q('SELECT source_commit, loaded_at, rows_read, rows_kept, rules_json FROM catalogue_loads ORDER BY id DESC LIMIT 1')->fetch();
        return ['total' => $total, 'page' => $page, 'pages' => max(1, (int)ceil($total / $size)), 'rows' => $rows, 'exclusion_reasons' => $reasons, 'mics' => $mics,
                'rules' => $load && $load['rules_json'] ? json_decode($load['rules_json'], true) : null, 'load' => $load ? ['commit' => substr($load['source_commit'], 0, 8), 'loaded_at' => $load['loaded_at'], 'rows_read' => (int)$load['rows_read'], 'rows_kept' => (int)$load['rows_kept']] : null];
    },
    'admin/fdb' => function () { require_admin(); return engine_call('fdb-state', []); },
    'admin/yahoo' => function () { require_admin(); return engine_call('yahoo-state', []); },
    'admin/titles' => function () {
        require_admin();
        $keys = ['q', 'kind', 'mic', 'fdb', 'yahoo', 'final', 'daily', 'sort', 'dir'];
        $req = ['page' => (int)($_GET['page'] ?? 1)];
        foreach ($keys as $k) $req[$k] = (string)($_GET[$k] ?? '');
        return engine_call('titles', $req);
    },
    'admin/rules/save' => function () {
        need_post(); require_admin(); $b = body();
        return engine_call('rules-save', ['level' => str_in($b, 'level', 20), 'config' => is_array($b['config'] ?? null) ? $b['config'] : new stdClass()]);
    },
    'admin/rules/reset' => function () { need_post(); require_admin(); return engine_call('rules-reset', ['level' => str_in(body(), 'level', 20)]); },
    'admin/funnel' => function () { require_admin(); return engine_call('funnel', ['stage' => (string)($_GET['stage'] ?? '')]); },
    'admin/funnel/items' => function () {
        require_admin();
        return engine_call('funnel-items', ['stage' => (string)($_GET['stage'] ?? ''), 'step' => (string)($_GET['step'] ?? ''), 'q' => (string)($_GET['q'] ?? ''), 'kind' => (string)($_GET['kind'] ?? ''),
                                            'mic' => (string)($_GET['mic'] ?? ''), 'page' => (int)($_GET['page'] ?? 1), 'quality' => (string)($_GET['quality'] ?? '')]);
    },
    'admin/funnel/explain' => function () { require_admin(); return engine_call('funnel-explain', ['q' => (string)($_GET['q'] ?? '')]); },
    'admin/cron' => function () {
        // (journaux du cron lus ci-dessous : lignes d'erreur de cron.log et appels refusés de cron-rejets.log)
        require_admin();
        $file = cfg('JIGO_CRON_KEY_FILE', '');
        $s = engine_call('schedule-get', []);
        $dir = cfg('JIGO_LOG_DIR', engine_root() . '/logs');
        $s['site'] = ['cron_key_present' => $file !== '' && is_file($file) && trim((string)file_get_contents($file)) !== '', 'cron_path' => 'api/cron?k=<clé>',
                      'rejected' => log_tail($dir . '/cron-rejets.log', 10, null), 'log_errors' => log_tail($dir . '/cron.log', 15, '/Traceback|Error|Exception|No such file|not found|denied|Permission|failed|cannot|Killed/i')];
        return $s;
    },
    'admin/cron/save' => function () { need_post(); require_admin(); return engine_call('schedule-save', body()); },
    'admin/cron/test' => function () {
        need_post(); require_admin();
        $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/admin.log';
        if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
        return ['started' => true, 'pid' => engine_spawn('tick', $log, ['--trigger', 'admin']), 'note' => 'Un passage est lancé maintenant, comme le ferait le cron. Il n’est pas compté comme un passage du cron.'];
    },
    'admin/jobs' => function () {
        require_admin();
        return engine_call('jobs-list', ['type' => (string)($_GET['type'] ?? ''), 'status' => (string)($_GET['status'] ?? ''), 'trigger' => (string)($_GET['trigger'] ?? ''),
                                         'since' => (string)($_GET['since'] ?? ''), 'page' => (int)($_GET['page'] ?? 1)]);
    },
    'admin/job' => function () { require_admin(); return engine_call('job-detail', ['id' => (int)($_GET['id'] ?? 0)]); },
    'admin/settings' => function () {
        need_post(); require_admin(); $b = body();
        $name = str_in($b, 'name', 64); $v = $b['value'] ?? null;
        $rules = [
            'intraday_retention_sessions' => function ($v) { if (!is_numeric($v) || $v < 5 || $v > 60) throw new ApiError('Rétention : 5 à 60 séances'); return (int)$v; },
            'invite_code' => function ($v) { $v = trim((string)$v); if ($v !== '' && !preg_match('/^[\p{L}\p{N} _.-]{4,60}$/u', $v)) throw new ApiError('Mot d’invitation : 4 à 60 caractères'); return $v; },
        ];
        if (!isset($rules[$name])) throw new ApiError('Réglage inconnu');
        $val = $rules[$name]($v);
        q('INSERT INTO settings(name, value_json, updated_at) VALUES (?,?,?) ON DUPLICATE KEY UPDATE value_json = VALUES(value_json), updated_at = VALUES(updated_at)', [$name, json_encode($val), now_utc()]);
        return ['ok' => true];
    },
    'admin/run' => function () {
        need_post(); require_admin();
        $job = str_in(body(), 'job', 24);
        $labels = ['fdb_import' => 'Import FinanceDatabase', 'fdb_filter' => 'Filtrage FinanceDatabase', 'yahoo_info' => 'Import des informations Yahoo', 'yahoo_filter' => 'Filtrage Yahoo',
                   'history' => 'Import / mise à jour des historiques'];
        if (!isset($labels[$job])) throw new ApiError('Traitement inconnu');
        engine_call('job-check', ['name' => $job]);          // 422 avec un message clair si l'étape précédente manque ou si un traitement est en cours
        $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/admin.log';
        if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
        return ['started' => true, 'label' => $labels[$job], 'pid' => engine_spawn('job', $log, ['--name', $job, '--trigger', 'admin'])];
    },
];
