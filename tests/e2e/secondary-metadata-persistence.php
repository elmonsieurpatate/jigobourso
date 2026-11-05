<?php
if(getenv('JIGO_TEST_DATABASE')!=='1'||!in_array(getenv('JIGO_DB_NAME'),['jigobourso_filters_it','jigobourso_it'],true))throw new RuntimeException('Base isolée requise');
require __DIR__.'/../../app/services/secondary_filters.php';
$check=function($ok,$why){if(!$ok)throw new RuntimeException($why);};
$raw=q('SELECT name,value_json FROM settings WHERE name IN (?,?) ORDER BY name',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll(PDO::FETCH_KEY_PAIR);
$state=secondary_read();$d=$state['definitions'];$s=$state['defaults'];
$volIndex=array_search('volatility',array_column($d['filters'],'id'),true);
$d['filters'][$volIndex]['enabled']=false;$d['filters'][$volIndex]['measures'][0]['categories'][0]['name']='Personnalisée préexistante';
$d['filters'][$volIndex]['measures'][0]['categories'][0]['active']=false;$financial=$d['filters'][$volIndex];
unset($s['category_selection_version'],$s['category_selection_previous']);
foreach($d['filters'] as &$f)if($f['id']==='country'){$f['enabled']=false;$f['name']='Pays';$f['description']='Ancienne définition';}unset($f);
unset($d['metadata_version'],$d['metadata_migration'],$s['metadata_version'],$s['metadata_migration']);
$s['filters']['country']['values']=['mode'=>'custom','selected'=>['country:France','country:United States','country:Atlantis']];
$s['filters']['market']['values']=['mode'=>'custom','selected'=>['market:XPAR','market:XNAS','market:ZZZZ']];
$s['filters']['sector']['values']=['mode'=>'custom','selected'=>['equity:Technology','etf:Equity']];
$s['filters']['asset']['values']=['mode'=>'custom','selected'=>['unknown']];
$s['filters']['volatility']['volatility']=['mode'=>'all','selected'=>[]];
$oldDefaults=$s;
try{
 q('UPDATE settings SET value_json=? WHERE name=?',[secondary_json($d),SECONDARY_DEFINITIONS]);q('UPDATE settings SET value_json=? WHERE name=?',[secondary_json($s),SECONDARY_DEFAULTS]);
 secondary_initialize();$next=secondary_read();
 $check(secondary_find($next['definitions'],'volatility')===$financial,'Personnalisations financières intactes');
 $country=secondary_find($next['definitions'],'country');$check($country['name']==='Zone géographique'&&!$country['enabled'],'Renommage sans réactivation silencieuse');
 foreach(['country'=>['country:europe','country:us','country:other'],'market'=>['market:europe','market:us','unknown'],'sector'=>['sector:technology','sector:other']] as $id=>$expected)$check($next['defaults']['filters'][$id]['values']['selected']===$expected,'Migration '.$id);
 $check($next['defaults']['filters']['asset']['values']['mode']==='all','Ancien type inconnu : aucun type artificiel ni exclusion silencieuse');
 $check($next['defaults']['filters']['volatility']['volatility']===['mode'=>'custom','selected'=>array_values(array_diff(secondary_ids($financial['measures'][0]),[$financial['measures'][0]['categories'][0]['id']]))],'Ancienne catégorie masquée convertie en sélection explicite');
 $check($next['defaults']['category_selection_previous']['volatility']['volatility']['legacy_unselected']===[$financial['measures'][0]['categories'][0]['id']],'Ancienne activation archivée sans supprimer la catégorie');
 $check($next['defaults']['metadata_migration']['previous']['country']===$oldDefaults['filters']['country']['values'],'Ancienne sélection archivée dans settings');
 $check(count($next['migration_notices'])===4,'Avis explicites de migration');
 $after=q('SELECT name,value_json,updated_at FROM settings WHERE name IN (?,?) ORDER BY name',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll();secondary_read();secondary_initialize();
 $check($after===q('SELECT name,value_json,updated_at FROM settings WHERE name IN (?,?) ORDER BY name',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll(),'Migration strictement idempotente');
 $next=secondary_write(['action'=>'defaults','filter_id'=>'country','measure_id'=>'values','selection'=>['mode'=>'custom','selected'=>['country:emerging','unknown']],'defaults_revision'=>$next['defaults']['revision']]);
 $check(secondary_read()['defaults']['filters']['country']['values']['selected']===['country:emerging','unknown'],'Nouveaux défauts conservés au rechargement');
 $next=secondary_write(['action'=>'restore','filter_id'=>'country','revision'=>$next['definitions']['revision'],'defaults_revision'=>$next['defaults']['revision']]);
 $check($next['defaults']['filters']['country']['values']['mode']==='all'&&secondary_find($next['definitions'],'country')['enabled'],'Restauration explicite des nouveaux défauts');
 $check(secondary_find($next['definitions'],'volatility')===$financial,'Restauration ciblée préserve les autres réglages');
}finally{foreach($raw as $key=>$json)q('UPDATE settings SET value_json=? WHERE name=?',[$json,$key]);}
// A single French instrument with US and EU listings: origin must not follow exchange.
q("INSERT INTO listings(instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,'XNAS','FIX1US','USD','candidate',0)");
q("UPDATE instruments SET category='Equity' WHERE id=2");
$report=secondary_catalogue_report();$assign=$report['assignments'];
$check(secondary_metadata_classify('country',q('SELECT country FROM instruments WHERE id=1')->fetchColumn())['id']==='country:europe','Double cotation : pays de rattachement préservé');
$check(in_array('market:us',array_column($assign['market'],'id'),true)&&in_array('market:europe',array_column($assign['market'],'id'),true),'Double cotation : deux marchés identifiés');
$check((bool)array_filter($assign['sector'],fn($r)=>($r['kind']??null)==='etf'&&$r['raw']==='Equity'&&$r['id']==='sector:other'),'ETF large : pas de secteur action inventé');
foreach($assign as $filter=>$rows){if($filter!=='asset')foreach($rows as $row)$check($row['id']!==null,'Aucune métadonnée abandonnée');}
$beforeCheck=q('SELECT name,value_json,updated_at FROM settings ORDER BY name')->fetchAll();
exec(escapeshellarg(PHP_BINARY).' '.escapeshellarg(__DIR__.'/../../scripts/check_secondary_catalogue.php'),$checkOutput,$checkCode);
$check($checkCode===0&&str_contains(implode(' ',$checkOutput),'affectations exhaustives'),'Contrôle du catalogue réellement stocké');
$check($beforeCheck===q('SELECT name,value_json,updated_at FROM settings ORDER BY name')->fetchAll(),'Contrôle du catalogue sans initialisation ni écriture settings');
echo "PASS: migration ancienne->groupes, archives, idempotence, défauts et activation préservés, restauration ciblée, inconnus, ETF large, double cotation indépendante du pays.\n";
