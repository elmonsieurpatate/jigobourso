<?php
// Exclusively the disposable database created by the local validation launcher.
if(getenv('JIGO_TEST_DATABASE')!=='1'||!in_array(getenv('JIGO_DB_NAME'),['jigobourso_filters_it','jigobourso_it'],true))throw new RuntimeException('Base isolée requise');
require __DIR__.'/../../app/services/secondary_filters.php';
require __DIR__.'/../../app/lib/auth.php';
$check=function($condition,$message){if(!$condition)throw new RuntimeException($message);};
$reject=function($action,$status)use($check){try{$action();}catch(ApiError $e){$check($e->status===$status,'Statut attendu '.$status.', reçu '.$e->status);return;}throw new RuntimeException('Rejet attendu');};
if(($argv[1]??'')==='seed'){
    $adminId=create_user('filters_admin','filters-isolated-password',null,true);create_user('filters_reader','filters-reader-password',null,false);
    foreach([[1,'equity','France','Technology'],[2,'etf','United States','Technology'],[3,'equity',null,null]] as [$id,$kind,$country,$sector]){
        q('INSERT INTO instruments(id,group_key,kind,name,country,category) VALUES (?,?,?,?,?,?)',[$id,'filters:'.$id,$kind,'Catalogue isolé '.$id,$country,$sector]);
        q("INSERT INTO listings(instrument_id,mic,symbol,currency,status,is_primary) VALUES (?,?,?,'EUR','candidate',1)",[$id,$id===1?'XPAR':'XNAS','FIX'.$id]);
    }
    q('INSERT INTO settings(name,value_json,updated_at) VALUES (?,?,?)',['explorer_growth','{"weights":{"force":35},"historical":"preserve"}',now_utc()]);
    q('INSERT INTO settings(name,value_json,updated_at) VALUES (?,?,?)',['catalogue_rules','{"preserve":true}',now_utc()]);
    q('INSERT INTO saved_searches(user_id,name,config,view,created_at,updated_at) VALUES (?,?,?,?,?,?)',[$adminId,'Recherche à préserver','{"strategy":"legacy"}','{}',now_utc(),now_utc()]);
    q('INSERT INTO saved_presets(user_id,preset,config,view,updated_at) VALUES (?,?,?,?,?)',[$adminId,'fast','{"legacy":true}','{}',now_utc()]);
    q('INSERT INTO portfolios(user_id,name,strategy_config,created_at,updated_at) VALUES (?,?,?,?,?)',[$adminId,'Portefeuille à conserver','{"legacy":true}',now_utc(),now_utc()]);
    $pf=(int)db()->lastInsertId();
    q("INSERT INTO portfolio_transactions(portfolio_id,symbol,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,created_at) VALUES (?,'KEEP','buy',1,10,'EUR',1,0.25,'2026-11-04',?)",[$pf,now_utc()]);
    q('INSERT INTO result_cache(cache_key,data_version,built_at,payload) VALUES (?,?,?,?)',[str_repeat('a',40),'preserve',now_utc(),'{"score":77,"rank":1}']);
    echo "Fixtures privées prêtes.\n";exit;
}
$untouched=function(){return hash('sha256',json_encode([q('SELECT * FROM settings WHERE name NOT IN (?,?) ORDER BY name',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll(),q('SELECT * FROM saved_searches ORDER BY id')->fetchAll(),q('SELECT * FROM saved_presets ORDER BY user_id,preset')->fetchAll(),q('SELECT id,prefs_json FROM users ORDER BY id')->fetchAll(),q('SELECT * FROM instruments ORDER BY id')->fetchAll(),q('SELECT * FROM listings ORDER BY id')->fetchAll(),q('SELECT * FROM portfolios ORDER BY id')->fetchAll(),q('SELECT * FROM portfolio_transactions ORDER BY id')->fetchAll(),q('SELECT * FROM result_cache ORDER BY cache_key')->fetchAll()]));};
$original=$untouched();$state=secondary_read();$check(count($state['definitions']['filters'])===13,'13 filtres');
$check(count(array_filter($state['definitions']['filters'],fn($f)=>$f['editable']))===9,'9 éditables');
$raw=q('SELECT name,value_json,updated_at FROM settings WHERE name IN (?,?) ORDER BY name',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll();secondary_initialize();secondary_read();
$check($raw===q('SELECT name,value_json,updated_at FROM settings WHERE name IN (?,?) ORDER BY name',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll(),'Initialisation strictement idempotente');
foreach($state['definitions']['filters'] as $f){$check($f['enabled'],'13 filtres activés initialement');if(!$f['editable'])$check($state['defaults']['filters'][$f['id']]['values']['mode']==='all','Métadonnées toutes incluses initialement');foreach($f['measures'] as $m){secondary_validate_measure($m,$m['categories']);$check($state['defaults']['filters'][$f['id']][$m['id']]['mode']==='all','Toutes incluses initialement');}}
$metadata=secondary_catalogue();$check(array_column($metadata['asset'],'id')===['asset:equity','asset:etf'],'Deux types uniquement');
$check(count($metadata['country'])===5&&count($metadata['market'])===5&&count($metadata['sector'])===12,'Groupes fixes');
$report=secondary_catalogue_report();$check(in_array('sector:technology',array_column($report['assignments']['sector'],'id'),true),'Correspondances sectorielles explicites');
$save=function($f,$s){return secondary_write(['action'=>'save','filter_id'=>$f['id'],'filter'=>$f,'revision'=>$s['definitions']['revision']]);};
$vol=secondary_find($state['definitions'],'volatility');$vol['enabled']=false;$vol['measures'][0]['categories'][2]['name']='Modérée persistante';$vol['measures'][0]['categories'][2]['description']='Description persistante';$vol['measures'][0]['categories'][2]['color']='#aabbcc';
$stale=$state;$state=$save($vol,$state);secondary_initialize();$state=secondary_read();$actual=secondary_find($state['definitions'],'volatility');
$check(!$actual['enabled']&&$actual['measures'][0]['categories'][2]['name']==='Modérée persistante','Édition et activation conservées');
$reject(fn()=>$save($vol,$stale),409);
$vol=$actual;$new=$vol['measures'][0]['categories'][0];$new['id']='new-1';$new['name']='Nouvelle catégorie';$new['active']=true;$new['min']=0;$new['max']=0.75;$new['minIncluded']=false;$new['maxIncluded']=true;$vol['measures'][0]['categories'][0]['max']=0;$new['description']='Nouvel identifiant stable';$vol['measures'][0]['categories'][]=$new;$state=$save($vol,$state);
$vol=secondary_find($state['definitions'],'volatility');$newId=end($vol['measures'][0]['categories'])['id'];$check((bool)preg_match('/^cat-[a-f0-9]{32}$/',$newId),'Identifiant serveur pérenne');
$state=secondary_read();$check(end(secondary_find($state['definitions'],'volatility')['measures'][0]['categories'])['id']===$newId,'Identifiant conservé au rechargement');
$vol['measures'][0]['categories']=array_reverse($vol['measures'][0]['categories']);$state=$save($vol,$state);$check(secondary_find($state['definitions'],'volatility')['measures'][0]['categories'][0]['id']===$newId,'Ordre persistant');
$chosen=$vol['measures'][0]['categories'][1]['id'];$state=secondary_write(['action'=>'defaults','filter_id'=>'volatility','measure_id'=>'volatility','selection'=>['mode'=>'custom','selected'=>[$chosen]],'defaults_revision'=>$state['defaults']['revision']]);
$beforeDefs=$state['definitions'];$state=secondary_read();$check($state['defaults']['filters']['volatility']['volatility']['selected']===[$chosen],'Défauts persistants');$check($state['definitions']===$beforeDefs,'Défauts distincts des définitions');
$bad=$vol;$bad['measures'][0]['unit']='annualisé inventé';$reject(fn()=>$save($bad,$state),422);
$bad=$vol;$bad['measures'][0]['categories'][1]['min']=99;$bad['measures'][0]['categories'][1]['max']=1;$reject(fn()=>$save($bad,$state),422);
$country=secondary_find($state['definitions'],'country');$country['values']=[['id'=>'fake','label'=>'Inventé']];$reject(fn()=>$save($country,$state),422);
$reject(fn()=>secondary_write(['action'=>'defaults','filter_id'=>'country','measure_id'=>'values','selection'=>['mode'=>'custom','selected'=>['country:Inventé']],'defaults_revision'=>$state['defaults']['revision']]),422);
$vol=secondary_find($state['definitions'],'volatility');$vol['measures'][0]['categories']=[];$state=$save($vol,$state);secondary_initialize();$check(secondary_find(secondary_read()['definitions'],'volatility')['measures'][0]['categories']===[],'Ne ressuscite pas les catégories supprimées');
$liquidity=secondary_find($state['definitions'],'liquidity');$liquidity['enabled']=false;$state=$save($liquidity,$state);
$state=secondary_write(['action'=>'restore','filter_id'=>'volatility','revision'=>$state['definitions']['revision'],'defaults_revision'=>$state['defaults']['revision']]);
$check(secondary_find($state['definitions'],'volatility')===secondary_find(secondary_proposed(),'volatility'),'Restauration exacte ciblée');$check(!secondary_find($state['definitions'],'liquidity')['enabled'],'Restauration préserve les autres filtres');$check($state['defaults']['filters']['volatility']['volatility']['mode']==='all','Restauration des sélections');
// Simulate an older document missing a filter: append only the missing definition.
$d=$state['definitions'];$d['filters']=array_values(array_filter($d['filters'],fn($f)=>$f['id']!=='asset'));q('UPDATE settings SET value_json=? WHERE name=?',[secondary_json($d),SECONDARY_DEFINITIONS]);secondary_initialize();$state=secondary_read();$check(count($state['definitions']['filters'])===13&&!secondary_find($state['definitions'],'liquidity')['enabled'],'Complément sans écrasement');
$check($untouched()===$original,'Réglages historiques, recherches, profils, utilisateurs et catalogue inchangés');
// Reset only these two test documents to the proposals before browser tests.
foreach($state['definitions']['filters'] as $f)if(!$f['enabled'])$state=secondary_write(['action'=>'restore','filter_id'=>$f['id'],'revision'=>$state['definitions']['revision'],'defaults_revision'=>$state['defaults']['revision']]);
echo "PASS: DB MariaDB réelle, 13/9/4, idempotence, rechargement, activation, catégories, couleurs/descriptions, IDs stables, ordre, défauts distincts, conflits, validation, métadonnées réelles, restauration ciblée, conservation de l’existant.\n";
