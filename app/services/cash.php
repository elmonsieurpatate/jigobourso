<?php
// Liquidités d'un portefeuille (modèle « cash »). Règles uniques, utilisées par toutes les écritures (transactions, mouvements, conversion) :
//  - le solde n'est JAMAIS stocké : il se déduit des mouvements d'argent et des transactions (achat = débit frais compris, vente = crédit net de frais) ;
//  - dépôts, retraits et capital initial sont des apports externes, jamais un gain ni une perte ; dividendes = gain ; frais de compte = perte ;
//  - virtuel : le solde ne descend jamais sous zéro (pas de marge) ; réel : un solde négatif est toléré et signalé, mais un retrait ne peut pas le creuser ;
//  - ordre à horodatage égal : capital et dépôts, puis ventes, puis achats, puis frais, puis retraits (résultat déterministe, jamais dépendant de l'ordre de saisie).
// Un portefeuille « legacy » (tous ceux d'avant la migration) n'a aucune liquidité : rien ici ne s'applique tant qu'il n'est pas converti explicitement.
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/portfolio_access.php';
require_once __DIR__ . '/ledger.php';
require_once __DIR__ . '/transactions.php';

const CASH_EPS = 0.005;                       // un demi-centime : en dessous, un solde est considéré nul (arrondis des quantités fractionnaires)
const CASH_ALL_HISTORY = '1970-01-01 00:00:00';
const CASH_KINDS = ['deposit', 'withdrawal', 'dividend', 'fee'];   // saisissables ; initial_capital n'est créé que par la création, la réinitialisation et la conversion
const CASH_PRIORITY = ['initial_capital' => 0, 'deposit' => 1, 'dividend' => 1, 'sell' => 2, 'buy' => 3, 'fee' => 4, 'withdrawal' => 5];

function cash_load_movements(int $portfolioId, bool $lock = false): array {
    return q('SELECT * FROM portfolio_cash_movements WHERE portfolio_id = ? ORDER BY occurred_at, id' . ($lock ? ' FOR UPDATE' : ''), [$portfolioId])->fetchAll();
}

// Effet d'une transaction sur les liquidités, en euros ; null = taux de change inconnu (jamais deviné).
function cash_tx_delta(array $t): ?float {
    $fx = $t['fx_to_eur'] !== null ? (float)$t['fx_to_eur'] : (($t['currency'] ?? '') === 'EUR' ? 1.0 : null);
    if ($fx === null || $fx <= 0) return null;
    $gross = (float)$t['quantity'] * (float)$t['unit_price'] * $fx;
    $fees = (float)($t['fees'] ?? 0);
    return $t['side'] === 'buy' ? -($gross + $fees) : $gross - $fees;
}

function cash_mov_delta(array $m): float {
    $eur = (float)$m['amount_net'] * (float)$m['fx_to_eur'];
    return in_array($m['kind'], ['withdrawal', 'fee'], true) ? -$eur : $eur;
}

// Événements chronologiques qui agissent sur les liquidités. Les transactions antérieures à cash_from (période « ancien modèle ») n'en font pas partie.
function cash_events(array $pf, array $transactions, array $movements): array {
    $ev = [];
    $from = $pf['cash_from'] ?? null;
    if ($from !== null) {
        foreach ($transactions as $t) {
            if ($t['trade_at'] < $from) continue;
            $ev[] = ['at' => $t['trade_at'], 'prio' => CASH_PRIORITY[$t['side']], 'src' => 1, 'id' => (int)$t['id'], 'kind' => $t['side'], 'delta' => cash_tx_delta($t),
                     'label' => ($t['side'] === 'buy' ? 'achat ' : 'vente ') . ($t['symbol'] ?? '')];
        }
    }
    foreach ($movements as $m) {
        $ev[] = ['at' => $m['occurred_at'], 'prio' => CASH_PRIORITY[$m['kind']], 'src' => 0, 'id' => (int)($m['id'] ?? 0), 'kind' => $m['kind'], 'delta' => cash_mov_delta($m),
                 'label' => ['initial_capital' => 'capital initial', 'deposit' => 'dépôt', 'withdrawal' => 'retrait', 'dividend' => 'dividende', 'fee' => 'frais'][$m['kind']]];
    }
    usort($ev, function ($a, $b) { return [$a['at'], $a['prio'], $a['src'], $a['id']] <=> [$b['at'], $b['prio'], $b['src'], $b['id']]; });
    return $ev;
}

// Solde après chaque événement. Renvoie ['events' => [... + balance], 'balance', 'min' => ['balance','at','label']|null, 'unknown_fx' => [ids de transactions]].
function cash_timeline(array $events): array {
    $bal = 0.0; $min = null; $unknown = [];
    foreach ($events as &$e) {
        if ($e['delta'] === null) { $unknown[] = $e['id']; $e['balance'] = round($bal, 2); continue; }
        $bal += $e['delta'];
        $e['balance'] = round($bal, 2);
        if ($min === null || $bal < $min['balance']) $min = ['balance' => round($bal, 2), 'at' => $e['at'], 'label' => $e['label']];
    }
    unset($e);
    return ['events' => $events, 'balance' => round($bal, 2), 'min' => $min, 'unknown_fx' => $unknown];
}

// Refuse l'historique qui violerait les règles de liquidités. Lève ApiError 422 avec la date et le manque en euros.
function cash_validate(array $pf, array $transactions, array $movements): void {
    if (($pf['cash_model'] ?? 'legacy') !== 'cash') return;
    $tl = cash_timeline(cash_events($pf, $transactions, $movements));
    if ($tl['unknown_fx']) throw new ApiError('Taux de change manquant pour la transaction n° ' . $tl['unknown_fx'][0] . ' : les liquidités ne peuvent pas être calculées', 422);
    $virtual = ($pf['kind'] ?? null) === 'virtual';
    foreach ($tl['events'] as $e) {
        if ($e['balance'] >= -CASH_EPS) continue;
        if ($virtual || $e['kind'] === 'withdrawal')
            throw new ApiError(sprintf('Liquidités insuffisantes au %s (%s) : il manque %s €', substr($e['at'], 0, 16), $e['label'], number_format(-$e['balance'], 2, ',', ' ')), 422);
    }
}

// Résumé affiché (liste, détail, bilan) ; null pour un portefeuille legacy.
function cash_summary(array $pf, ?array $transactions = null, ?array $movements = null): ?array {
    if (($pf['cash_model'] ?? 'legacy') !== 'cash') return null;
    $transactions = $transactions ?? q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ?', [$pf['id']])->fetchAll();
    $movements = $movements ?? cash_load_movements((int)$pf['id']);
    $tl = cash_timeline(cash_events($pf, $transactions, $movements));
    return ['model' => 'cash', 'kind' => $pf['kind'], 'balance' => $tl['balance'], 'negative' => $tl['min'] !== null && $tl['min']['balance'] < -CASH_EPS,
            'min' => $tl['min'], 'movements' => count($movements), 'from' => $pf['cash_from'], 'converted_at' => $pf['cash_converted_at'] ?? null,
            'unknown_fx' => $tl['unknown_fx']];
}

// ───────── saisie d'un mouvement ─────────
// Date sans heure : un dépôt vaut début de journée, un retrait fin de journée, le reste midi (comme les transactions). Une heure explicite est toujours respectée.
function cash_when(string $when, string $kind): string {
    if (!preg_match('/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/', $when)) throw new ApiError('Date invalide', 422);
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', substr($when, 0, 10), new DateTimeZone('UTC'));
    if (!$date || $date->format('Y-m-d') !== substr($when, 0, 10)) throw new ApiError('Date invalide', 422);
    $time = strlen($when) <= 10 ? (in_array($kind, ['deposit', 'initial_capital'], true) ? ' 00:00:00' : ($kind === 'withdrawal' ? ' 23:59:59' : ' 12:00:00')) : '';
    $ts = strtotime($when . $time . ' UTC');
    if ($ts === false || $ts > time() + 86400) throw new ApiError('Date invalide', 422);
    return gmdate('Y-m-d H:i:s', $ts);
}

function cash_fields(array $b, ?array $old = null): array {
    $kind = $old ? $old['kind'] : str_in($b, 'kind', 16);
    if (!$old && !in_array($kind, CASH_KINDS, true)) throw new ApiError('Type de mouvement invalide (dépôt, retrait, dividende ou frais)', 422);
    $amount = num_in($b, 'amount', true, 0.00000001);
    $currency = price_unit($b['currency'] ?? 'EUR') ?? 'EUR';
    if ($currency !== 'EUR' && $kind !== 'dividend') throw new ApiError('Dépôts, retraits et frais sont saisis en euros', 422);
    $when = cash_when(str_in($b, 'occurred_at', 25), $kind);
    $fx = historical_fx($currency, $when, num_in($b, 'fx_to_eur', false, 0));
    $gross = $kind === 'dividend' ? num_in($b, 'gross_amount', false, 0) : null;
    $tax = $kind === 'dividend' ? num_in($b, 'withholding_tax', false, 0) : null;
    $listing = null;
    if ($kind === 'dividend' && !empty($b['listing_id'])) {
        if (!q('SELECT 1 FROM listings WHERE id = ?', [(int)$b['listing_id']])->fetch()) throw new ApiError('Titre introuvable', 404);
        $listing = (int)$b['listing_id'];
    }
    return ['kind' => $kind, 'amount_net' => $amount, 'currency' => $currency, 'fx_to_eur' => $fx, 'gross_amount' => $gross, 'withholding_tax' => $tax,
            'listing_id' => $listing, 'occurred_at' => $when, 'note' => str_in($b, 'note', 500, false) ?: null];
}

function cash_insert(int $portfolioId, array $f, string $source = 'manual', ?string $now = null): int {
    $now = $now ?? now_utc();
    q('INSERT INTO portfolio_cash_movements(portfolio_id, kind, amount_net, currency, fx_to_eur, gross_amount, withholding_tax, listing_id, occurred_at, note, source, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
      [$portfolioId, $f['kind'], $f['amount_net'], $f['currency'], $f['fx_to_eur'], $f['gross_amount'] ?? null, $f['withholding_tax'] ?? null, $f['listing_id'] ?? null, $f['occurred_at'], $f['note'] ?? null, $source, $now, $now]);
    return (int)db()->lastInsertId();
}

function cash_audit(int $portfolioId, ?int $movementId, string $action, $before, $after): void {
    q('INSERT INTO portfolio_cash_audit(portfolio_id, movement_id, action, before_json, after_json, at) VALUES (?,?,?,?,?,?)',
      [$portfolioId, $movementId, $action, $before === null ? null : json_encode($before, JSON_UNESCAPED_UNICODE), $after === null ? null : json_encode($after, JSON_UNESCAPED_UNICODE), now_utc()]);
}

function cash_require_model(array $pf): void {
    if ($pf['cash_model'] !== 'cash') throw new ApiError('Ce portefeuille n’a pas de liquidités : convertissez-le d’abord (aperçu avant validation)', 409);
}

function own_cash_movement(int $id, array $user): array {
    $m = q('SELECT m.* FROM portfolio_cash_movements m JOIN portfolios p ON p.id = m.portfolio_id WHERE m.id = ? AND p.user_id = ?', [$id, $user['id']])->fetch();
    if (!$m) throw new ApiError('Mouvement introuvable', 404);
    return $m;
}

function cash_add(array $u, array $b = []) {
    $p = own_portfolio((int)($b['portfolio_id'] ?? 0), $u);
    cash_require_model($p);
    $f = cash_fields($b);
    return write_transaction((int)$u['id'], (int)$p['id'], function ($rows, $pf) use ($f) {
        cash_require_model($pf);
        return ['id' => cash_insert((int)$pf['id'], $f)];
    });
}

function cash_update(array $u, array $b = []) {
    $m = own_cash_movement((int)($b['id'] ?? 0), $u);
    $f = cash_fields($b, $m);   // le type d'un mouvement existant ne change pas : on supprime et on recrée plutôt que de réinterpréter un dépôt en retrait
    return write_transaction((int)$u['id'], (int)$m['portfolio_id'], function ($rows, $pf) use ($m, $f) {
        $old = q('SELECT * FROM portfolio_cash_movements WHERE id = ? AND portfolio_id = ? FOR UPDATE', [$m['id'], $pf['id']])->fetch();
        if (!$old) throw new ApiError('Mouvement introuvable', 404);
        q('UPDATE portfolio_cash_movements SET amount_net = ?, currency = ?, fx_to_eur = ?, gross_amount = ?, withholding_tax = ?, listing_id = ?, occurred_at = ?, note = ?, updated_at = ? WHERE id = ?',
          [$f['amount_net'], $f['currency'], $f['fx_to_eur'], $f['gross_amount'], $f['withholding_tax'], $f['listing_id'], $f['occurred_at'], $f['note'], now_utc(), $old['id']]);
        cash_audit((int)$pf['id'], (int)$old['id'], 'edit', $old, $f);
        return ['ok' => true];
    });
}

function cash_delete(array $u, array $b = []) {
    $m = own_cash_movement((int)($b['id'] ?? 0), $u);
    return write_transaction((int)$u['id'], (int)$m['portfolio_id'], function ($rows, $pf) use ($m) {
        $old = q('SELECT * FROM portfolio_cash_movements WHERE id = ? AND portfolio_id = ? FOR UPDATE', [$m['id'], $pf['id']])->fetch();
        if (!$old) throw new ApiError('Mouvement introuvable', 404);
        q('DELETE FROM portfolio_cash_movements WHERE id = ?', [$old['id']]);
        cash_audit((int)$pf['id'], (int)$old['id'], 'remove', $old, null);
        return ['ok' => true];
    });
}

// Mouvements, soldes successifs et corrections d'un portefeuille.
function cash_list(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    if ($p['cash_model'] !== 'cash') return ['cash' => null, 'movements' => [], 'audit' => []];
    $tx = q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ?', [$p['id']])->fetchAll();
    $mov = cash_load_movements((int)$p['id']);
    $tl = cash_timeline(cash_events($p, $tx, $mov));
    $after = [];
    foreach ($tl['events'] as $e) if ($e['src'] === 0) $after[$e['id']] = $e['balance'];
    $rows = array_map(function ($m) use ($after) { return $m + ['balance_after' => $after[(int)$m['id']] ?? null]; }, array_reverse($mov));
    $audit = q('SELECT id, movement_id, action, before_json, after_json, at FROM portfolio_cash_audit WHERE portfolio_id = ? ORDER BY id DESC LIMIT 50', [$p['id']])->fetchAll();
    return ['cash' => cash_summary($p, $tx, $mov), 'movements' => $rows, 'audit' => $audit];
}

// ───────── conversion explicite legacy → cash ─────────
// Plan validé à partir de la saisie ; aucune écriture. Deux voies :
//  from_date : les liquidités démarrent à une date avec un solde d'ouverture déclaré (0 = non renseigné) ; les opérations antérieures gardent l'ancien calcul.
//  full      : tout l'historique est rejoué ; les dépôts passés sont déclarés par l'utilisateur, rien n'est inventé.
function cash_convert_plan(array $b): array {
    $kind = str_in($b, 'kind', 8);
    if (!in_array($kind, ['virtual', 'real'], true)) throw new ApiError('Type invalide (virtual ou real)', 422);
    $mode = str_in($b, 'mode', 12);
    $movements = [];
    if ($mode === 'from_date') {
        $date = str_in($b, 'date', 10);
        $when = cash_when($date, 'deposit');
        if (strlen($date) !== 10) throw new ApiError('Date invalide', 422);
        $opening = num_in($b, 'opening_balance', false, 0) ?? 0.0;
        if ($opening > 0) $movements[] = ['kind' => 'deposit', 'amount_net' => $opening, 'currency' => 'EUR', 'fx_to_eur' => 1.0, 'occurred_at' => $when, 'note' => 'Solde d’ouverture déclaré à la conversion'];
        return ['mode' => $mode, 'kind' => $kind, 'cash_from' => $when, 'movements' => $movements, 'opening_declared' => $opening > 0];
    }
    if ($mode !== 'full') throw new ApiError('Mode de conversion invalide (from_date ou full)', 422);
    $deposits = $b['deposits'] ?? [];
    if (!is_array($deposits) || count($deposits) > 100) throw new ApiError('Liste de dépôts invalide (100 maximum)', 422);
    foreach ($deposits as $d) {
        if (!is_array($d)) throw new ApiError('Dépôt invalide', 422);
        $movements[] = ['kind' => 'deposit', 'amount_net' => num_in($d, 'amount', true, 0.00000001), 'currency' => 'EUR', 'fx_to_eur' => 1.0,
                        'occurred_at' => cash_when(str_in($d, 'date', 25), 'deposit'), 'note' => str_in($d, 'note', 500, false) ?: 'Dépôt déclaré à la conversion'];
    }
    return ['mode' => $mode, 'kind' => $kind, 'cash_from' => CASH_ALL_HISTORY, 'movements' => $movements, 'opening_declared' => count($movements) > 0];
}

function cash_duplicates(array $rows): array {
    $seen = []; $out = [];
    foreach ($rows as $t) {
        $k = implode('|', [transaction_key($t), $t['side'], (float)$t['quantity'], (float)$t['unit_price'], $t['trade_at']]);
        if (isset($seen[$k])) $out[] = ['ids' => [$seen[$k], (int)$t['id']], 'symbol' => $t['symbol'], 'side' => $t['side'], 'quantity' => (float)$t['quantity'], 'unit_price' => (float)$t['unit_price'], 'trade_at' => $t['trade_at']];
        else $seen[$k] = (int)$t['id'];
    }
    return $out;
}

function cash_plan_hash(array $plan, array $rows): string {
    $keys = array_map(function ($t) { return [(int)$t['id'], $t['side'], (string)$t['quantity'], (string)$t['unit_price'], (string)$t['fx_to_eur'], (string)$t['fees'], $t['trade_at']]; }, $rows);
    return sha1(json_encode([$plan, $keys]));
}

function cash_convert_preview(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    if ($p['cash_model'] !== 'legacy') throw new ApiError('Ce portefeuille a déjà des liquidités', 409);
    $plan = cash_convert_plan($b);
    $rows = q('SELECT * FROM portfolio_transactions WHERE portfolio_id = ? ORDER BY trade_at, id', [$p['id']])->fetchAll();
    $sim = array_merge($p, ['cash_model' => 'cash', 'kind' => $plan['kind'], 'cash_from' => $plan['cash_from']]);
    $tl = cash_timeline(cash_events($sim, $rows, $plan['movements']));
    $before = array_filter($rows, function ($t) use ($plan) { return $t['trade_at'] < $plan['cash_from']; });
    $negatives = [];
    foreach ($tl['events'] as $e) if ($e['balance'] < -CASH_EPS && count($negatives) < 20) $negatives[] = ['at' => $e['at'], 'label' => $e['label'], 'balance' => $e['balance']];
    $min = $tl['min'];
    $warnings = [];
    if ($tl['unknown_fx']) $warnings[] = 'Transactions sans taux de change (n° ' . implode(', ', $tl['unknown_fx']) . ') : conversion impossible tant qu’elles ne sont pas corrigées.';
    if (!$plan['opening_declared']) $warnings[] = 'Aucune liquidité déclarée : le solde de départ est considéré comme nul (non renseigné).';
    if ($before) $warnings[] = count($before) . ' opération(s) antérieure(s) à la date de départ restent calculées selon l’ancien modèle, sans effet sur les liquidités.';
    if ($negatives) $warnings[] = ($plan['kind'] === 'virtual' ? 'Portefeuille virtuel : la conversion sera refusée tant que le solde est négatif.' : 'Solde négatif à certaines dates (dépôt manquant ?) : toléré pour un portefeuille réel, à corriger si possible.');
    $dups = cash_duplicates($rows);
    if ($dups) $warnings[] = 'Doublon probable de transaction (n° ' . implode(' et ', $dups[0]['ids']) . ', ' . $dups[0]['symbol'] . ') : rien n’est supprimé automatiquement.';
    $v = portfolio_valuation((int)$p['id']);
    $ok = !$tl['unknown_fx'] && !($plan['kind'] === 'virtual' && $negatives);
    return ['plan' => $plan, 'ok' => $ok, 'plan_hash' => cash_plan_hash($plan, $rows), 'balance' => $tl['balance'], 'min_balance' => $min, 'negatives' => $negatives,
            'needed_opening' => $min && $min['balance'] < 0 ? round(-$min['balance'], 2) : 0.0, 'legacy_operations' => count($before), 'operations_in_model' => count($rows) - count($before),
            'positions_value' => $v['totals']['value'] ?? null, 'value_with_cash' => isset($v['totals']['value']) && $v['totals']['value'] !== null ? round($v['totals']['value'] + $tl['balance'], 2) : null,
            'timeline' => array_map(function ($e) { return ['at' => $e['at'], 'label' => $e['label'], 'balance' => $e['balance']]; }, array_slice($tl['events'], -60)), 'duplicates' => $dups, 'warnings' => $warnings];
}

function cash_convert_apply(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    if (empty($b['confirm'])) throw new ApiError('Confirmation requise après l’aperçu', 422);
    $plan = cash_convert_plan($b);
    return write_transaction((int)$u['id'], (int)$p['id'], function ($rows, $pf) use ($plan, $b) {
        if ($pf['cash_model'] !== 'legacy') throw new ApiError('Ce portefeuille a déjà des liquidités', 409);
        if (!hash_equals(cash_plan_hash($plan, $rows), (string)($b['plan_hash'] ?? ''))) throw new ApiError('L’aperçu ne correspond plus aux données : relancez l’aperçu avant de convertir', 409);
        $now = now_utc();
        q('UPDATE portfolios SET cash_model = ?, kind = ?, cash_from = ?, cash_converted_at = ?, updated_at = ? WHERE id = ?', ['cash', $plan['kind'], $plan['cash_from'], $now, $now, $pf['id']]);
        $ids = [];
        foreach ($plan['movements'] as $m) $ids[] = cash_insert((int)$pf['id'], $m + ['gross_amount' => null, 'withholding_tax' => null, 'listing_id' => null], 'conversion', $now);
        cash_audit((int)$pf['id'], null, 'convert', null, ['plan' => $plan, 'movement_ids' => $ids, 'max_transaction_id' => $rows ? max(array_map(function ($t) { return (int)$t['id']; }, $rows)) : 0]);
        return ['ok' => true, 'movement_ids' => $ids];   // write_transaction revalide ensuite tout l'historique avec les liquidités : refus et retour arrière si le solde est invalide
    });
}

// Annulation : possible uniquement si elle ne rend aucun historique incohérent.
// Bloquée par : un mouvement saisi après la conversion (dépôt, retrait, dividende, frais : il n'a aucun sens sans liquidités) ou une transaction créée après la conversion
// (elle a été validée contre les liquidités que la conversion a apportées).
function cash_undo_blockers(array $pf, array $rows, array $movements): array {
    $b = [];
    foreach ($movements as $m) if ($m['source'] !== 'conversion') $b[] = ['type' => 'movement', 'id' => (int)$m['id'], 'detail' => $m['kind'] . ' du ' . substr($m['occurred_at'], 0, 10)];
    // Transaction postérieure à la conversion : identifiant plus grand que le plus grand identifiant existant à ce moment (fiable à la seconde près, contrairement à la date de création).
    $a = q("SELECT after_json FROM portfolio_cash_audit WHERE portfolio_id = ? AND action = 'convert' ORDER BY id DESC LIMIT 1", [$pf['id']])->fetchColumn();
    $max = $a ? (json_decode($a, true)['max_transaction_id'] ?? null) : null;
    foreach ($rows as $t) {
        $later = $max !== null ? (int)$t['id'] > $max : $t['created_at'] > $pf['cash_converted_at'];
        if ($later) $b[] = ['type' => 'transaction', 'id' => (int)$t['id'], 'detail' => $t['side'] . ' ' . $t['symbol'] . ' du ' . substr($t['trade_at'], 0, 10)];
    }
    return $b;
}

function cash_convert_undo_preview(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    if ($p['cash_model'] !== 'cash' || $p['cash_converted_at'] === null) return ['possible' => false, 'blockers' => [], 'reason' => 'Ce portefeuille n’a pas été converti depuis l’ancien modèle'];
    $blockers = cash_undo_blockers($p, q('SELECT id, side, symbol, trade_at, created_at FROM portfolio_transactions WHERE portfolio_id = ?', [$p['id']])->fetchAll(), cash_load_movements((int)$p['id']));
    return ['possible' => !$blockers, 'blockers' => array_slice($blockers, 0, 20), 'blocker_count' => count($blockers), 'reason' => $blockers ? 'Des opérations dépendent des liquidités ajoutées par la conversion' : null];
}

function cash_convert_undo(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    if (empty($b['confirm'])) throw new ApiError('Confirmation requise', 422);
    return write_transaction((int)$u['id'], (int)$p['id'], function ($rows, $pf) {
        if ($pf['cash_model'] !== 'cash' || $pf['cash_converted_at'] === null) throw new ApiError('Ce portefeuille n’a pas été converti depuis l’ancien modèle', 409);
        $mov = cash_load_movements((int)$pf['id'], true);
        $blockers = cash_undo_blockers($pf, $rows, $mov);
        if ($blockers) throw new ApiError('Annulation refusée : ' . count($blockers) . ' opération(s) dépendent des liquidités (' . $blockers[0]['type'] . ' n° ' . $blockers[0]['id'] . ', ' . $blockers[0]['detail'] . ')', 409);
        q('DELETE FROM portfolio_cash_movements WHERE portfolio_id = ? AND source = ?', [$pf['id'], 'conversion']);
        q('UPDATE portfolios SET cash_model = ?, kind = NULL, cash_from = NULL, cash_converted_at = NULL, updated_at = ? WHERE id = ?', ['legacy', now_utc(), $pf['id']]);
        cash_audit((int)$pf['id'], null, 'undo_convert', ['movements' => $mov], null);
        return ['ok' => true];
    });
}
