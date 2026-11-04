<?php
/** Typed saves; no mutation or implicit conversion of historical saved searches. */
function explorer_library_list(int $uid): array {
    $items = q('SELECT id,kind,name,payload,active,updated_at FROM explorer_saved WHERE user_id=? ORDER BY kind,name',[$uid])->fetchAll();
    foreach ($items as &$item) { $item['id']=(string)$item['id'];$item['payload']=json_decode($item['payload'],true);if (isset($item['payload']['config']) && is_array($item['payload']['config'])) $item['payload']['config']=explorer_config_shape($item['payload']['config']);if (($item['payload']['universe']??null)===[])$item['payload']['universe']=new stdClass();$item['active']=(bool)$item['active'];$item['legacy']=false; } unset($item);
    foreach (q('SELECT id,name,config,view,updated_at FROM saved_searches WHERE user_id=?',[$uid])->fetchAll() as $r)
        $items[]=['id'=>'legacy-search:'.$r['id'],'name'=>$r['name'],'kind'=>'search','legacy'=>true,'active'=>true,'updated_at'=>$r['updated_at'],'payload'=>['schema'=>3,'config'=>json_decode($r['config'],true),'universe'=>json_decode($r['view'],true)?:new stdClass()]];
    foreach (q('SELECT preset,config,view,updated_at FROM saved_presets WHERE user_id=?',[$uid])->fetchAll() as $r)
        $items[]=['id'=>'legacy-preset:'.$r['preset'],'name'=>$r['preset'].' (réglage personnel)','kind'=>'search','legacy'=>true,'active'=>true,'updated_at'=>$r['updated_at'],'payload'=>['schema'=>3,'config'=>json_decode($r['config'],true),'universe'=>json_decode($r['view'],true)?:new stdClass()]];
    $states=[];
    foreach(q('SELECT item_key,active,archived FROM explorer_states WHERE user_id=?',[$uid])->fetchAll() as $r)
        $states[$r['item_key']]=['active'=>(bool)$r['active'],'archived'=>(bool)$r['archived']];
    foreach($items as &$item) {
        $key=$item['legacy']?$item['id']:'saved:'.$item['id'];$state=$states[$key]??null;
        $item['archived']=$state['archived']??false;
        if($state && $item['legacy'])$item['active']=$state['active'];
    } unset($item);
    return ['items'=>$items,'states'=>$states?:new stdClass()];
}

function explorer_library_state(int $uid,array $b): array {
    $key=(string)($b['id']??'');
    if(preg_match('/^[0-9]+$/',$key))$key='saved:'.$key;
    $active=$b['active']??false;$archived=$b['archived']??false;
    if(!is_bool($active)||!is_bool($archived))throw new ApiError('États booléens requis',422);
    if(preg_match('/^saved:([0-9]+)$/',$key,$m)) {
        if(!q('SELECT id FROM explorer_saved WHERE id=? AND user_id=?',[$m[1],$uid])->fetch())throw new ApiError('Sauvegarde introuvable',404);
        q('UPDATE explorer_saved SET active=?,updated_at=? WHERE id=? AND user_id=?',[$active?1:0,now_utc(),$m[1],$uid]);
    } elseif(preg_match('/^legacy-search:([0-9]+)$/',$key,$m)) {
        if(!q('SELECT id FROM saved_searches WHERE id=? AND user_id=?',[$m[1],$uid])->fetch())throw new ApiError('Recherche introuvable',404);
    } elseif(preg_match('/^legacy-preset:([a-z0-9_]+)$/',$key,$m)) {
        if(!q('SELECT preset FROM saved_presets WHERE preset=? AND user_id=?',[$m[1],$uid])->fetch())throw new ApiError('Profil introuvable',404);
    } elseif(!in_array($key,['builtin:regular','builtin:fast','builtin:recovery','builtin:low_volatility','builtin:momentum','builtin:momentum12','builtin:momentum_risk'],true))throw new ApiError('Profil introuvable',404);
    q('INSERT INTO explorer_states(user_id,item_key,active,archived,updated_at) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE active=VALUES(active),archived=VALUES(archived),updated_at=VALUES(updated_at)',[$uid,$key,$active?1:0,$archived?1:0,now_utc()]);
    return ['ok'=>true];
}
function explorer_library_save(int $uid,array $b): array {
    $kind=(string)($b['kind']??'');
    if (!in_array($kind,['strategy','universe','search'],true)) throw new ApiError('Type de sauvegarde inconnu',422);
    $name=str_in($b,'name',80);$p=$b['payload']??null;
    if (!is_array($p)) throw new ApiError('Sauvegarde invalide',422);
    $payload=['schema'=>4];
    if ($kind!=='universe') $payload['config']=engine_call('validate-config',is_array($p['config']??null)?$p['config']:[]);
    if ($kind!=='strategy') $payload['universe']=clean_view($p['universe']??[]);
    $id=(int)($b['id']??0);
    if ($id && !q('SELECT id FROM explorer_saved WHERE id=? AND user_id=?',[$id,$uid])->fetch()) throw new ApiError('Sauvegarde introuvable',404);
    if (!$id && (int)q('SELECT COUNT(*) FROM explorer_saved WHERE user_id=?',[$uid])->fetchColumn()>=150) throw new ApiError('150 sauvegardes au maximum',422);
    if (q('SELECT id FROM explorer_saved WHERE user_id=? AND kind=? AND name=? AND id<>?',[$uid,$kind,$name,$id])->fetch()) throw new ApiError('Ce nom existe déjà dans cette catégorie',422);
    $args=[$kind,$name,json_encode($payload),!array_key_exists('active',$b)||$b['active']?1:0,now_utc()];
    if ($id) q('UPDATE explorer_saved SET kind=?,name=?,payload=?,active=?,updated_at=? WHERE id=? AND user_id=?',array_merge($args,[$id,$uid]));
    else { q('INSERT INTO explorer_saved(kind,name,payload,active,updated_at,user_id,created_at) VALUES (?,?,?,?,?,?,?)',array_merge($args,[$uid,now_utc()]));$id=(int)db()->lastInsertId(); }
    return ['id'=>(string)$id,'ok'=>true];
}

function explorer_legacy_action(int $uid,array $b): array {
    $id=(string)($b['id']??'');$action=(string)($b['action']??'');
    if (preg_match('/^legacy-search:([0-9]+)$/',$id,$m)) {
        if (!q('SELECT id FROM saved_searches WHERE id=? AND user_id=?',[(int)$m[1],$uid])->fetch()) throw new ApiError('Recherche introuvable',404);
        if ($action==='rename') q('UPDATE saved_searches SET name=?,updated_at=? WHERE id=? AND user_id=?',[str_in($b,'name',80),now_utc(),(int)$m[1],$uid]);
        elseif ($action==='delete') q('DELETE FROM saved_searches WHERE id=? AND user_id=?',[(int)$m[1],$uid]);
        else throw new ApiError('Action inconnue',422);
    } elseif (preg_match('/^legacy-preset:([a-z0-9_]+)$/',$id,$m) && $action==='delete') {
        q('DELETE FROM saved_presets WHERE user_id=? AND preset=?',[$uid,$m[1]]);
    } else throw new ApiError('Cette sauvegarde historique doit être dupliquée pour être renommée',422);
    return ['ok'=>true];
}
