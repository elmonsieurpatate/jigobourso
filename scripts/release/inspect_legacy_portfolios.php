<?php
// Diagnostic ponctuel, SELECT uniquement, exécuté par stdin. Aucun endpoint web.
require_once getcwd() . '/app/services/portfolios.php';
$pdo = db();
$pdo->exec('SET TRANSACTION READ ONLY');
$pdo->beginTransaction();
try {
    $owners = q("SELECT user_id FROM portfolios WHERE name IN ('Midterms','Nouveau') GROUP BY user_id HAVING COUNT(DISTINCT name)=2")->fetchAll();
    if (count($owners) !== 1) throw new RuntimeException('Compte non identifié de façon unique ; aucune donnée exportée');
    $uid = (int)$owners[0]['user_id'];
    $pfs = q("SELECT id,name,is_default,cash_model,kind,cash_from FROM portfolios WHERE user_id=? AND (name IN ('Midterms','Nouveau','Portefeuille principal') OR is_default=1) ORDER BY id", [$uid])->fetchAll();
    if (count($pfs)>4) throw new RuntimeException('Périmètre ambigu ; arrêt');
    $out = ['read_only'=>true, 'observed_at'=>gmdate('c'), 'portfolios'=>[]];
    foreach ($pfs as $p) {
        $id = (int)$p['id'];
        $rows = q('SELECT id,listing_id,symbol,name,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at FROM portfolio_transactions WHERE portfolio_id=? ORDER BY trade_at,id',[$id])->fetchAll();
        $movements = q('SELECT id,kind,amount_net,currency,fx_to_eur,occurred_at,source FROM portfolio_cash_movements WHERE portfolio_id=? ORDER BY occurred_at,id',[$id])->fetchAll();
        $v = portfolio_valuation($id);
        $buys = $sells = 0.0; $missing = [];
        $balance = 0.0; $minimum = 0.0;
        foreach ($rows as $t) {
            $fx = $t['fx_to_eur'] !== null ? (float)$t['fx_to_eur'] : (strtoupper($t['currency'])==='EUR' ? 1.0 : null);
            if ($fx===null) { $missing[]=(int)$t['id']; continue; }
            $gross=(float)$t['quantity']*(float)$t['unit_price']*$fx;
            $amount=$t['side']==='buy' ? $gross+(float)$t['fees'] : $gross-(float)$t['fees'];
            if ($t['side']==='buy') { $buys+=$amount; $balance-=$amount; } else { $sells+=$amount; $balance+=$amount; }
            $minimum=min($minimum,$balance);
        }
        $out['portfolios'][] = $p + ['transactions'=>$rows,'cash_movements'=>$movements,'totals'=>$v['totals'], 'positions'=>array_map(fn($r)=>array_intersect_key($r,array_flip(['listing_id','symbol','qty','cost','value','unrealized','realized'])),$v['positions']), 'closed'=>array_map(fn($r)=>array_intersect_key($r,array_flip(['listing_id','symbol','qty','realized'])),$v['closed']), 'duplicates'=>cash_duplicates($rows), 'cash_flow_summary'=>['buys_with_fees_eur'=>$buys,'sales_net_fees_eur'=>$sells,'net_buy_outlay_eur'=>$buys-$sells,'minimum_initial_funding_without_external_flows_eur'=>-$minimum,'residual_if_minimum_funding_eur'=>$balance-$minimum,'unknown_fx_transaction_ids'=>$missing], 'note'=>'Le financement minimum est un calcul hypothétique, pas une preuve de dépôt ou de solde réel.'];
    }
    echo json_encode($out,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT);
} finally {
    if ($pdo->inTransaction()) $pdo->rollBack();
}
