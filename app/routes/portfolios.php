<?php
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../services/portfolios.php';

// Routes de portefeuille : authentification, méthode, paramètres ; la logique est dans services/portfolios.php.
return [
    'portfolios' => function () { return pf_list(require_user(), $_GET); },
    'portfolio' => function () { return pf_detail(require_user(), $_GET); },
    'portfolio/history-refresh' => function () { need_post(); return pf_history_refresh(require_user(), body()); },
    'portfolio/history' => function () { return pf_history(require_user(), $_GET); },
    'portfolio/performance' => function () { return pf_performance(require_user(), $_GET); },
    'position/levels' => function () { need_post(); return pf_set_levels(require_user(), body()); },
    'portfolio/target' => function () { need_post(); return pf_set_target(require_user(), body()); },
    'lot/settings' => function () { need_post(); return pf_lot_settings(require_user(), body()); },
    'portfolio/create' => function () { need_post(); return pf_create(require_user(), body()); },
    'portfolio/rename' => function () { need_post(); return pf_rename(require_user(), body()); },
    'portfolio/default' => function () { need_post(); return pf_make_default(require_user(), body()); },
    'portfolio/delete' => function () { need_post(); return pf_delete(require_user(), body()); },
    'portfolio/update' => function () { need_post(); return pf_update(require_user(), body()); },
    'portfolio/archive' => function () { need_post(); return pf_archive(require_user(), body()); },
    'portfolio/unarchive' => function () { need_post(); return pf_unarchive(require_user(), body()); },
    'portfolio/reset-preview' => function () { return pf_reset_preview(require_user(), $_GET); },
    'portfolio/reset' => function () { need_post(); return pf_reset(require_user(), body()); },
    'portfolio/delete-preview' => function () { return pf_delete_preview(require_user(), $_GET); },
    'portfolio/cash' => function () { return cash_list(require_user(), $_GET); },
    'cash/add' => function () { need_post(); return cash_add(require_user(), body()); },
    'cash/update' => function () { need_post(); return cash_update(require_user(), body()); },
    'cash/delete' => function () { need_post(); return cash_delete(require_user(), body()); },
    'portfolio/convert-preview' => function () { need_post(); return cash_convert_preview(require_user(), body()); },
    'portfolio/convert' => function () { need_post(); return cash_convert_apply(require_user(), body()); },
    'portfolio/convert-undo-preview' => function () { return cash_convert_undo_preview(require_user(), $_GET); },
    'portfolio/convert-undo' => function () { need_post(); return cash_convert_undo(require_user(), body()); },
    'portfolio/strategy' => function () { need_post(); return pf_set_strategy(require_user(), body()); },
    'tx/preview' => function () { need_post(); return tx_preview(require_user(), body()); },
    'tx/add' => function () { need_post(); return tx_add(require_user(), body()); },
    'tx/delete' => function () { need_post(); return tx_delete(require_user(), body()); },
    'tx/update' => function () { need_post(); return tx_update(require_user(), body()); },
    'bilan' => function () { return pf_bilan(require_user(), $_GET); },
    'export' => function () {
        $u = require_user();
        $export = pf_export_data($u, (int)($_GET['id'] ?? 0));
        $p = $export['portfolio'];
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="transactions-' . preg_replace('/[^A-Za-z0-9_-]+/', '_', $p['name']) . '.csv"');
        $f = fopen('php://output', 'w');
        // Un texte qui commence par = + - @ (ou tabulation / retour) serait interprété comme une formule par un tableur : on le préfixe d'une apostrophe.
        $cell = function ($v) { return is_string($v) && $v !== '' && strpbrk($v[0], "=+-@\t\r") !== false ? "'" . $v : $v; };
        fputcsv($f, ['date', 'sens', 'symbole', 'nom', 'isin', 'quantite', 'prix_unitaire', 'devise', 'change_eur', 'frais', 'note'], ',', '"', '');
        foreach ($export['transactions'] as $t)
            fputcsv($f, [$t['trade_at'], $t['side'], $cell($t['symbol']), $cell($t['name']), $cell($t['isin']), $t['quantity'], $t['unit_price'], $t['currency'], $t['fx_to_eur'], $t['fees'], $cell($t['note'])], ',', '"', '');
        exit;
    },
];
