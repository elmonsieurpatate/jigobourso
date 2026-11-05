<?php
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';

const SECONDARY_DEFINITIONS = 'explorer_secondary_filters';
const SECONDARY_DEFAULTS = 'explorer_secondary_defaults';

function secondary_proposed(): array {
    static $value;
    if ($value === null) $value = json_decode(file_get_contents(__DIR__ . '/../config/explorer_secondary_filters.json'), true, 512, JSON_THROW_ON_ERROR);
    return $value;
}
function secondary_ids(array $measure): array { return array_column($measure['categories'], 'id'); }
function secondary_all(): array { return ['mode' => 'all', 'selected' => []]; }
function secondary_json($value): string { return json_encode($value, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR); }
function secondary_decode(string $json): array {
    $v = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($v) || ($v['schema'] ?? null) !== 1) throw new ApiError('Configuration des filtres incompatible : aucun remplacement automatique.', 503);
    return $v;
}
/** Ne complète que les structures manquantes, jamais une catégorie supprimée intentionnellement. */
function secondary_initialize_once(): void {
    $db = db(); $db->beginTransaction();
    try {
        // Lock rows exclusively in a fixed order. INSERT IGNORE on existing keys
        // would first take shared locks, then deadlock on concurrent lock upgrades.
        $documents=[];
        foreach ([SECONDARY_DEFINITIONS => ['schema'=>1,'revision'=>1,'filters'=>[]], SECONDARY_DEFAULTS => ['schema'=>1,'revision'=>1,'filters'=>[]]] as $name=>$initial) {
            $json=q('SELECT value_json FROM settings WHERE name=? FOR UPDATE',[$name])->fetchColumn();
            if($json===false){q('INSERT INTO settings(name,value_json,updated_at) VALUES (?,?,?)',[$name,secondary_json($initial),now_utc()]);$documents[$name]=$initial;}
            else $documents[$name]=secondary_decode($json);
        }
        $definitions=$documents[SECONDARY_DEFINITIONS];$defaults=$documents[SECONDARY_DEFAULTS];
        if (!isset($definitions['filters'],$defaults['filters']) || !is_array($definitions['filters']) || !is_array($defaults['filters'])) throw new ApiError('Configuration des filtres illisible.',503);
        $oldD=$definitions; $oldS=$defaults;
        foreach (secondary_proposed()['filters'] as $f) {
            $id=$f['id']; $index=array_search($id,array_column($definitions['filters'],'id'),true);
            if ($index===false) { $definitions['filters'][]=$f; $index=count($definitions['filters'])-1; }
            $stored=&$definitions['filters'][$index];
            foreach (['enabled','name','description','editable'] as $key) if(!array_key_exists($key,$stored)) $stored[$key]=$f[$key];
            if (!isset($stored['measures'])) $stored['measures']=$f['measures'];
            foreach ($f['measures'] as $m) {
                $mi=array_search($m['id'],array_column($stored['measures'],'id'),true);
                if($mi===false) $stored['measures'][]=$m;
                else foreach($m as $field=>$value) if(!array_key_exists($field,$stored['measures'][$mi])) $stored['measures'][$mi][$field]=$value;
            }
            if(!array_key_exists($id,$defaults['filters'])) $defaults['filters'][$id]=[];
            foreach ($stored['measures'] as $m) if(!array_key_exists($m['id'],$defaults['filters'][$id])) $defaults['filters'][$id][$m['id']]=secondary_all();
            if(!$f['editable']&&!array_key_exists('values',$defaults['filters'][$id])) $defaults['filters'][$id]['values']=secondary_all();
            unset($stored);
        }
        foreach ([[SECONDARY_DEFINITIONS,$oldD,$definitions],[SECONDARY_DEFAULTS,$oldS,$defaults]] as [$name,$old,$next]) {
            if($old!==$next) { $next['revision']=(int)$old['revision']+1; q('UPDATE settings SET value_json=?,updated_at=? WHERE name=?',[secondary_json($next),now_utc(),$name]); }
        }
        $db->commit();
    } catch(Throwable $e) { if($db->inTransaction())$db->rollBack();throw $e; }
}
function secondary_initialize(): void {
    // A simultaneous very first insertion can contend on an InnoDB gap lock.
    // Retry only an aborted transaction, never a partially committed update.
    for($attempt=0;$attempt<4;$attempt++){
        try{secondary_initialize_once();return;}
        catch(PDOException $e){
            $code=(int)($e->errorInfo[1]??0);
            if(!in_array($code,[1205,1213],true))throw $e;
            if($attempt===3)throw new ApiError('Les réglages sont occupés. Réessayez dans un instant.',409);
            usleep(10000*($attempt+1));
        }
    }
}
function secondary_setting(string $name): array { return secondary_decode(q('SELECT value_json FROM settings WHERE name=?',[$name])->fetchColumn()); }
function secondary_find(array $definitions,string $id): array {
    foreach($definitions['filters'] as $f) if($f['id']===$id)return $f;
    throw new ApiError('Filtre inconnu.',404);
}
/** Catalogue stocké complet, sans lancer une sélection ni modifier les garde-fous techniques. */
function secondary_catalogue(): array {
    $out=['country'=>[],'sector'=>[],'market'=>[],'asset'=>[]];
    foreach(q("SELECT DISTINCT TRIM(country) value FROM instruments WHERE country IS NOT NULL AND TRIM(country)<>'' ORDER BY value")->fetchAll() as $r) $out['country'][]=['id'=>'country:'.$r['value'],'label'=>$r['value'],'value'=>$r['value']];
    foreach(q("SELECT DISTINCT kind,TRIM(category) value FROM instruments WHERE category IS NOT NULL AND TRIM(category)<>'' ORDER BY kind,value")->fetchAll() as $r) $out['sector'][]=['id'=>$r['kind'].':'.$r['value'],'label'=>($r['kind']==='equity'?'Actions · secteur : ':'ETF · catégorie : ').$r['value'],'value'=>$r['value'],'kind'=>$r['kind']];
    foreach(q("SELECT DISTINCT TRIM(mic) value FROM listings WHERE TRIM(mic)<>'' ORDER BY value")->fetchAll() as $r) $out['market'][]=['id'=>'market:'.$r['value'],'label'=>$r['value'],'value'=>$r['value']];
    foreach(q('SELECT DISTINCT kind value FROM instruments ORDER BY kind')->fetchAll() as $r) $out['asset'][]=['id'=>'asset:'.$r['value'],'label'=>['equity'=>'Action','etf'=>'ETF'][$r['value']]??$r['value'],'value'=>$r['value']];
    foreach($out as &$values)$values[]=['id'=>'unknown','label'=>'Inconnu','value'=>null];unset($values);
    return $out;
}
function secondary_read(): array {
    secondary_initialize();
    // Read the two documents consistently, including during a restore transaction.
    $values=q('SELECT name,value_json FROM settings WHERE name IN (?,?)',[SECONDARY_DEFINITIONS,SECONDARY_DEFAULTS])->fetchAll(PDO::FETCH_KEY_PAIR);
    $definitions=secondary_decode($values[SECONDARY_DEFINITIONS]);$defaults=secondary_decode($values[SECONDARY_DEFAULTS]);
    $catalogue=secondary_catalogue();
    foreach($definitions['filters'] as &$f) if(!$f['editable'])$f['values']=$catalogue[$f['id']]??[];unset($f);
    return ['schema'=>2,'source'=>'settings','source_label'=>'Réglages persistants de l’administration','definitions'=>$definitions,'defaults'=>$defaults,'proposed'=>secondary_proposed(),'catalogue_scope'=>'Valeurs présentes dans le catalogue stocké ; aucun calcul de classement.','filtering_connected'=>false];
}
function secondary_bound($v): bool { return $v===null || ((is_int($v)||is_float($v))&&is_finite((float)$v)); }
function secondary_validate_measure(array $m,array $categories): void {
    if(!array_is_list($categories)||count($categories)>100)throw new ApiError('100 catégories maximum par mesure.',422);
    $ids=[];$names=[];$unknown=0;$active=[];
    foreach($categories as $c){
        if(is_array($c)&&array_diff(array_keys($c),['id','name','description','min','max','minIncluded','maxIncluded','color','active','unknown','values']))throw new ApiError('Champ de catégorie non autorisé.',422);
        if(!is_array($c)||!is_string($c['id']??null)||!preg_match('/^[a-zA-Z0-9_-]{1,100}$/',$c['id'])||isset($ids[$c['id']]))throw new ApiError('Identifiants de catégories invalides ou dupliqués.',422);
        $ids[$c['id']]=true;
        $name=$c['name']??null;$normalized=is_string($name)?mb_strtolower(trim($name)):'';
        if($normalized===''||mb_strlen($name)>80||isset($names[$normalized]))throw new ApiError('Noms de catégories vides ou dupliqués.',422);$names[$normalized]=true;
        if(!is_string($c['description']??null)||mb_strlen($c['description'])>180||!preg_match('/^#[a-f0-9]{6}$/i',$c['color']??''))throw new ApiError('Description ou couleur invalide.',422);
        foreach(['active','unknown','minIncluded','maxIncluded'] as $key)if(!is_bool($c[$key]??null))throw new ApiError('États de catégorie booléens attendus.',422);
        if(!array_key_exists('min',$c)||!array_key_exists('max',$c)||!secondary_bound($c['min'])||!secondary_bound($c['max'])||!is_array($c['values']??null)||!array_is_list($c['values']))throw new ApiError('Bornes numériques invalides.',422);
        if($c['unknown']){if(++$unknown>1||!$m['supportsUnknown']||$c['min']!==null||$c['max']!==null||$c['values']!==[]||$c['minIncluded']||$c['maxIncluded'])throw new ApiError('Une seule inconnue, sans borne ni valeur, est autorisée.',422);continue;}
        if($m['kind']==='enum'){
            $allowed=array_column($m['domain'],'value');if(!$c['values']||count(array_filter($c['values'],'is_string'))!==count($c['values'])||count(array_unique($c['values']))!==count($c['values'])||array_diff($c['values'],$allowed)||$c['min']!==null||$c['max']!==null)throw new ApiError('Valeurs d’état invalides.',422);
        }else{
            if($c['values']!==[]||($c['min']===null&&$c['minIncluded'])||($c['max']===null&&$c['maxIncluded'])||($c['min']!==null&&$c['max']!==null&&($c['min']>$c['max']||($c['min']==$c['max']&&!($c['minIncluded']&&$c['maxIncluded'])))))throw new ApiError('Intervalle vide, inversé ou incohérent.',422);
        }
        if($c['active'])$active[]=$c;
    }
    foreach($active as $i=>$a)foreach(array_slice($active,$i+1) as $b){
        if($m['kind']==='enum'){$overlap=(bool)array_intersect($a['values'],$b['values']);}
        else{
            $lo=max($a['min']??-INF,$b['min']??-INF);$hi=min($a['max']??INF,$b['max']??INF);
            $includes=function($c,$v){return ($c['min']===null||$v>$c['min']||($v==$c['min']&&$c['minIncluded']))&&($c['max']===null||$v<$c['max']||($v==$c['max']&&$c['maxIncluded']));};
            $overlap=$lo<$hi||($lo==$hi&&is_finite($lo)&&$includes($a,$lo)&&$includes($b,$lo));
        }
        if($overlap)throw new ApiError('Chevauchement entre « '.$a['name'].' » et « '.$b['name'].' ».',422);
    }
}
function secondary_validate_filter(array $candidate,array $canonical): void {
    if(($candidate['id']??null)!==$canonical['id']||!is_bool($candidate['enabled']??null))throw new ApiError('Filtre ou activation invalide.',422);
    if(array_diff(array_keys($candidate),['id','name','description','editable','enabled','measures','provenance']))throw new ApiError('Champ de filtre non autorisé.',422);
    if(isset($canonical['provenance'])&&($candidate['provenance']??null)!==$canonical['provenance'])throw new ApiError('Provenance non modifiable.',422);
    // Definition identity/units/domains cannot be changed by this API.
    foreach(['name','description','editable'] as $key)if(($candidate[$key]??null)!==$canonical[$key])throw new ApiError('Identité de filtre non modifiable.',422);
    if(!$canonical['editable']){
        if(($candidate['measures']??null)!==[]||isset($candidate['values'])||isset($candidate['examples']))throw new ApiError('Les valeurs de ce filtre ne sont pas éditables.',422);return;
    }
    if(!is_array($candidate['measures']??null)||!array_is_list($candidate['measures'])||array_column($candidate['measures'],'id')!==array_column($canonical['measures'],'id'))throw new ApiError('Mesures prédéfinies attendues.',422);
    foreach($candidate['measures'] as $index=>$m){
        foreach(['id','name','description','unit','kind','domain','supportsUnknown'] as $field)if(($m[$field]??null)!==$canonical['measures'][$index][$field])throw new ApiError('Mesure, unité ou domaine non modifiable.',422);
        if(!is_array($m['categories']??null))throw new ApiError('Catégories attendues.',422);
        secondary_validate_measure($m,$m['categories']);
    }
}
/** Atomic patch with optimistic revision: stale admin tabs never silently win. */
function secondary_write(array $request): array {
    secondary_initialize();$db=db();$db->beginTransaction();
    try{
        $d=secondary_decode(q('SELECT value_json FROM settings WHERE name=? FOR UPDATE',[SECONDARY_DEFINITIONS])->fetchColumn());
        $s=secondary_decode(q('SELECT value_json FROM settings WHERE name=? FOR UPDATE',[SECONDARY_DEFAULTS])->fetchColumn());
        if(!is_string($request['filter_id']??null))throw new ApiError('Identifiant de filtre requis.',422);
        $id=$request['filter_id'];$stored=secondary_find($d,$id);$canonical=secondary_find(secondary_proposed(),$id);$action=$request['action']??'save';
        $index=array_search($id,array_column($d['filters'],'id'),true);$changedD=false;$changedS=false;
        if(in_array($action,['save','restore'],true)&&($request['revision']??null)!==$d['revision'])throw new ApiError('Les filtres ont changé dans une autre session. Rechargez avant d’enregistrer.',409);
        if(in_array($action,['defaults','restore'],true)&&($request['defaults_revision']??null)!==$s['revision'])throw new ApiError('Les sélections par défaut ont changé. Rechargez avant d’enregistrer.',409);
        if($action==='save'){
            $candidate=$request['filter']??null;if(!is_array($candidate))throw new ApiError('Filtre attendu.',422);
            // Client temporary IDs are replaced once and returned to the UI.
            secondary_validate_filter($candidate,$canonical);
            foreach($candidate['measures'] as &$m){foreach($m['categories'] as &$c){if(str_starts_with($c['id'],'new-'))$c['id']='cat-'.bin2hex(random_bytes(16));}unset($c);}unset($m);$d['filters'][$index]=$candidate;$changedD=true;
            foreach($candidate['measures'] as $m){
                $selection=$s['filters'][$id][$m['id']]??secondary_all();
                if($selection['mode']==='custom'){$selected=array_values(array_intersect($selection['selected'],secondary_ids($m)));if($selected!==$selection['selected']){$s['filters'][$id][$m['id']]['selected']=$selected;$changedS=true;}}
            }
        }elseif($action==='defaults'){
            if(isset($request['measure_id'])&&!is_string($request['measure_id']))throw new ApiError('Identifiant de mesure invalide.',422);
            $measure=$request['measure_id']??'values';$selection=$request['selection']??null;
            if(!is_array($selection)||!in_array($selection['mode']??null,['all','custom'],true)||!is_array($selection['selected']??null)||!array_is_list($selection['selected']))throw new ApiError('Sélection par défaut invalide.',422);
            if($stored['editable']){$m=null;foreach($stored['measures'] as $item)if($item['id']===$measure)$m=$item;if(!$m)throw new ApiError('Mesure inconnue.',422);$allowed=secondary_ids($m);}
            else{if($measure!=='values')throw new ApiError('Valeurs catalogue attendues.',422);$allowed=array_column(secondary_catalogue()[$id],'id');}
            if(count(array_filter($selection['selected'],'is_string'))!==count($selection['selected'])||count(array_unique($selection['selected']))!==count($selection['selected'])||array_diff($selection['selected'],$allowed)||($selection['mode']==='all'&&$selection['selected']!==[]))throw new ApiError('Catégorie ou valeur par défaut inconnue.',422);
            $s['filters'][$id][$measure]=$selection;$changedS=true;
        }elseif($action==='restore'){
            $d['filters'][$index]=$canonical;$changedD=true;$s['filters'][$id]=[];
            foreach($canonical['measures'] as $m)$s['filters'][$id][$m['id']]=secondary_all();
            if(!$canonical['editable'])$s['filters'][$id]['values']=secondary_all();$changedS=true;
        }else throw new ApiError('Action inconnue.',422);
        if($changedD){$d['revision']++;q('UPDATE settings SET value_json=?,updated_at=? WHERE name=?',[secondary_json($d),now_utc(),SECONDARY_DEFINITIONS]);}
        if($changedS){$s['revision']++;q('UPDATE settings SET value_json=?,updated_at=? WHERE name=?',[secondary_json($s),now_utc(),SECONDARY_DEFAULTS]);}
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
    return secondary_read();
}
