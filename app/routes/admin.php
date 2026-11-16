<?php
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/config.php';
require_once __DIR__ . '/../lib/account.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/admin.php';
require_once __DIR__ . '/../services/ct_strategies.php';
require_once __DIR__ . '/../services/scores.php';

require_once __DIR__ . '/../services/admin_actions.php';

return [
    'admin/splits' => function () {
        require_admin();
        return engine_call('split-reviews', ['state' => (string)($_GET['state'] ?? 'pending'), 'q' => (string)($_GET['q'] ?? ''), 'page' => max(1,(int)($_GET['page'] ?? 1)), 'sort' => (string)($_GET['sort'] ?? 'magnitude_desc'),
            'min_ratio' => (string)($_GET['min_ratio'] ?? '1')]);
    },
    'admin/splits/scan' => function () { need_post(); require_admin(); return engine_call('split-review-scan', []); },
    'admin/splits/decide' => function () {
        need_post(); $u = require_admin(); $b = body(); $b['actor_id'] = (int)$u['id'];
        $result = engine_call('split-review-decide', $b);
        if (!empty($result['changed']) && !empty($result['recompute_pending'])) {
            try { $result['recompute_started'] = engine_spawn('job', engine_root() . '/logs/admin.log', ['--name','metrics','--trigger','admin']) > 0; }
            catch (Throwable $e) { $result['recompute_started'] = false; } // le cron reprendra la demande persistée
        }
        return $result;
    },
    'admin/users' => function () { require_admin(); return admin_list_users(); },
    'admin/user/create' => function () {
        need_post(); require_admin(); $b = body();
        return ['id' => create_user(str_in($b, 'username', 30), password_input($b, 'password'), str_in($b, 'email', 190, false) ?: null, !empty($b['is_admin']))];
    },
    'admin/user/update' => function () { need_post(); $me = require_admin(); return admin_update_user($me, body()); },
    'admin/system' => function () { require_admin(); return admin_system_state(); },
    'admin/catalogue' => function () { require_admin(); return admin_catalogue_search($_GET); },
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
        $s['site'] = ['cron_key_present' => $file !== '' && is_file($file) && trim((string)file_get_contents($file)) !== '', 'cron_path' => 'api/cron (en-tête X-Cron-Key)',
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
                                         'since' => (string)($_GET['since'] ?? ''), 'all' => (string)($_GET['all'] ?? ''), 'page' => (int)($_GET['page'] ?? 1)]);
    },
    'admin/job' => function () { require_admin(); return engine_call('job-detail', ['id' => (int)($_GET['id'] ?? 0)]); },
    'admin/settings' => function () { need_post(); require_admin(); return admin_save_setting(body()); },
    'admin/scores' => function () { require_admin(); return engine_call('scores-state', []); },
    'admin/scores/save' => function () {
        need_post(); require_admin(); $b = body();
        $req = [];
        foreach (['reset', 'name', 'global', 'profile', 'kappa', 'threshold', 'complex_weights'] as $k) if (array_key_exists($k, $b)) $req[$k] = $b[$k];
        return engine_call('scores-save', $req);
    },
    'admin/scores/preview' => function () {
        need_post(); require_admin(); $b = body();
        return engine_call('scores-preview', ['kappa' => $b['kappa'] ?? null, 'periods' => is_array($b['periods'] ?? null) ? $b['periods'] : []]);
    },
    'admin/scores/simulate' => function () { need_post(); require_admin(); return engine_call('scores-simulate', scores_simulate_request(body())); },
    'admin/scores/ranking' => function () { need_post(); $adm = require_admin(); return engine_call('scores-ranking', scores_ranking_request($adm, body())); },
    'admin/scores/monitor' => function () { require_admin(); return engine_call('scores-monitor', []); },
    'admin/run' => function () {
        need_post(); require_admin();
        $job = str_in(body(), 'job', 24);
        $labels = ['fdb_import' => 'Import FinanceDatabase', 'fdb_filter' => 'Filtrage FinanceDatabase', 'yahoo_info' => 'Import des informations Yahoo', 'yahoo_filter' => 'Filtrage Yahoo',
                   'history' => 'Import / mise à jour des historiques', 'gaps' => 'Clôtures manquantes (tout le catalogue)', 'volumes' => 'Volumes quotidiens (tout le catalogue)', 'maintenance' => 'Entretien après collecte',
                       'metrics' => 'Indicateurs et classements', 'etf' => 'Similarité des ETF'];
        if (!isset($labels[$job])) throw new ApiError('Traitement inconnu');
        engine_call('job-check', ['name' => $job]);          // 422 avec un message clair si l'étape précédente manque ou si un traitement est en cours
        $log = cfg('JIGO_LOG_DIR', engine_root() . '/logs') . '/admin.log';
        if (!is_dir(dirname($log))) @mkdir(dirname($log), 0700, true);
        return ['started' => true, 'label' => $labels[$job], 'pid' => engine_spawn('job', $log, ['--name', $job, '--trigger', 'admin'])];
    },
];
