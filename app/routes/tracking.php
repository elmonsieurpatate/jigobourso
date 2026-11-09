<?php
// Plan de suivi des positions : tendance, risque, protection indicative et conseil (moteur : engine/analytics/position_plan.py).
// Lecture seule pour les données financières : rien n'est vendu, aucun niveau personnel n'est modifié, aucune transaction n'est touchée.
// Seule écriture : la stratégie de surveillance d'une position (table position_watch, déjà existante) à la demande explicite de l'utilisateur.
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/engine.php';
require_once __DIR__ . '/../services/transactions.php';
require_once __DIR__ . '/../services/ct_strategies.php';
require_once __DIR__ . '/portfolios.php';

// identifiants de la page Classement -> modèles du moteur (mêmes sept stratégies)
const TRACK_PRESET = ['fast' => 'fast', 'regular' => 'regular', 'calm' => 'low_volatility', 'rebound' => 'recovery', 'mom6' => 'momentum', 'mom12' => 'momentum12', 'momrisk' => 'momentum_risk'];
const TRACK_LABEL = ['fast' => 'Croissance rapide', 'regular' => 'Croissance régulière', 'calm' => 'Hausse calme', 'rebound' => 'Rebond', 'mom6' => 'Momentum 6 mois', 'mom12' => 'Momentum 12 mois', 'momrisk' => 'Momentum ajusté au risque'];

function track_custom_names(int $uid): array {
    $out = [];
    foreach ((ct_all($uid)['items'] ?? []) as $it) if (empty($it['builtin'])) $out[$it['id']] = $it['name'] ?? $it['id'];
    return $out;
}
function track_label(string $key, array $custom): string { return TRACK_LABEL[$key] ?? ($custom[$key] ?? $key); }

return [
    'tracking/state' => function () {
        $u = require_user();
        $pid = (int)($_GET['portfolio'] ?? 0);
        $p = $pid ? own_portfolio($pid, $u) : (q('SELECT * FROM portfolios WHERE user_id = ? ORDER BY is_default DESC, id LIMIT 1', [$u['id']])->fetch() ?: null);
        if (!$p) return ['portfolio' => null, 'positions' => (object)[], 'strategies' => []];
        $val = portfolio_valuation((int)$p['id']);
        $custom = track_custom_names((int)$u['id']);
        $watch = []; foreach (q('SELECT listing_id, strategy_key FROM position_watch WHERE portfolio_id = ?', [$p['id']])->fetchAll() as $w) $watch[(int)$w['listing_id']] = $w['strategy_key'];
        $levels = []; foreach (q('SELECT listing_id, stop_px, target_px FROM position_levels WHERE portfolio_id = ?', [$p['id']])->fetchAll() as $l) $levels[(int)$l['listing_id']] = $l;
        $origin = []; foreach (q("SELECT t.id, o.strategy_key FROM portfolio_transactions t LEFT JOIN lot_origin o ON o.transaction_id = t.id WHERE t.portfolio_id = ? AND t.side = 'buy'", [$p['id']])->fetchAll() as $o) $origin[(int)$o['id']] = $o['strategy_key'];
        // Date d'ouverture = achat le plus ancien encore détenu (FIFO) ; origines = stratégies d'origine des achats encore détenus (information historique, jamais modifiée ici).
        $openDate = []; $origins = [];
        foreach (open_lots(q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ?', [$p['id']])->fetchAll()) as $l) {
            $lid = (int)($l['tx']['listing_id'] ?? 0); if (!$lid) continue;
            $d = substr($l['tx']['trade_at'], 0, 10);
            if (!isset($openDate[$lid]) || $d < $openDate[$lid]) $openDate[$lid] = $d;
            $origins[$lid][] = ['tx' => (int)$l['tx']['id'], 'date' => $d, 'remaining' => (float)$l['remaining'], 'strategy' => $origin[(int)$l['tx']['id']] ?? null, 'label' => isset($origin[(int)$l['tx']['id']]) ? track_label($origin[(int)$l['tx']['id']], $custom) : null];
        }
        $req = []; $held = [];
        foreach ($val['positions'] as $x) {
            if (!$x['listing_id'] || $x['qty'] <= 0) continue;
            $lid = (int)$x['listing_id']; $key = $watch[$lid] ?? null;
            $held[$lid] = $x;
            $req[] = ['listing_id' => $lid, 'kind' => $x['kind'] ?? null, 'qty' => (float)$x['qty'], 'avg_cost' => $x['avg_cost'] !== null ? (float)$x['avg_cost'] : null, 'price' => $x['price'] !== null ? (float)$x['price'] : null,
                      'price_eur' => $x['price_eur'] !== null ? (float)$x['price_eur'] : null, 'currency' => $x['price_currency'] ?? $x['currency'], 'open_date' => $openDate[$lid] ?? null,
                      'stop_px' => isset($levels[$lid]) && $levels[$lid]['stop_px'] !== null ? (float)$levels[$lid]['stop_px'] : null,
                      'watch_key' => $key !== null ? (TRACK_PRESET[$key] ?? null) : null, 'watch_label' => $key !== null && !isset(TRACK_PRESET[$key]) ? track_label($key, $custom) : null];
        }
        $plans = $req ? engine_call('position-plan', ['positions' => $req])['positions'] : [];
        $out = [];
        foreach ($req as $r) {
            $lid = $r['listing_id']; $key = $watch[$lid] ?? null; $x = $held[$lid];
            $out[(string)$lid] = ($plans[(string)$lid] ?? ['status' => 'unavailable']) + [
                'listing_id' => $lid, 'symbol' => $x['symbol'], 'name' => $x['name_catalogue'] ?? $x['name'], 'kind' => $x['kind'] ?? null, 'qty' => (float)$x['qty'], 'open_date' => $openDate[$lid] ?? null,
                'watch' => $key !== null ? ['key' => $key, 'label' => track_label($key, $custom)] : null, 'origins' => $origins[$lid] ?? [],
                'personal' => ['stop' => ($levels[$lid]['stop_px'] ?? null) !== null ? (float)$levels[$lid]['stop_px'] : null, 'target' => ($levels[$lid]['target_px'] ?? null) !== null ? (float)$levels[$lid]['target_px'] : null, 'currency' => $r['currency']]];
        }
        $opts = []; foreach (TRACK_LABEL as $k => $l) $opts[] = ['key' => $k, 'label' => $l, 'custom' => false];
        foreach ($custom as $k => $l) $opts[] = ['key' => $k, 'label' => $l, 'custom' => true];
        return ['portfolio' => ['id' => (int)$p['id'], 'name' => $p['name']], 'positions' => (object)$out, 'strategies' => $opts, 'model' => 1];
    },
    // Change la stratégie de surveillance d'UNE position (jamais les achats, leurs stratégies d'origine, ni les protections personnelles).
    'tracking/strategy' => function () {
        need_post(); $u = require_user(); $b = body();
        $p = own_portfolio((int)($b['portfolio_id'] ?? 0), $u); $lid = (int)($b['listing_id'] ?? 0);
        if (!q('SELECT 1 FROM portfolio_transactions WHERE portfolio_id = ? AND listing_id = ?', [$p['id'], $lid])->fetch()) throw new ApiError('Ce titre n’est pas dans ce portefeuille', 404);
        $custom = track_custom_names((int)$u['id']);
        $key = $b['strategy'] ?? null; $key = ($key === null || $key === '') ? null : (string)$key;
        if ($key !== null && !isset(TRACK_LABEL[$key]) && !isset($custom[$key])) throw new ApiError('Stratégie inconnue', 422);
        $old = q('SELECT strategy_key FROM position_watch WHERE portfolio_id = ? AND listing_id = ?', [$p['id'], $lid])->fetchColumn();
        $old = $old === false ? null : $old;
        if ($old === $key) return ['ok' => true, 'unchanged' => true];
        if ($key === null) q('DELETE FROM position_watch WHERE portfolio_id = ? AND listing_id = ?', [$p['id'], $lid]);
        else q('INSERT INTO position_watch(portfolio_id, listing_id, strategy_key, model_version, updated_at) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE strategy_key = VALUES(strategy_key), model_version = NULL, updated_at = VALUES(updated_at)', [$p['id'], $lid, $key, null, now_utc()]);
        q('INSERT INTO position_watch_log(portfolio_id, listing_id, from_key, to_key, summary, at) VALUES (?,?,?,?,?,?)',
          [$p['id'], $lid, $old, $key ?? 'none', mb_substr('Stratégie de surveillance : ' . ($old ? track_label($old, $custom) : 'aucune') . ' → ' . ($key ? track_label($key, $custom) : 'aucune'), 0, 300), now_utc()]);
        return ['ok' => true];
    },
];
