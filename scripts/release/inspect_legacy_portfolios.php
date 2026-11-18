<?php
// Vérification ASO ciblée : seuls des booléens sont exportés, aucun montant ni transaction.
// Les données métier ne sont pas modifiées ; le calcul normal peut actualiser son cache de marché.
require_once getcwd() . '/app/services/portfolios.php';
$pdo=db();$pdo->exec('SET TRANSACTION READ ONLY');$pdo->beginTransaction();
try {
    $owners=q("SELECT user_id FROM portfolios WHERE name IN ('Midterms','Nouveau') GROUP BY user_id HAVING COUNT(DISTINCT name)=2")->fetchAll();
    if(count($owners)!==1)throw new RuntimeException('Périmètre ambigu');
    $uid=(int)$owners[0]['user_id'];
    $pfs=q("SELECT id FROM portfolios WHERE user_id=? AND (name IN ('Midterms','Nouveau','Portefeuille principal') OR is_default=1)",[$uid])->fetchAll();
    $out=['financial_data_unchanged'=>true,'aso_found'=>false];
    foreach($pfs as $p){
        $v=portfolio_valuation((int)$p['id']);
        foreach($v['positions'] as $pos){
            if(!preg_match('/^ASO(?:[.].*)?$/i',$pos['symbol']))continue;
            $out['aso_found']=true;
            $perf=pf_performance(['id'=>$uid],['id'=>(int)$p['id']]);
            $key=(string)$pos['listing_id'];
            $gain=end($perf['chart']['full']['holdings'][$key]['gain']);
            $total=end($perf['chart']['full']['gain']);
            $share=is_numeric($gain)&&is_numeric($total)&&abs($total)>1e-9?100*$gain/abs($total):null;
            $market=engine_call('portfolio-dynamics',['listing_ids'=>[(int)$pos['listing_id']]])['listings'][$key];
            $month=$market['cells']['1m'];
            $rows=q('SELECT side,quantity,unit_price,fx_to_eur,currency,fees,trade_at FROM portfolio_transactions WHERE portfolio_id=? AND listing_id=? ORDER BY trade_at,id',[(int)$p['id'],(int)$pos['listing_id']])->fetchAll();
            $buys=array_values(array_filter($rows,fn($r)=>$r['side']==='buy'));
            $sales=array_filter($rows,fn($r)=>$r['side']==='sell');
            $first=$buys[0]??null;
            $near=fn($x,$target)=>is_numeric($x)&&abs((float)$x-$target)<2;
            $flags=[
              'contribution_is_share_of_total_gain'=>true,
              'gain_share_near_reported_21'=>$near($share,21),
              'personal_EUR_return_near_reported_26'=>$near($pos['unrealized_pct'],26),
              'month_price_return_near_reported_24'=>$near($month['return'],24),
              'contribution_and_personal_return_differ'=>is_numeric($share)&&is_numeric($pos['unrealized_pct'])&&abs($share-$pos['unrealized_pct'])>1,
              'single_purchase_without_sale'=>count($buys)===1&&!$sales,
              'purchase_is_october_20'=>$first&&substr($first['trade_at'],5,5)==='10-20',
              'month_window_starts_before_purchase'=>$first&&$month['start']&&$month['start']<substr($first['trade_at'],0,10),
              'valuation_quote_is_newer_than_market_window'=>substr((string)$pos['price_time'],0,10)>$month['end'],
              'purchase_currency_not_EUR'=>$first&&strtoupper($first['currency'])!=='EUR',
              'personal_gain_and_cost_reconcile'=>$pos['cost']>0&&$pos['value']!==null&&abs(100*($pos['value']-$pos['cost'])/$pos['cost']-$pos['unrealized_pct'])<1e-8,
            ];
            if($first&&count($buys)===1&&!$sales){
                $expected=(float)$first['quantity']*(float)$first['unit_price']*(float)$first['fx_to_eur']+(float)$first['fees'];
                $flags['purchase_cost_matches_record']=abs($expected-$pos['cost'])<1e-6;
                $f=eur_factor($pos['price_currency'],fx_rates());
                $flags['FX_has_changed_since_purchase']=$f!==null&&abs($f-(float)$first['fx_to_eur'])>1e-6;
                $flags['FX_increases_EUR_return']=$f!==null&&$f>(float)$first['fx_to_eur'];
                $last=q('SELECT close_px FROM daily_prices WHERE listing_id=? AND price_date=?',[(int)$pos['listing_id'],$month['end']])->fetch();
                $flags['valuation_quote_matches_market_end_close']=$last&&abs((float)$pos['price']-(float)$last['close_px'])<1e-5;
                $usd=100*((float)$pos['price']/(float)$first['unit_price']-1);
                $flags['USD_purchase_return_is_lower_than_personal_EUR_return']=$usd<$pos['unrealized_pct'];
                $b=q('SELECT close_px FROM daily_prices WHERE listing_id=? AND price_date=?',[(int)$pos['listing_id'],$month['start']])->fetch();
                $flags['purchase_price_lower_than_month_start']=$b&&(float)$first['unit_price']<(float)$b['close_px'];
            }
            $out['checks'][]=$flags;
        }
    }
    echo json_encode($out,JSON_THROW_ON_ERROR),PHP_EOL;
}finally{if($pdo->inTransaction())$pdo->rollBack();}
