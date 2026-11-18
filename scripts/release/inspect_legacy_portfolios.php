<?php
// SELECT uniquement : vérifie des concordances, n'exporte aucun montant ni transaction.
require_once getcwd().'/app/services/portfolios.php';
$pdo=db();$pdo->exec('SET TRANSACTION READ ONLY');$pdo->beginTransaction();
try{
 $owners=q("SELECT user_id FROM portfolios WHERE name IN ('Midterms','Nouveau') GROUP BY user_id HAVING COUNT(DISTINCT name)=2")->fetchAll();
 if(count($owners)!==1)throw new RuntimeException('Périmètre ambigu');
 $uid=(int)$owners[0]['user_id'];
 $p=q("SELECT id FROM portfolios WHERE user_id=? AND (is_default=1 OR name='Portefeuille principal') ORDER BY is_default DESC,id LIMIT 1",[$uid])->fetch();
 if(!$p)throw new RuntimeException('Portefeuille introuvable');
 $id=(int)$p['id'];$v=portfolio_valuation($id);$old=pf_history(['id'=>$uid],['id'=>$id]);$new=pf_performance(['id'=>$uid],['id'=>$id]);
 $growth=1.;$valid=true;
 foreach($old['performance']['factors'] as $f){if($f===null){$valid=false;break;}$growth*=$f;}
 $oldPct=$valid?100*($growth-1):null;
 $r=end($new['chart']['full']['twr']['central']);$newPct=$r===null?null:100*$r;
 $oldGain=end($old['gain']);$newGain=end($new['chart']['full']['gain']);
 echo json_encode(['financial_data_unchanged'=>true,'old_method_is_modified_dietz'=>$old['performance']['method']==='linked_daily_modified_dietz','old_return_near_reported_21_58'=>$oldPct!==null&&abs($oldPct-21.58)<.2,'new_return_near_reported_23_57'=>$newPct!==null&&abs($newPct-23.57)<.2,'both_methods_produce_different_returns'=>$oldPct!==null&&$newPct!==null&&abs($oldPct-$newPct)>.1,'old_gain_matches_ledger'=>is_numeric($oldGain)&&abs($oldGain-$v['totals']['total_gain'])<.01,'new_gain_matches_ledger'=>is_numeric($newGain)&&abs($newGain-$v['totals']['total_gain'])<.01,'both_gain_amounts_match'=>is_numeric($oldGain)&&is_numeric($newGain)&&abs($oldGain-$newGain)<.01],JSON_THROW_ON_ERROR),PHP_EOL;
}finally{if($pdo->inTransaction())$pdo->rollBack();}
