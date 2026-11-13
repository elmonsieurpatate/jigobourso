<?php
// Règles d'alerte par position : modèles de stratégie, import des anciens niveaux, historique. Aucune vente automatique.
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../lib/mail.php';
require_once __DIR__ . '/ct_strategies.php';

const ALERT_KINDS = ['price_below', 'price_above', 'target', 'gain_pct_above', 'loss_pct', 'gain_eur_above', 'loss_eur', 'drawdown_from_high', 'gain_giveback', 'daily_move', 'slope_min', 'r2_min', 'vol_max',
    'drawdown_max', 'momentum_min', 'ma_below', 'momentum6_min', 'momentum12_min', 'er_min', 'ma_falling', 'gap_ma20_max'];
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
    foreach (($st['strategies'] ?? []) as $s) $out[$s['id']] = ['key' => $s['id'], 'preset' => ALERT_PRESET[$s['id']] ?? null, 'label' => $s['label'], 'status' => $s['status'], 'config' => ($s['status'] === 'official' ?
        null : ($cfg[$s['id']] ?? null))];
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
      [$u['id'], $pid, $lid, $r['kind'], $r['granularity'] ?? null, $r['threshold'] ?? null, $source === 'strategy' ? ($r['threshold'] ?? null) : null, $r['severity'] ?? 'vigilance', $source, $strategy,
          array_key_exists('enabled', $r) && !$r['enabled'] ? 0 : 1, isset($r['why']) ? mb_substr((string)$r['why'], 0, 220) : null, $r['model_version'] ?? null, now_utc(), now_utc()]);
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
    return q("SELECT t.id AS transaction_id, o.strategy_key, o.status, o.set_by, t.trade_at FROM portfolio_transactions t LEFT JOIN lot_origin o ON o.transaction_id = t.id WHERE t.portfolio_id = ? AND t.listing_id = ? AND t.side = 'buy' ORDER BY t.trade_at",
        [$pid, $lid])->fetchAll();
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
    $plan = ['add' => [], 'update' => [], 'keep' => [], 'personal_kept' => (int)q("SELECT COUNT(*) c FROM alert_rules WHERE portfolio_id = ? AND listing_id = ? AND source <> 'strategy'", [$pid, $lid])->fetch()['c'],
        'strategy_label' => $s['label'], 'available' => 0];
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
        if ($custom && $mode === 'reset') { $plan['update'][] = ['id' => (int)$ex['id'], 'kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null, 'from' => (float)$ex['threshold'], 'to' => $r['threshold']];
            if (!$dry) q('UPDATE alert_rules SET threshold = ?, default_threshold = ?, why = ?, model_version = ?, updated_at = ? WHERE id = ?', [$r['threshold'], $r['threshold'], $r['why'] ?? null, $mv, now_utc(), $ex['id']]); }
        elseif ($custom) { $plan['keep'][] = ['id' => (int)$ex['id'], 'kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null, 'threshold' => (float)$ex['threshold'], 'strategy_threshold' => $r['threshold']];
            if (!$dry) q('UPDATE alert_rules SET default_threshold = ? WHERE id = ?', [$r['threshold'], $ex['id']]); }
        elseif (abs((float)$ex['threshold'] - round((float)$r['threshold'], 6)) > 2e-6 ) { $plan['update'][] = ['id' => (int)$ex['id'], 'kind' => $r['kind'], 'granularity' => $r['granularity'] ?? null,
            'from' => (float)$ex['threshold'], 'to' => $r['threshold']]; if (!$dry) q('UPDATE alert_rules SET threshold = ?, default_threshold = ?, why = ?, model_version = ?, updated_at = ? WHERE id = ?',
            [$r['threshold'], $r['threshold'], $r['why'] ?? null, $mv, now_utc(), $ex['id']]); }
    }
    return $plan + ['added' => count($plan['add']), 'updated' => count($plan['update']), 'kept' => count($plan['keep'])];
}

const ALERT_LABELS = ['price_below' => 'cours inférieur à', 'price_above' => 'cours supérieur à', 'target' => 'objectif de cours', 'gain_pct_above' => 'gain d’au moins (%)', 'loss_pct' => 'perte d’au moins (%)',
    'gain_eur_above' => 'gain d’au moins (€)', 'loss_eur' => 'perte d’au moins (€)', 'drawdown_from_high' => 'recul depuis le sommet (%)', 'gain_giveback' => 'gain rendu (points)', 'daily_move' => 'variation sur une séance (%)',
    'slope_min' => 'pente sous', 'r2_min' => 'R² sous', 'vol_max' => 'volatilité au-dessus de', 'drawdown_max' => 'recul maximal au-dessus de', 'momentum_min' => 'progression sous', 'ma_below' => 'cours sous la moyenne mobile',
    'momentum6_min' => 'momentum 6 mois (6−1) sous', 'momentum12_min' => 'momentum 12 mois (12−1) sous', 'er_min' => 'régularité sous', 'ma_falling' => 'moyenne mobile en baisse', 'gap_ma20_max' => 'écart à la moyenne 20 séances au-dessus de'];
