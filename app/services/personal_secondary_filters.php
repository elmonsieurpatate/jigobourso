<?php
/** Définitions et options personnelles de l'Explorer, indépendantes des stratégies. */
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/secondary_filters.php';

function secondary_user_key(int $userId): string { return 'explorer_secondary_user:' . $userId; }
function secondary_user_empty(): array { return ['schema'=>1,'revision'=>0,'overrides'=>[],'defaults'=>[],'order'=>[]]; }
function secondary_user_document(int $userId): array {
    $json=q('SELECT value_json FROM settings WHERE name=?',[secondary_user_key($userId)])->fetchColumn();
    $doc=$json===false?secondary_user_empty():secondary_decode($json);
    foreach(['overrides','defaults','order'] as $field)if(!is_array($doc[$field]??null))throw new ApiError('Vos filtres sont illisibles. Aucun réglage remplacé.',503);
    return $doc;
}
function secondary_user_revision(array $base,array $doc): string {
    return hash('sha256',secondary_json([$base['definitions']['revision'],$base['defaults']['revision'],$doc['revision']]));
}
function secondary_user_merge(array $base,array $doc): array {
    foreach($base['definitions']['filters'] as &$filter){
        $id=$filter['id'];$own=$doc['overrides'][$id]??null;
        if($own){
            $filter['enabled']=$own['enabled'];$filter['group']=$own['group'];
            foreach($filter['measures'] as &$measure){
                foreach($own['measures'] as $saved)if($saved['id']===$measure['id'])$measure['categories']=$saved['categories'];
            }unset($measure);
        }
        foreach(($doc['defaults'][$id]??[]) as $measure=>$selection)$base['defaults']['filters'][$id][$measure]=$selection;
        foreach($filter['measures'] as $measure){
            $selection=$base['defaults']['filters'][$id][$measure['id']]??secondary_all();
            if($selection['mode']==='custom')$selection['selected']=array_values(array_intersect($selection['selected'],secondary_ids($measure)));
            $base['defaults']['filters'][$id][$measure['id']]=$selection;
        }
    }unset($filter);
    $byId=[];foreach($base['definitions']['filters'] as $f)$byId[$f['id']]=$f;
    $ordered=[];foreach($doc['order'] as $id)if(isset($byId[$id])){$ordered[]=$byId[$id];unset($byId[$id]);}
    $base['definitions']['filters']=array_merge($ordered,array_values($byId));
    $base['definitions']['revision']=$base['defaults']['revision']=secondary_user_revision($base,$doc);
    $base['source']='personal';$base['source_label']='Mes filtres de l’Explorer';$base['filtering_connected']=true;
    $base['personalized_filters']=array_keys($doc['overrides']);
    return $base;
}
function secondary_user_read(int $userId): array { return secondary_user_merge(secondary_read(),secondary_user_document($userId)); }

function secondary_user_write_once(int $userId,array $request): array {
    $base=secondary_read();
    tx(function () use ($userId,$request,$base) {
        // Même ordre de verrous que les réglages partagés ; l'identité vient toujours de la session.
        foreach([SECONDARY_DEFINITIONS=>'definitions',SECONDARY_DEFAULTS=>'defaults'] as $key=>$field){
            $now=secondary_decode(q('SELECT value_json FROM settings WHERE name=? FOR UPDATE',[$key])->fetchColumn());
            if($now['revision']!==$base[$field]['revision'])throw new ApiError('Les valeurs de référence ont changé. Rechargez vos filtres.',409);
        }
        $json=q('SELECT value_json FROM settings WHERE name=? FOR UPDATE',[secondary_user_key($userId)])->fetchColumn();
        $doc=$json===false?secondary_user_empty():secondary_decode($json);$current=secondary_user_merge($base,$doc);
        $action=$request['action']??'save';
        if(!in_array($action,['save','defaults','restore','order'],true))throw new ApiError('Action inconnue.',422);
        $revision=$action==='defaults'?($request['defaults_revision']??null):($request['revision']??null);
        if($revision!==$current['definitions']['revision']||($action==='restore'&&($request['defaults_revision']??null)!==$current['defaults']['revision']))throw new ApiError('Vos filtres ont changé dans une autre fenêtre. Rechargez avant d’enregistrer.',409);
        if($action==='order'){
            $order=$request['order']??null;$ids=array_column($current['definitions']['filters'],'id');
            if(!is_array($order)||!array_is_list($order)||count($order)!==count($ids)||count(array_filter($order,'is_string'))!==count($order)||count(array_unique($order))!==count($order)||array_diff($order,$ids))throw new ApiError('Ordre des filtres invalide.',422);
            $doc['order']=$order;
        }else{
            $id=$request['filter_id']??null;if(!is_string($id))throw new ApiError('Identifiant de filtre requis.',422);
            $stored=secondary_find($current['definitions'],$id);
            if($action==='save'){
                $candidate=$request['filter']??null;if(!is_array($candidate))throw new ApiError('Filtre attendu.',422);
                secondary_validate_filter($candidate,secondary_find(secondary_proposed(),$id));
                foreach($candidate['measures'] as &$m){foreach($m['categories'] as &$c)if(str_starts_with($c['id'],'new-'))$c['id']='cat-'.bin2hex(random_bytes(16));unset($c);}unset($m);
                $doc['overrides'][$id]=$candidate;
                foreach($candidate['measures'] as $m){
                    $selection=$doc['defaults'][$id][$m['id']]??null;
                    if($selection&&$selection['mode']==='custom')$doc['defaults'][$id][$m['id']]['selected']=array_values(array_intersect($selection['selected'],secondary_ids($m)));
                }
            }elseif($action==='defaults'){
                $measure=$request['measure_id']??'values';$selection=$request['selection']??null;
                if(!is_string($measure)||!is_array($selection)||!in_array($selection['mode']??null,['all','custom'],true)||!is_array($selection['selected']??null)||!array_is_list($selection['selected']))throw new ApiError('Sélection par défaut invalide.',422);
                if($stored['editable']){
                    $found=null;foreach($stored['measures'] as $m)if($m['id']===$measure)$found=$m;
                    if(!$found)throw new ApiError('Mesure inconnue.',422);$allowed=secondary_ids($found);
                }else{if($measure!=='values')throw new ApiError('Valeurs catalogue attendues.',422);$allowed=array_column($stored['values'],'id');}
                $chosen=$selection['selected'];
                if(count(array_filter($chosen,'is_string'))!==count($chosen)||count(array_unique($chosen))!==count($chosen)||array_diff($chosen,$allowed)||($selection['mode']==='all'&&$chosen!==[]))throw new ApiError('Catégorie ou valeur inconnue.',422);
                $doc['defaults'][$id][$measure]=$selection;
            }elseif($action==='restore'){
                unset($doc['overrides'][$id],$doc['defaults'][$id]);
            }
        }
        $doc['revision']++;
        q('INSERT INTO settings(name,value_json,updated_at) VALUES (?,?,?) ON DUPLICATE KEY UPDATE value_json=VALUES(value_json),updated_at=VALUES(updated_at)',[secondary_user_key($userId),secondary_json($doc),now_utc()]);
    });
    return secondary_user_read($userId);
}
function secondary_user_write(int $userId,array $request): array {
    for($attempt=0;$attempt<4;$attempt++){
        try{return secondary_user_write_once($userId,$request);}
        catch(PDOException $e){
            if(!in_array((int)($e->errorInfo[1]??0),[1205,1213],true))throw $e;
            if($attempt===3)throw new ApiError('Vos filtres sont occupés. Réessayez dans un instant.',409);
            usleep(10000*($attempt+1));
        }
    }
    throw new ApiError('Enregistrement impossible.',503);
}
