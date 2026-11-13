<?php
// Centre d'alertes : règles par position (héritées d'une stratégie ou personnelles), historique, stratégie d'origine des achats, stratégie de surveillance.
// Chaque requête est bornée à l'utilisateur connecté et à ses portefeuilles. Aucune vente automatique : une règle ne fait que signaler.
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/alerts.php';
require_once __DIR__ . '/../services/ct_strategies.php';
require_once __DIR__ . '/../services/portfolio_access.php';
require_once __DIR__ . '/../services/ledger.php';

return [
    'alerts/state' => function () {
        $u = require_user();
        $pid = (int)($_GET['portfolio'] ?? 0);
        $p = $pid ? own_portfolio($pid, $u) : (q('SELECT * FROM portfolios WHERE user_id = ? ORDER BY is_default DESC, id LIMIT 1', [$u['id']])->fetch() ?: null);
        if (!$p) return ['portfolio' => null, 'positions' => [], 'rules' => [], 'events' => [], 'counts' => ['active' => 0, 'triggered' => 0, 'todo' => 0, 'insufficient' => 0]];
        alert_import_legacy($u, (int)$p['id']);
        $val = portfolio_valuation((int)$p['id']);
        $strategies = alert_strategies($u);
        $pos = []; $rules = q('SELECT * FROM alert_rules WHERE user_id = ? AND portfolio_id = ? ORDER BY id', [$u['id'], $p['id']])->fetchAll();
        $by = []; foreach ($rules as $r) $by[(int)$r['listing_id']][] = $r;
        $watch = []; $wmv = []; foreach (q('SELECT listing_id, strategy_key, model_version FROM position_watch WHERE portfolio_id = ?', [$p['id']])->fetchAll() as $w) { $watch[(int)$w['listing_id']] = $w['strategy_key'];
            $wmv[(int)$w['listing_id']] = $w['model_version'] === null ? null : (int)$w['model_version']; }
        $latest = []; foreach (q("SELECT strategy_key, MAX(version) v FROM alert_models WHERE status = 'published' GROUP BY strategy_key")->fetchAll() as $m) $latest[$m['strategy_key']] = (int)$m['v'];
        foreach ($val['positions'] as $x) {
            if (!$x['listing_id'] || $x['qty'] <= 0) continue;
            $lid = (int)$x['listing_id'];
            $origins = array_map(fn($o) => ['tx' => (int)$o['transaction_id'], 'date' => $o['trade_at'], 'strategy' => $o['strategy_key'], 'label' => alert_label($strategies, $o['strategy_key']), 'status' => $o['status'],
                'by' => $o['set_by']], alert_origin_for((int)$u['id'], (int)$p['id'], $lid));
            $legacyLot = q("SELECT s.strategy, t.id FROM lot_settings s JOIN portfolio_transactions t ON t.id = s.transaction_id WHERE t.portfolio_id = ? AND t.listing_id = ? AND s.strategy IS NOT NULL", [$p['id'], $lid])->fetchAll();
            $pos[] = ['listing_id' => $lid, 'symbol' => $x['symbol'], 'name' => $x['name'], 'kind' => $x['kind'] ?? null, 'price' => $x['price'] ?? null, 'currency' => $x['price_currency'] ?? $x['currency'], 'value' => $x['value'] ?? null,
                      'origins' => $origins, 'lot_strategies' => array_map(fn($l) => ['tx' => (int)$l['id'], 'strategy' => $l['strategy'], 'label' => alert_label($strategies, $l['strategy'])], $legacyLot),
                      'watch' => isset($watch[$lid]) ? ['key' => $watch[$lid], 'label' => $strategies[$watch[$lid]]['label'] ?? $watch[$lid], 'status' => $strategies[$watch[$lid]]['status'] ?? null, 'model_version' => $wmv[$lid] ?? null,
                          'model_latest' => $latest[$watch[$lid]] ?? null] : null,
                      'rules' => count($by[$lid] ?? []),
                      'watch_log' => q('SELECT at, summary FROM position_watch_log WHERE portfolio_id = ? AND listing_id = ? ORDER BY at DESC, id DESC LIMIT 6', [$p['id'], $lid])->fetchAll()];
        }
        $events = q('SELECT e.*, r.kind, r.listing_id FROM alert_events e JOIN alert_rules r ON r.id = e.rule_id WHERE e.user_id = ? AND r.portfolio_id = ? ORDER BY e.at DESC, e.id DESC LIMIT 80', [$u['id'], $p['id']])->fetchAll();
        $c = ['active' => 0, 'triggered' => 0, 'todo' => 0, 'insufficient' => 0];
        foreach ($rules as $r) { if (!(int)$r['enabled']) continue; $c['active']++; if ($r['state'] === 'triggered' && $r['acked_at'] === null) $c['triggered']++; if (in_array($r['state'], ['insufficient',
            'error'], true) || $r['state'] === null) $c['insufficient']++; }
        $held = array_column($pos, 'listing_id'); foreach ($pos as $x) if (!$x['rules']) $c['todo']++;
        $prefs = $u['prefs_json'] ? (json_decode($u['prefs_json'], true) ?: []) : [];
        return ['portfolio' => ['id' => (int)$p['id'], 'name' => $p['name']], 'portfolios' => q('SELECT id, name FROM portfolios WHERE user_id = ? ORDER BY is_default DESC, id', [$u['id']])->fetchAll(),
            'positions' => $pos, 'rules' => array_map('alert_rule_view', $rules),
                'events' => array_map(function ($e) { $e['id'] = (int)$e['id']; $e['rule_id'] = (int)$e['rule_id']; $e['listing_id'] = (int)$e['listing_id']; return $e; }, $events), 'counts' => $c,
                'strategies' => array_values(array_map(fn($s) => ['key' => $s['key'], 'label' => $s['label'], 'status' => $s['status']], $strategies)),
                'prefs' => ['alert_email' => $prefs['alert_email'] ?? true, 'alert_digest' => $prefs['alert_digest'] ?? false]];
    },
    'alerts/rule-save' => function () {
        need_post(); $u = require_user(); $b = body();
        $kind = (string)($b['kind'] ?? ''); if (!in_array($kind, ALERT_KINDS, true)) throw new ApiError('Type d’alerte inconnu', 422);
        $gran = $b['granularity'] ?? null; if (in_array($kind, ALERT_TREND, true)) { if (!in_array($gran, ALERT_GRAN, true)) throw new ApiError('Choisissez la durée de mesure', 422); } else $gran = null;
        $thr = $b['threshold'] ?? null; if ($thr === '' || $thr === null) throw new ApiError('Indiquez un seuil', 422); if (!is_numeric($thr) || abs((float)$thr) > 1e9) throw new ApiError('Seuil invalide', 422);
        $sev = in_array($b['severity'] ?? 'vigilance', ALERT_SEV, true) ? ($b['severity'] ?? 'vigilance') : 'vigilance';
        if (!empty($b['id'])) {
            $r = alert_owned_rule((int)$b['id'], $u);
            q('UPDATE alert_rules SET threshold = ?, granularity = ?, severity = ?, enabled = ?, updated_at = ? WHERE id = ?', [(float)$thr, $gran, $sev, empty($b['enabled']) && array_key_exists('enabled', $b) ? 0 : 1, now_utc(), $r['id']]);
            if (abs((float)$r['threshold'] - (float)$thr) > 2e-6) alert_log_change((int)$r['portfolio_id'], (int)$r['listing_id'], 'Seuil modifié : ' . (ALERT_LABELS[$r['kind']] ?? $r['kind']) . ' ' . rtrim(rtrim(number_format((float)$r['threshold'],
                4, ',', ''), '0'), ',') . ' → ' . rtrim(rtrim(number_format((float)$thr, 4, ',', ''), '0'), ',') . '.');
            return ['id' => (int)$r['id']];
        }
        $p = own_portfolio((int)($b['portfolio_id'] ?? 0), $u); $lid = (int)($b['listing_id'] ?? 0);
        $held = array_filter(portfolio_valuation((int)$p['id'])['positions'], fn($x) => (int)$x['listing_id'] === $lid && $x['qty'] > 0);
        if (!$lid || !$held) throw new ApiError('Titre non détenu dans ce portefeuille', 404);
        $id = alert_insert($u, (int)$p['id'], $lid, ['kind' => $kind, 'granularity' => $gran, 'threshold' => (float)$thr, 'severity' => $sev], 'personal', null);
        return ['id' => $id];
    },
    'alerts/rule-toggle' => function () {
        need_post(); $u = require_user(); $b = body(); $r = alert_owned_rule((int)($b['id'] ?? 0), $u);
        $on = !empty($b['enabled']) ? 1 : 0; q('UPDATE alert_rules SET enabled = ?, state = ?, updated_at = ? WHERE id = ?', [$on, $on ? null : $r['state'], now_utc(), $r['id']]);
        alert_log_change((int)$r['portfolio_id'], (int)$r['listing_id'], ($on ? 'Règle activée : ' : 'Règle désactivée : ') . (ALERT_LABELS[$r['kind']] ?? $r['kind']) . '.');
        return ['ok' => true];
    },
    'alerts/rule-delete' => function () { need_post(); $u = require_user(); $r = alert_owned_rule((int)(body()['id'] ?? 0), $u); q('DELETE FROM alert_rules WHERE id = ?', [$r['id']]); return ['ok' => true]; },
    'alerts/rule-ack' => function () {
        need_post(); $u = require_user(); $r = alert_owned_rule((int)(body()['id'] ?? 0), $u);
        q('UPDATE alert_rules SET acked_at = ? WHERE id = ?', [now_utc(), $r['id']]); alert_event((int)$r['id'], (int)$u['id'], 'acked'); return ['ok' => true];
    },
    'alerts/rule-rearm' => function () {
        need_post(); $u = require_user(); $r = alert_owned_rule((int)(body()['id'] ?? 0), $u);
        q('UPDATE alert_rules SET acked_at = NULL, state = NULL, notified_at = NULL, updated_at = ? WHERE id = ?', [now_utc(), $r['id']]); alert_event((int)$r['id'], (int)$u['id'], 'rearmed'); return ['ok' => true];
    },
    'alerts/rule-restore' => function () {
        need_post(); $u = require_user(); $r = alert_owned_rule((int)(body()['id'] ?? 0), $u);
        if ($r['default_threshold'] === null) throw new ApiError('Cette règle n’a pas de valeur d’origine', 422);
        q('UPDATE alert_rules SET threshold = ?, updated_at = ? WHERE id = ?', [$r['default_threshold'], now_utc(), $r['id']]); alert_log_change((int)$r['portfolio_id'], (int)$r['listing_id'], 'Seuil du modèle restauré : ' .
            (ALERT_LABELS[$r['kind']] ?? $r['kind']) . '.');
            return ['ok' => true];
    },
    // Modèle de surveillance d'une stratégie appliqué à une position : ajoute les règles manquantes ; en mode « sync », met à jour les règles héritées non modifiées et conserve les personnalisées.
    'alerts/apply-template' => function () {
        need_post(); $u = require_user(); $b = body(); $p = own_portfolio((int)($b['portfolio_id'] ?? 0), $u);
        $lid = (int)($b['listing_id'] ?? 0); $key = (string)($b['strategy'] ?? '');
        if (!$lid) throw new ApiError('Titre manquant', 422);
        $dry = !empty($b['dry']);
        $prev = q('SELECT strategy_key FROM position_watch WHERE portfolio_id = ? AND listing_id = ?', [$p['id'], $lid])->fetch();
        $r = alert_apply_template($u, (int)$p['id'], $lid, $key, in_array($b['mode'] ?? 'add', ['sync', 'reset'], true) ? $b['mode'] : 'add', $dry);
        if ($dry) return $r;
        $sum = ($prev && $prev['strategy_key'] !== $key ? 'Changement vers « ' . $r['strategy_label'] . ' »' : ($prev ? 'Mise à jour de « ' . $r['strategy_label'] . ' »' : 'Surveillance « ' . $r['strategy_label'] .
            ' » activée')) . ' : ' . $r['added'] . ' ajoutée(s), ' . $r['updated'] . ' mise(s) à jour, ' . $r['kept'] . ' conservée(s), ' . $r['personal_kept'] . ' règle(s) personnelle(s) intacte(s).';
        q('INSERT INTO position_watch_log(portfolio_id, listing_id, from_key, to_key, summary, at) VALUES (?,?,?,?,?,?)', [$p['id'], $lid, $prev['strategy_key'] ?? null, $key, $sum, now_utc()]);
        q('INSERT INTO position_watch(portfolio_id, listing_id, strategy_key, model_version, updated_at) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE strategy_key = VALUES(strategy_key), model_version = VALUES(model_version), updated_at = VALUES(updated_at)',
            [$p['id'], $lid, $key, $r['model_version'] ?? null, now_utc()]);
        return $r;
    },
    // Stratégie d'origine d'un achat, renseignée à la main quand elle est inconnue (jamais inventée, jamais réécrite si déjà connue par l'achat).
    'alerts/origin' => function () {
        need_post(); $u = require_user(); $b = body();
        $t = q("SELECT t.id FROM portfolio_transactions t JOIN portfolios p ON p.id = t.portfolio_id WHERE t.id = ? AND p.user_id = ? AND t.side = 'buy'", [(int)($b['tx_id'] ?? 0), $u['id']])->fetch();
        if (!$t) throw new ApiError('Achat introuvable', 404);
        $key = (string)($b['strategy'] ?? ''); $all = alert_strategies($u); if (!isset($all[$key])) throw new ApiError('Stratégie inconnue', 422);
        $has = q('SELECT set_by FROM lot_origin WHERE transaction_id = ?', [$t['id']])->fetch();
        if ($has && $has['set_by'] === 'purchase') throw new ApiError('La stratégie d’origine enregistrée à l’achat ne se modifie pas', 409);
        q('INSERT INTO lot_origin(transaction_id, strategy_key, status, snapshot, set_by, created_at) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE strategy_key = VALUES(strategy_key), status = VALUES(status), snapshot = VALUES(snapshot)',
          [$t['id'], $key, $all[$key]['status'], json_encode($all[$key]['config'], JSON_UNESCAPED_UNICODE), 'manual', now_utc()]);
        return ['ok' => true];
    },
    'alerts/refresh' => function () {
        need_post(); require_user();
        return ['disabled' => true, 'rules' => 0, 'triggered' => 0];   // ancien moteur désactivé : aucune évaluation
    },
    'alerts/prefs' => function () {
        need_post(); $u = require_user(); $b = body(); $prefs = $u['prefs_json'] ? (json_decode($u['prefs_json'], true) ?: []) : [];
        foreach (['alert_email', 'alert_digest'] as $k) if (array_key_exists($k, $b)) $prefs[$k] = !empty($b[$k]);
        q('UPDATE users SET prefs_json = ? WHERE id = ?', [json_encode($prefs), $u['id']]); return ['prefs' => $prefs];
    },
];
