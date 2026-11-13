<?php
/** Filtres de vue conservés dans une recherche ou un réglage enregistré : valeurs simples seulement, clés connues seulement. */
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/engine.php';
function clean_view($in): array {
    $view = [];
    if (!is_array($in)) return $view;
    foreach (['currency', 'min_aum', 'max_aum', 'kind', 'geo_region', 'market', 'country', 'category', 'budget', 'min_price', 'max_price', 'min_score', 'max_volatility', 'max_drawdown', 'min_volume', 'max_fee',
        'cap', 'regularity', 'risk', 'liquidity', 'pea', 'owned_only', 'open_now', 'fresh_only', 'sort', 'dir'] as $k)
        if (isset($in[$k]) && is_scalar($in[$k]) && $in[$k] !== '' && $in[$k] !== false) $view[$k] = $in[$k];
    if (isset($view['kind']) && !in_array($view['kind'], ['all', 'equity', 'etf', 'large_etf'], true)) unset($view['kind']);
    if (isset($view['geo_region']) && !in_array($view['geo_region'], ['us', 'eu', 'emerging'], true)) unset($view['geo_region']);
    if (isset($in['q']) && is_scalar($in['q'])) $view['q'] = mb_substr(trim((string)$in['q']), 0, 100);
    if (array_key_exists('tradable', $in) && is_bool($in['tradable'])) $view['tradable'] = $in['tradable'];
    if (isset($in['status']) && in_array($in['status'], ['retained', 'rejected', 'unknown', 'all'], true)) $view['status'] = $in['status'];
    if (isset($in['description']) && is_scalar($in['description'])) $view['description'] = mb_substr(trim((string)$in['description']), 0, 300);
    if (isset($in['icon']) && in_array($in['icon'], ['📈', '⚡', '🔎', '🛡️', '🌱', '📊', '💼', '⭐'], true)) $view['icon'] = $in['icon'];
    return $view;
}

/** Sauvegardes typées (stratégie, univers, recherche) de l'utilisateur. */
function explorer_library_list(int $uid): array {
    $items = q('SELECT id,kind,name,payload,active,updated_at FROM explorer_saved WHERE user_id=? ORDER BY kind,name',[$uid])->fetchAll();
    foreach ($items as &$item) { $item['id']=(string)$item['id'];$item['payload']=json_decode($item['payload'],true);if (isset($item['payload']['config']) && is_array($item['payload']['config'])) $item['payload']['config']=explorer_config_shape($item['payload']['config']);if (($item['payload']['universe']??null)===[])$item['payload']['universe']=new stdClass();$item['active']=(bool)$item['active'];
        } unset($item);
    return ['items'=>$items];
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
