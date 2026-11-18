<?php
// Diagnostic SELECT uniquement : aucun montant, identifiant, symbole ou transaction exporté.
require_once getcwd() . '/app/lib/db.php';
$pdo=db(); $pdo->exec('SET TRANSACTION READ ONLY'); $pdo->beginTransaction();
try {
    $owners=q("SELECT user_id FROM portfolios WHERE name IN ('Midterms','Nouveau') GROUP BY user_id HAVING COUNT(DISTINCT name)=2")->fetchAll();
    if (count($owners)!==1) throw new RuntimeException('Périmètre ambigu');
    $pfs=q("SELECT id,name,is_default,cash_model FROM portfolios WHERE user_id=? AND (name IN ('Midterms','Nouveau','Portefeuille principal') OR is_default=1)",[(int)$owners[0]['user_id']])->fetchAll();
    if (count($pfs)>4) throw new RuntimeException('Périmètre ambigu');
    $summary=['read_only'=>true,'legacy_portfolio_found'=>false,'midterms_sale_recorded'=>false,'external_cash_movement_recorded'=>false,'principal_withdrawal_recorded'=>false,'duplicate_transaction_candidate'=>false];
    foreach ($pfs as $p) {
        $id=(int)$p['id'];
        $summary['legacy_portfolio_found']=$summary['legacy_portfolio_found']||$p['cash_model']==='legacy';
        if ($p['name']==='Midterms') $summary['midterms_sale_recorded']=(bool)q("SELECT 1 FROM portfolio_transactions WHERE portfolio_id=? AND side='sell' LIMIT 1",[$id])->fetchColumn();
        $summary['external_cash_movement_recorded']=$summary['external_cash_movement_recorded']||(bool)q("SELECT 1 FROM portfolio_cash_movements WHERE portfolio_id=? AND kind IN ('deposit','withdrawal','initial_capital') LIMIT 1",[$id])->fetchColumn();
        if ($p['is_default'] || $p['name']==='Portefeuille principal') $summary['principal_withdrawal_recorded']=(bool)q("SELECT 1 FROM portfolio_cash_movements WHERE portfolio_id=? AND kind='withdrawal' LIMIT 1",[$id])->fetchColumn();
        $summary['duplicate_transaction_candidate']=$summary['duplicate_transaction_candidate']||(bool)q('SELECT 1 FROM portfolio_transactions WHERE portfolio_id=? GROUP BY listing_id,symbol,side,quantity,unit_price,trade_at HAVING COUNT(*)>1 LIMIT 1',[$id])->fetchColumn();
    }
    echo json_encode($summary,JSON_THROW_ON_ERROR),PHP_EOL;
} finally { if ($pdo->inTransaction()) $pdo->rollBack(); }
