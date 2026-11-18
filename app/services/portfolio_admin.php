<?php
// Administration des portefeuilles : création (avec capital), nom/icône/description, archivage, réinitialisation, suppression.
// Chaque opération destructrice : propriétaire vérifié, verrou de la ligne, une seule transaction, confirmation par le nom, aperçu des données concernées.
// Seules les données PROPRES au portefeuille sont touchées (jamais instruments, cotations, modèles d'alerte ni stratégies sauvegardées).
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/cash.php';
require_once __DIR__ . '/portfolio_access.php';

const PF_ICONS = ['💼', '📈', '🚀', '🛡️', '🌍', '🌱', '💰', '🏦', '🏠', '⭐', '🔥', '🎯', '🧪', '🎓', '🧺', '🪙'];   // liste fermée : l'icône n'est jamais un texte libre

function pf_icon(array $b): ?string {
    if (!isset($b['icon']) || $b['icon'] === '' || $b['icon'] === null) return null;
    if (!is_string($b['icon']) || !in_array($b['icon'], PF_ICONS, true)) throw new ApiError('Icône invalide', 422);
    return $b['icon'];
}

// Création. Avec « kind » (virtual|real) : portefeuille à liquidités, capital initial enregistré comme un apport (jamais comme un gain), le tout atomique.
// Sans « kind » : ancien modèle (compatibilité des appels existants) ; l'interface envoie toujours « kind ».
function pf_create(array $u, array $b = []) {
    $name = str_in($b, 'name', 100);
    $icon = pf_icon($b);
    $desc = str_in($b, 'description', 280, false) ?: null;
    $kind = isset($b['kind']) && $b['kind'] !== '' ? (string)$b['kind'] : null;
    if ($kind !== null && !in_array($kind, ['virtual', 'real'], true)) throw new ApiError('Type invalide (virtuel ou réel)', 422);
    $capital = 0.0; $start = gmdate('Y-m-d');
    if ($kind !== null) {
        $capital = num_in($b, 'initial_capital', $kind === 'virtual', 0) ?? 0.0;
        if ($kind === 'virtual' && $capital <= 0) throw new ApiError('Un portefeuille virtuel a besoin d’un capital initial supérieur à zéro', 422);
        if (!empty($b['start_date'])) $start = substr(cash_when((string)$b['start_date'], 'initial_capital'), 0, 10);
    }
    return tx(function () use ($u, $name, $icon, $desc, $kind, $capital, $start) {
        if (q('SELECT 1 FROM portfolios WHERE user_id = ? AND name = ?', [$u['id'], $name])->fetch()) throw new ApiError('Ce nom existe déjà', 409);
        $first = !q('SELECT 1 FROM portfolios WHERE user_id = ? AND archived_at IS NULL AND is_default = 1', [$u['id']])->fetch();
        $now = now_utc();
        q('INSERT INTO portfolios(user_id, name, is_default, icon, description, cash_model, kind, cash_from, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
          [$u['id'], $name, $first ? 1 : 0, $icon, $desc, $kind === null ? 'legacy' : 'cash', $kind, $kind === null ? null : CASH_ALL_HISTORY, $now, $now]);
        $id = (int)db()->lastInsertId();
        if ($kind !== null && $capital > 0)
            cash_insert($id, ['kind' => 'initial_capital', 'amount_net' => $capital, 'currency' => 'EUR', 'fx_to_eur' => 1.0, 'occurred_at' => $start . ' 00:00:00', 'note' => 'Capital initial'], 'manual', $now);
        return ['id' => $id];
    });
}

// Nom, icône, description : seuls les champs présents changent.
function pf_update(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    $set = []; $args = [];
    if (array_key_exists('name', $b)) {
        $name = str_in($b, 'name', 100);
        if (q('SELECT 1 FROM portfolios WHERE user_id = ? AND name = ? AND id <> ?', [$u['id'], $name, $p['id']])->fetch()) throw new ApiError('Ce nom existe déjà', 409);
        $set[] = 'name = ?'; $args[] = $name;
    }
    if (array_key_exists('icon', $b)) { $set[] = 'icon = ?'; $args[] = pf_icon($b); }
    if (array_key_exists('description', $b)) { $set[] = 'description = ?'; $args[] = str_in($b, 'description', 280, false) ?: null; }
    if (!$set) throw new ApiError('Rien à modifier', 422);
    q('UPDATE portfolios SET ' . implode(', ', $set) . ', updated_at = ? WHERE id = ?', array_merge($args, [now_utc(), $p['id']]));
    return ['ok' => true];
}

// Archivage : lecture seule, exclu du bilan par défaut. S'il était par défaut, le défaut passe à un autre portefeuille actif ; sinon action explicite (no_default).
function pf_archive(array $u, array $b = []) {
    $p0 = own_portfolio((int)($b['id'] ?? 0), $u);
    return tx(function () use ($u, $p0, $b) {
        $p = q('SELECT * FROM portfolios WHERE id = ? FOR UPDATE', [$p0['id']])->fetch();
        if ($p['archived_at'] !== null) return ['ok' => true, 'new_default' => null];
        $newDefault = null;
        if ($p['is_default']) {
            $other = q('SELECT id, name FROM portfolios WHERE user_id = ? AND id <> ? AND archived_at IS NULL ORDER BY name LIMIT 1', [$u['id'], $p['id']])->fetch();
            if (!$other && empty($b['no_default']))
                throw new ApiError('C’est votre seul portefeuille actif : créez-en un autre, ou confirmez l’archivage sans portefeuille par défaut', 409);
            q('UPDATE portfolios SET is_default = 0 WHERE id = ?', [$p['id']]);
            if ($other) { q('UPDATE portfolios SET is_default = 1 WHERE id = ?', [$other['id']]); $newDefault = ['id' => (int)$other['id'], 'name' => $other['name']]; }
        }
        q('UPDATE portfolios SET archived_at = ?, updated_at = ? WHERE id = ?', [now_utc(), now_utc(), $p['id']]);
        return ['ok' => true, 'new_default' => $newDefault];
    });
}

function pf_unarchive(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    q('UPDATE portfolios SET archived_at = NULL, updated_at = ? WHERE id = ?', [now_utc(), $p['id']]);
    return ['ok' => true];
}

// Données propres à un portefeuille, par catégorie (aperçu avant réinitialisation ou suppression).
function pf_data_counts(int $id): array {
    $one = function ($sql) use ($id) { return (int)q($sql, [$id])->fetchColumn(); };
    return [
        'transactions' => $one('SELECT COUNT(*) FROM portfolio_transactions WHERE portfolio_id = ?'),
        'lot_origins' => $one('SELECT COUNT(*) FROM lot_origin o JOIN portfolio_transactions t ON t.id = o.transaction_id WHERE t.portfolio_id = ?'),
        'lot_settings' => $one('SELECT COUNT(*) FROM lot_settings s JOIN portfolio_transactions t ON t.id = s.transaction_id WHERE t.portfolio_id = ?'),
        'cash_movements' => $one('SELECT COUNT(*) FROM portfolio_cash_movements WHERE portfolio_id = ?'),
        'cash_corrections' => $one('SELECT COUNT(*) FROM portfolio_cash_audit WHERE portfolio_id = ?'),
        'levels' => $one('SELECT COUNT(*) FROM position_levels WHERE portfolio_id = ?'),
        'targets' => $one('SELECT COUNT(*) FROM portfolio_targets WHERE portfolio_id = ?'),
        'alert_rules' => $one('SELECT COUNT(*) FROM alert_rules WHERE portfolio_id = ?'),
        'watch' => $one('SELECT COUNT(*) FROM position_watch WHERE portfolio_id = ?'),
        'watch_log' => $one('SELECT COUNT(*) FROM position_watch_log WHERE portfolio_id = ?'),
        'plan_rules' => $one('SELECT COUNT(*) FROM position_plan_rules WHERE portfolio_id = ?'),
    ];
}

function pf_reset_preview(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    return ['name' => $p['name'], 'cash_model' => $p['cash_model'], 'kind' => $p['kind'], 'counts' => pf_data_counts((int)$p['id']),
            'keeps' => ['nom', 'icône', 'description', 'type', 'stratégie associée', 'statut par défaut']];
}

// Tables portant une colonne portfolio_id : la garde de suppression les contrôle TOUTES, y compris celles ajoutées plus tard.
function pf_owned_tables(): array {
    return array_map(function ($r) { return $r['table_name']; }, q("SELECT DISTINCT table_name FROM information_schema.columns WHERE table_schema = DATABASE() AND column_name = 'portfolio_id' ORDER BY table_name")->fetchAll());
}

// Réinitialisation : toutes les opérations et données de suivi disparaissent, le portefeuille (identité, type, stratégie, défaut) reste. Capital initial optionnel ensuite.
function pf_reset(array $u, array $b = []) {
    $p0 = own_portfolio((int)($b['id'] ?? 0), $u);
    if (($b['confirm'] ?? '') !== $p0['name']) throw new ApiError('Tapez le nom du portefeuille pour confirmer la réinitialisation', 422);
    $capital = num_in($b, 'initial_capital', false, 0);
    if ($capital !== null && $capital > 0 && $p0['cash_model'] !== 'cash') throw new ApiError('Convertissez d’abord ce portefeuille au modèle avec liquidités pour y définir un capital', 422);
    $start = !empty($b['start_date']) ? substr(cash_when((string)$b['start_date'], 'initial_capital'), 0, 10) : gmdate('Y-m-d');
    return tx(function () use ($p0, $capital, $start) {
        $p = q('SELECT * FROM portfolios WHERE id = ? FOR UPDATE', [$p0['id']])->fetch();
        if ($p['archived_at'] !== null) throw new ApiError('Portefeuille archivé : désarchivez-le pour le réinitialiser', 409);
        $before = pf_data_counts((int)$p['id']);
        foreach (['portfolio_transactions', 'portfolio_cash_movements', 'portfolio_cash_audit', 'position_levels', 'portfolio_targets', 'alert_rules', 'position_watch', 'position_watch_log', 'position_plan_rules'] as $t)
            q("DELETE FROM $t WHERE portfolio_id = ?", [$p['id']]);   // lot_origin et lot_settings partent avec leurs transactions (clé étrangère en cascade)
        q('UPDATE portfolios SET cash_converted_at = NULL, updated_at = ? WHERE id = ?', [now_utc(), $p['id']]);
        $left = array_sum(pf_data_counts((int)$p['id']));
        if ($left) throw new ApiError('Réinitialisation incomplète : annulée', 500);
        if ($capital !== null && $capital > 0)
            cash_insert((int)$p['id'], ['kind' => 'initial_capital', 'amount_net' => $capital, 'currency' => 'EUR', 'fx_to_eur' => 1.0, 'occurred_at' => $start . ' 00:00:00', 'note' => 'Capital initial (après réinitialisation)']);
        if ($p['cash_model'] === 'cash') cash_audit((int)$p['id'], null, 'reset', $before, ['initial_capital' => $capital]);
        return ['ok' => true, 'deleted' => $before];
    });
}

function pf_delete_preview(array $u, array $b = []) {
    $p = own_portfolio((int)($b['id'] ?? 0), $u);
    $other = $p['is_default'] ? q('SELECT id, name FROM portfolios WHERE user_id = ? AND id <> ? AND archived_at IS NULL ORDER BY name LIMIT 1', [$u['id'], $p['id']])->fetch() : null;
    $counts = pf_data_counts((int)$p['id']);
    return ['name' => $p['name'], 'is_default' => (bool)$p['is_default'], 'new_default' => $other ?: null, 'counts' => $counts, 'has_data' => array_sum($counts) > 0];
}

// Suppression définitive : la ligne portfolios part, les clés étrangères en cascade retirent toutes ses données propres (transactions, lots, mouvements, alertes, niveaux, surveillance…).
// Garde : après la suppression, plus aucune ligne de aucune table portant portfolio_id ; sinon tout est annulé. Le défaut est réaffecté dans la même transaction.
function pf_delete(array $u, array $b = []) {
    $p0 = own_portfolio((int)($b['id'] ?? 0), $u);
    $counts = pf_data_counts((int)$p0['id']);
    if (array_sum($counts) > 0 && ($b['confirm'] ?? '') !== $p0['name'])
        throw new ApiError('Ce portefeuille contient des données (' . $counts['transactions'] . ' transactions, ' . $counts['cash_movements'] . ' mouvements d’argent) : tapez son nom pour confirmer la suppression', 422);
    return tx(function () use ($u, $p0) {
        $p = q('SELECT * FROM portfolios WHERE id = ? AND user_id = ? FOR UPDATE', [$p0['id'], $u['id']])->fetch();
        if (!$p) throw new ApiError('Portefeuille introuvable', 404);
        $deleted = pf_data_counts((int)$p['id']);
        q('DELETE FROM portfolios WHERE id = ?', [$p['id']]);
        foreach (pf_owned_tables() as $t) {
            if ($t === 'portfolios') continue;
            if ((int)q("SELECT COUNT(*) FROM `$t` WHERE portfolio_id = ?", [$p['id']])->fetchColumn() > 0) throw new ApiError("Suppression incomplète ($t) : annulée", 500);
        }
        $newDefault = null;
        if ($p['is_default']) {
            $other = q('SELECT id, name FROM portfolios WHERE user_id = ? AND archived_at IS NULL ORDER BY name LIMIT 1', [$u['id']])->fetch();
            if ($other) { q('UPDATE portfolios SET is_default = 1 WHERE id = ?', [$other['id']]); $newDefault = ['id' => (int)$other['id'], 'name' => $other['name']]; }
        }
        return ['ok' => true, 'deleted' => $deleted, 'new_default' => $newDefault];
    });
}
