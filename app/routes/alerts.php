<?php
// Centre d'alertes : règles par position (héritées d'une stratégie ou personnelles), historique, stratégie d'origine des achats, stratégie de surveillance.
// Chaque requête est bornée à l'utilisateur connecté et à ses portefeuilles. Aucune vente automatique : une règle ne fait que signaler.
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/ct_strategies.php';
require_once __DIR__ . '/portfolios.php';

const ALERT_KINDS = ['price_below', 'price_above', 'target', 'gain_pct_above', 'loss_pct', 'gain_eur_above', 'loss_eur', 'drawdown_from_high', 'gain_giveback', 'daily_move', 'slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min', 'ma_below', 'momentum6_min', 'momentum12_min', 'er_min', 'ma_falling', 'gap_ma20_max'];
const ALERT_TREND = ['slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min', 'momentum6_min', 'momentum12_min', 'er_min'];
const ALERT_GRAN = ['day', 'week', 'month', 'quarter', 'half', 'year'];
// identifiants des stratégies de la page Classement -> modèles du moteur (mêmes sept stratégies)
const ALERT_PRESET = ['fast' => 'fast', 'regular' => 'regular', 'calm' => 'low_volatility', 'rebound' => 'recovery', 'mom6' => 'momentum', 'mom12' => 'momentum12', 'momrisk' => 'momentum_risk'];
const ALERT_SEV = ['info', 'vigilance', 'goal', 'sell'];

/** Stratégies du compte : clé stockée, libellé, statut (official / adapted / personal) et configuration utile aux modèles. */
function alert_strategies(array $u): array {
    $items = []; $cfg = [];
    foreach ((ct_all((int)$u['id'])['items'] ?? []) as $it) { $items[] = ['id' => $it['id'], 'name' => $it['name'] ?? $it['id'], 'builtin' => !empty($it['builtin']), 'config' => $it['config'] ?? null]; $cfg[$it['id']] = $it['config'] ?? null; }
    $st = engine_call('strategies-status', ['user_id' => (int)$u['id'], 'ct_items' => $items]);
    $out = [];
    foreach (($st['strategies'] ?? []) as $s) $out[$s['id']] = ['key' => $s['id'], 'preset' => ALERT_PRESET[$s['id']] ?? null, 'label' => $s['label'], 'status' => $s['status'], 'config' => ($s['status'] === 'official' ? null : ($cfg[$s['id']] ?? null))];
    return $out;
}
/** Libellé d'une stratégie à partir de son identifiant Classement ou de l'ancien nom de modèle d'un achat (low_volatility…). */
function alert_label(array $all, ?string $key): ?string {
    if ($key === null) return null;
    if (isset($all[$key])) return $all[$key]['label'];
    foreach ($all as $s) if (($s['preset'] ?? null) === $key) return $s['label'];
    return $key;
}
function alert_rule_view(array $r): array {
    foreach (['id', 'portfolio_id', 'listing_id', 'enabled'] as $k) $r[$k] = (int)$r[$k];
    foreach (['threshold', 'default_threshold', 'last_value'] as $k) $r[$k] = $r[$k] === null ? null : (float)$r[$k];
    unset($r['user_id']);
    return $r;
}
function alert_owned_rule(int $id, array $u): array {
    $r = q('SELECT * FROM alert_rules WHERE id = ? AND user_id = ?', [$id, $u['id']])->fetch();
    if (!$r) throw new ApiError('Alerte introuvable', 404);
    return $r;
}
function alert_event(int $rule, int $uid, string $ev, $val = null, $thr = null, ?string $msg = null): void {
    q('INSERT INTO alert_events(rule_id, user_id, at, event, value_obs, threshold, message) VALUES (?,?,?,?,?,?,?)', [$rule, $uid, now_utc(), $ev, $val, $thr, $msg]);
}
function alert_insert(array $u, int $pid, int $lid, array $r, string $source, ?string $strategy): int {
    q('INSERT INTO alert_rules(user_id, portfolio_id, listing_id, kind, granularity, threshold, default_threshold, severity, source, strategy_key, enabled, why, model_version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
      [$u['id'], $pid, $lid, $r['kind'], $r['granularity'] ?? null, $r['threshold'] ?? null, $source === 'strategy' ? ($r['threshold'] ?? null) : null, $r['severity'] ?? 'vigilance', $source, $strategy, array_key_exists('enabled', $r) && !$r['enabled'] ? 0 : 1, isset($r['why']) ? mb_substr((string)$r['why'], 0, 220) : null, $r['model_version'] ?? null, now_utc(), now_utc()]);
    return (int)db()->lastInsertId();
}
/** Reprend, sans rien supprimer, les filets de sécurité et objectifs déjà enregistrés : ils deviennent des règles d'alerte (la table d'origine reste intacte). */
function alert_import_legacy(array $u, int $pid): void {
    foreach (q('SELECT * FROM position_levels WHERE portfolio_id = ?', [$pid])->fetchAll() as $l) {
        foreach ([['stop_px', 'price_below', 'sell'], ['target_px', 'target', 'goal']] as [$col, $kind, $sev]) {
            if ($l[$col] === null) continue;
            $has = q("SELECT 1 FROM alert_rules WHERE portfolio_id = ? AND listing_id = ? AND source = 'legacy' AND kind = ?", [$pid, $l['listing_id'], $kind])->fetch();
            if (!$has) alert_insert($u, $pid, (int)$l['listing_id'], ['kind' => $kind, 'threshold' => (float)$l[$col], 'severity' => $sev], 'legacy', null);
        }
    }
}
function alert_origin_for(int $uid, int $pid, int $lid): array {
    return q("SELECT t.id AS transaction_id, o.strategy_key, o.status, o.set_by, t.trade_at FROM portfolio_transactions t LEFT JOIN lot_origin o ON o.transaction_id = t.id WHERE t.portfolio_id = ? AND t.listing_id = ? AND t.side = 'buy' ORDER BY t.trade_at", [$pid, $lid])->fetchAll();
}
/** Version du modèle d'alerte d'une stratégie : enregistre une nouvelle version publiée uniquement si les règles ont changé (empreinte différente). Jamais de modification d'une version publiée. */
function alert_model_version(string $key, array $tpl): int {
    $rules = array_map(fn($r) => ['kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null, 'threshold' => isset($r['threshold']) ? round((float)$r['threshold'], 6) : null, 'enabled' => !isset($r['enabled']) || $r['enabled'] ? 1 : 0], $tpl);
    $json = json_encode($rules, JSON_UNESCAPED_UNICODE); $dg = sha1($json);
    $last = q("SELECT version, digest FROM alert_models WHERE strategy_key = ? AND status = 'published' ORDER BY version DESC LIMIT 1", [$key])->fetch();
    if ($last && $last['digest'] === $dg) return (int)$last['version'];
    $v = $last ? (int)$last['version'] + 1 : 1;
    q("INSERT INTO alert_models(strategy_key, version, status, rules_json, digest, created_by, created_at) VALUES (?,?,'published',?,?,'system',?)", [$key, $v, $json, $dg, now_utc()]);
    return $v;
}
function alert_log_change(int $pid, int $lid, string $summary): void {
    $w = q('SELECT strategy_key FROM position_watch WHERE portfolio_id = ? AND listing_id = ?', [$pid, $lid])->fetch();
    q('INSERT INTO position_watch_log(portfolio_id, listing_id, from_key, to_key, summary, at) VALUES (?,?,?,?,?,?)', [$pid, $lid, $w['strategy_key'] ?? null, $w['strategy_key'] ?? 'personal', mb_substr($summary, 0, 300), now_utc()]);
}
function alert_apply_template(array $u, int $pid, int $lid, string $key, string $mode, bool $dry = false): array {
    $all = alert_strategies($u); $s = $all[$key] ?? null;
    if (!$s) throw new ApiError('Stratégie inconnue', 422);
    $hasCfg = isset($s['config']['periods']);
    $plan = ['add' => [], 'update' => [], 'keep' => [], 'personal_kept' => (int)q("SELECT COUNT(*) c FROM alert_rules WHERE portfolio_id = ? AND listing_id = ? AND source <> 'strategy'", [$pid, $lid])->fetch()['c'], 'strategy_label' => $s['label'], 'available' => 0];
    if (!$s['preset'] && !$hasCfg) return $plan + ['added' => 0, 'updated' => 0, 'kept' => 0];       // stratégie sans critères de tendance exploitables : aucune règle inventée
    $tpl = engine_call('watch-template', ['name' => $s['preset'] ?: 'regular', 'config' => $hasCfg ? $s['config'] : null])['rules'] ?? [];
    $plan['available'] = count($tpl);
    $mv = alert_model_version($key, $tpl); $plan['model_version'] = $mv;
    $plan['tpl'] = array_map(fn($r) => $r + ['enabled' => !isset($r['enabled']) || $r['enabled']], $tpl);
    foreach ($tpl as $r) {
        $r['model_version'] = $mv;
        $ex = q("SELECT * FROM alert_rules WHERE portfolio_id = ? AND listing_id = ? AND source = 'strategy' AND strategy_key = ? AND kind = ? AND granularity <=> ?", [$pid, $lid, $key, $r['kind'], $r['granularity'] ?? null])->fetch();
        if (!$ex) { $plan['add'][] = $r; if (!$dry) alert_insert($u, $pid, $lid, $r, 'strategy', $key); continue; }
        if (!in_array($mode, ['sync', 'reset'], true)) continue;
        $custom = $ex['threshold'] !== null && $ex['default_threshold'] !== null && abs((float)$ex['threshold'] - (float)$ex['default_threshold']) > 2e-6;
        if ($custom && $mode === 'reset') { $plan['update'][] = ['id' => (int)$ex['id'], 'kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null, 'from' => (float)$ex['threshold'], 'to' => $r['threshold']]; if (!$dry) q('UPDATE alert_rules SET threshold = ?, default_threshold = ?, why = ?, model_version = ?, updated_at = ? WHERE id = ?', [$r['threshold'], $r['threshold'], $r['why'] ?? null, $mv, now_utc(), $ex['id']]); }
        elseif ($custom) { $plan['keep'][] = ['id' => (int)$ex['id'], 'kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null, 'threshold' => (float)$ex['threshold'], 'strategy_threshold' => $r['threshold']]; if (!$dry) q('UPDATE alert_rules SET default_threshold = ? WHERE id = ?', [$r['threshold'], $ex['id']]); }
        elseif (abs((float)$ex['threshold'] - round((float)$r['threshold'], 6)) > 2e-6 ) { $plan['update'][] = ['id' => (int)$ex['id'], 'kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null, 'from' => (float)$ex['threshold'], 'to' => $r['threshold']]; if (!$dry) q('UPDATE alert_rules SET threshold = ?, default_threshold = ?, why = ?, model_version = ?, updated_at = ? WHERE id = ?', [$r['threshold'], $r['threshold'], $r['why'] ?? null, $mv, now_utc(), $ex['id']]); }
    }
    return $plan + ['added' => count($plan['add']), 'updated' => count($plan['update']), 'kept' => count($plan['keep'])];
}

/** Envoie un e-mail par utilisateur pour les alertes nouvellement déclenchées (une seule fois par déclenchement) ; appelé par le cron. Aucun ordre de vente, simple information. */
function alerts_mail_pending(): int {
    $sent = 0;
    $rows = q("SELECT r.*, u.email, u.username, u.prefs_json FROM alert_rules r JOIN users u ON u.id = r.user_id WHERE r.enabled = 1 AND r.state = 'triggered' AND r.acked_at IS NULL AND (r.notified_at IS NULL OR r.notified_at < r.triggered_at) AND u.email IS NOT NULL AND u.email <> ''")->fetchAll();
    $by = []; foreach ($rows as $r) $by[$r['user_id']][] = $r;
    foreach ($by as $uid => $list) {
        $prefs = $list[0]['prefs_json'] ? (json_decode($list[0]['prefs_json'], true) ?: []) : [];
        if (array_key_exists('alert_email', $prefs) && !$prefs['alert_email']) { foreach ($list as $r) q('UPDATE alert_rules SET notified_at = ? WHERE id = ?', [now_utc(), $r['id']]); continue; }
        $lines = [];
        foreach ($list as $r) { $l = q('SELECT symbol FROM listings WHERE id = ?', [$r['listing_id']])->fetch(); $lines[] = '• ' . ($l['symbol'] ?? '?') . ' : ' . (ALERT_LABELS[$r['kind']] ?? $r['kind']) . ' ' . rtrim(rtrim(number_format((float)$r['threshold'], 4, ',', ' '), '0'), ',') . ' (valeur observée ' . ($r['last_value'] === null ? 'indisponible' : rtrim(rtrim(number_format((float)$r['last_value'], 4, ',', ' '), '0'), ',')) . ')'; }
        $body = "Bonjour " . $list[0]['username'] . ",\n\nVos règles de surveillance ont détecté :\n" . implode("\n", $lines) . "\n\nCeci est une information, pas un ordre de vente. Consultez le centre d'alertes pour le détail et pour gérer ces règles.\n";
        try { if (send_account_mail($list[0]['email'], count($list) > 1 ? count($list) . ' alertes Jigobourso' : 'Alerte Jigobourso', $body)) { foreach ($list as $r) q('UPDATE alert_rules SET notified_at = ? WHERE id = ?', [now_utc(), $r['id']]); $sent++; } } catch (Throwable $e) { error_log('alerts mail: transport failure'); }
    }
    return $sent;
}
const ALERT_LABELS = ['price_below' => 'cours inférieur à', 'price_above' => 'cours supérieur à', 'target' => 'objectif de cours', 'gain_pct_above' => 'gain d’au moins (%)', 'loss_pct' => 'perte d’au moins (%)', 'gain_eur_above' => 'gain d’au moins (€)', 'loss_eur' => 'perte d’au moins (€)', 'drawdown_from_high' => 'recul depuis le sommet (%)', 'gain_giveback' => 'gain rendu (points)', 'daily_move' => 'variation sur une séance (%)', 'slope_min' => 'pente sous', 'r2_min' => 'R² sous', 'vol_max' => 'volatilité au-dessus de', 'drawdown_max' => 'recul maximal au-dessus de', 'momentum_min' => 'progression sous', 'ma_below' => 'cours sous la moyenne mobile', 'momentum6_min' => 'momentum 6 mois (6−1) sous', 'momentum12_min' => 'momentum 12 mois (12−1) sous', 'er_min' => 'régularité sous', 'ma_falling' => 'moyenne mobile en baisse', 'gap_ma20_max' => 'écart à la moyenne 20 séances au-dessus de'];

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
        $watch = []; $wmv = []; foreach (q('SELECT listing_id, strategy_key, model_version FROM position_watch WHERE portfolio_id = ?', [$p['id']])->fetchAll() as $w) { $watch[(int)$w['listing_id']] = $w['strategy_key']; $wmv[(int)$w['listing_id']] = $w['model_version'] === null ? null : (int)$w['model_version']; }
        $latest = []; foreach (q("SELECT strategy_key, MAX(version) v FROM alert_models WHERE status = 'published' GROUP BY strategy_key")->fetchAll() as $m) $latest[$m['strategy_key']] = (int)$m['v'];
        foreach ($val['positions'] as $x) {
            if (!$x['listing_id'] || $x['qty'] <= 0) continue;
            $lid = (int)$x['listing_id'];
            $origins = array_map(fn($o) => ['tx' => (int)$o['transaction_id'], 'date' => $o['trade_at'], 'strategy' => $o['strategy_key'], 'label' => alert_label($strategies, $o['strategy_key']), 'status' => $o['status'], 'by' => $o['set_by']], alert_origin_for((int)$u['id'], (int)$p['id'], $lid));
            $legacyLot = q("SELECT s.strategy, t.id FROM lot_settings s JOIN portfolio_transactions t ON t.id = s.transaction_id WHERE t.portfolio_id = ? AND t.listing_id = ? AND s.strategy IS NOT NULL", [$p['id'], $lid])->fetchAll();
            $pos[] = ['listing_id' => $lid, 'symbol' => $x['symbol'], 'name' => $x['name'], 'kind' => $x['kind'] ?? null, 'price' => $x['price'] ?? null, 'currency' => $x['price_currency'] ?? $x['currency'], 'value' => $x['value'] ?? null,
                      'origins' => $origins, 'lot_strategies' => array_map(fn($l) => ['tx' => (int)$l['id'], 'strategy' => $l['strategy'], 'label' => alert_label($strategies, $l['strategy'])], $legacyLot),
                      'watch' => isset($watch[$lid]) ? ['key' => $watch[$lid], 'label' => $strategies[$watch[$lid]]['label'] ?? $watch[$lid], 'status' => $strategies[$watch[$lid]]['status'] ?? null, 'model_version' => $wmv[$lid] ?? null, 'model_latest' => $latest[$watch[$lid]] ?? null] : null,
                      'rules' => count($by[$lid] ?? []),
                      'watch_log' => q('SELECT at, summary FROM position_watch_log WHERE portfolio_id = ? AND listing_id = ? ORDER BY at DESC, id DESC LIMIT 6', [$p['id'], $lid])->fetchAll()];
        }
        $events = q('SELECT e.*, r.kind, r.listing_id FROM alert_events e JOIN alert_rules r ON r.id = e.rule_id WHERE e.user_id = ? AND r.portfolio_id = ? ORDER BY e.at DESC, e.id DESC LIMIT 80', [$u['id'], $p['id']])->fetchAll();
        $c = ['active' => 0, 'triggered' => 0, 'todo' => 0, 'insufficient' => 0];
        foreach ($rules as $r) { if (!(int)$r['enabled']) continue; $c['active']++; if ($r['state'] === 'triggered' && $r['acked_at'] === null) $c['triggered']++; if (in_array($r['state'], ['insufficient', 'error'], true) || $r['state'] === null) $c['insufficient']++; }
        $held = array_column($pos, 'listing_id'); foreach ($pos as $x) if (!$x['rules']) $c['todo']++;
        $prefs = $u['prefs_json'] ? (json_decode($u['prefs_json'], true) ?: []) : [];
        return ['portfolio' => ['id' => (int)$p['id'], 'name' => $p['name']], 'portfolios' => q('SELECT id, name FROM portfolios WHERE user_id = ? ORDER BY is_default DESC, id', [$u['id']])->fetchAll(), 'positions' => $pos, 'rules' => array_map('alert_rule_view', $rules),
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
            if (abs((float)$r['threshold'] - (float)$thr) > 2e-6) alert_log_change((int)$r['portfolio_id'], (int)$r['listing_id'], 'Seuil modifié : ' . (ALERT_LABELS[$r['kind']] ?? $r['kind']) . ' ' . rtrim(rtrim(number_format((float)$r['threshold'], 4, ',', ''), '0'), ',') . ' → ' . rtrim(rtrim(number_format((float)$thr, 4, ',', ''), '0'), ',') . '.');
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
        q('UPDATE alert_rules SET threshold = ?, updated_at = ? WHERE id = ?', [$r['default_threshold'], now_utc(), $r['id']]); alert_log_change((int)$r['portfolio_id'], (int)$r['listing_id'], 'Seuil du modèle restauré : ' . (ALERT_LABELS[$r['kind']] ?? $r['kind']) . '.'); return ['ok' => true];
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
        $sum = ($prev && $prev['strategy_key'] !== $key ? 'Changement vers « ' . $r['strategy_label'] . ' »' : ($prev ? 'Mise à jour de « ' . $r['strategy_label'] . ' »' : 'Surveillance « ' . $r['strategy_label'] . ' » activée')) . ' : ' . $r['added'] . ' ajoutée(s), ' . $r['updated'] . ' mise(s) à jour, ' . $r['kept'] . ' conservée(s), ' . $r['personal_kept'] . ' règle(s) personnelle(s) intacte(s).';
        q('INSERT INTO position_watch_log(portfolio_id, listing_id, from_key, to_key, summary, at) VALUES (?,?,?,?,?,?)', [$p['id'], $lid, $prev['strategy_key'] ?? null, $key, $sum, now_utc()]);
        q('INSERT INTO position_watch(portfolio_id, listing_id, strategy_key, model_version, updated_at) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE strategy_key = VALUES(strategy_key), model_version = VALUES(model_version), updated_at = VALUES(updated_at)', [$p['id'], $lid, $key, $r['model_version'] ?? null, now_utc()]);
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
        need_post(); $u = require_user();
        return engine_call('watch-run', ['user_id' => (int)$u['id']]);
    },
    'alerts/prefs' => function () {
        need_post(); $u = require_user(); $b = body(); $prefs = $u['prefs_json'] ? (json_decode($u['prefs_json'], true) ?: []) : [];
        foreach (['alert_email', 'alert_digest'] as $k) if (array_key_exists($k, $b)) $prefs[$k] = !empty($b[$k]);
        q('UPDATE users SET prefs_json = ? WHERE id = ?', [json_encode($prefs), $u['id']]); return ['prefs' => $prefs];
    },
];
