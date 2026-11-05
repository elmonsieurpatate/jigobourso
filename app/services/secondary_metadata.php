<?php
/** Pure metadata grouping; no strategy, prices, score or market-calendar dependency. */
function secondary_metadata_config(): array {
    static $config;
    return $config ??= json_decode(file_get_contents(__DIR__.'/../config/secondary_metadata_groups.json'),true,512,JSON_THROW_ON_ERROR);
}
function secondary_metadata_key(?string $value): string {
    $value=mb_strtolower(trim($value??''));
    $value=strtr($value,['é'=>'e','è'=>'e','ê'=>'e','ë'=>'e','à'=>'a','â'=>'a','ä'=>'a','á'=>'a','ã'=>'a','å'=>'a','î'=>'i','ï'=>'i','í'=>'i','ì'=>'i','ô'=>'o','ö'=>'o','ó'=>'o','ò'=>'o','õ'=>'o','û'=>'u','ü'=>'u','ú'=>'u','ù'=>'u','ç'=>'c','ñ'=>'n','ý'=>'y','ÿ'=>'y']);
    return preg_replace('/\s+/u',' ',$value);
}
function secondary_metadata_classify(string $filter,?string $raw,?string $kind=null): array {
    $c=secondary_metadata_config();$key=secondary_metadata_key($raw);
    $missing=in_array($key,['','unknown','inconnu','inconnue','n/a','n.a.','none','null','not available','unavailable','-','—'],true);
    if($filter==='asset')return ['id'=>in_array($key,['equity','etf'],true)?'asset:'.$key:null,'reason'=>in_array($key,['equity','etf'],true)?'mapped':'unsupported'];
    if($missing)return ['id'=>'unknown','reason'=>'missing'];
    if($filter==='country')return ['id'=>$c['country_aliases'][$key]??'country:other','reason'=>isset($c['country_aliases'][$key])?'mapped':'unmapped-country'];
    if($filter==='market')return ['id'=>$c['mic_groups'][strtoupper(trim($raw))]??'unknown','reason'=>isset($c['mic_groups'][strtoupper(trim($raw))])?'mapped':'unmapped-mic'];
    if($filter==='sector'){
        $map=$kind==='equity'?$c['equity_sectors']:($kind==='etf'?$c['etf_categories']:[]);
        return ['id'=>$map[$key]??'sector:other','reason'=>isset($map[$key])?'mapped':($kind==='etf'?'non-sectoral-or-unmapped-etf':'unmapped-sector')];
    }
    throw new InvalidArgumentException('Filtre de métadonnées inconnu');
}
function secondary_metadata_legacy_id(string $filter,string $id): ?string {
    if(in_array($id,array_column(secondary_metadata_config()['groups'][$filter],'id'),true))return $id;
    if($id==='unknown')return $filter==='asset'?null:'unknown';
    if($filter==='sector'&&preg_match('/^(equity|etf):(.*)$/s',$id,$parts))return secondary_metadata_classify($filter,$parts[2],$parts[1])['id'];
    $prefix=$filter.':';
    $raw=str_starts_with($id,$prefix)?substr($id,strlen($prefix)):$id;
    return secondary_metadata_classify($filter,$raw)['id'];
}
/** Union migration: preserve exclusions where representable, never silently narrow a group. */
function secondary_metadata_selection(string $filter,array $selection): array {
    if(($selection['mode']??null)==='all')return ['mode'=>'all','selected'=>[]];
    $selected=[];
    foreach($selection['selected']??[] as $id){$group=secondary_metadata_legacy_id($filter,$id);if($group!==null&&!in_array($group,$selected,true))$selected[]=$group;}
    // The old artificial asset "unknown" cannot be represented by the two supported types.
    if($filter==='asset'&&($selection['selected']??[])&&!$selected)return ['mode'=>'all','selected'=>[]];
    return ['mode'=>'custom','selected'=>$selected];
}
/** Called under both settings row locks, exactly once per document version. */
function secondary_metadata_migrate(array &$definitions,array &$defaults): void {
    $canonical=secondary_proposed();
    if(($definitions['metadata_version']??0)<2){
        $previous=[];
        foreach($definitions['filters'] as &$f)if(!$f['editable']){
            $new=secondary_find($canonical,$f['id']);$previous[$f['id']]=$f;
            // These four definitions are read-only; activation remains a user setting.
            $enabled=$f['enabled'];$f=$new;$f['enabled']=$enabled;
        }unset($f);
        $definitions['metadata_version']=2;
        $definitions['metadata_migration']=['version'=>2,'previous'=>$previous];
    }
    if(($defaults['metadata_version']??0)<2){
        $previous=[];$notices=[];
        foreach(array_keys(secondary_metadata_config()['groups']) as $id){
            $old=$defaults['filters'][$id]['values'];$next=secondary_metadata_selection($id,$old);
            $previous[$id]=$old;$defaults['filters'][$id]['values']=$next;
            if($old!==$next)$notices[]=['filter_id'=>$id,'previous'=>$old,'selection'=>$next,'message'=>'Anciennes sélections regroupées. Un groupe peut inclure des valeurs supplémentaires ; vérifiez les défauts.'];
        }
        $defaults['metadata_version']=2;
        $defaults['metadata_migration']=['version'=>2,'previous'=>$previous,'notices'=>$notices];
    }
}
