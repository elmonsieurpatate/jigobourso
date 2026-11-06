/* Présentation seulement : les catégories proviennent de l'administration, jamais des curseurs. */
(() => {
  'use strict';
  const format = n => new Intl.NumberFormat('fr-FR',{maximumFractionDigits:6}).format(n);
  function normalize(payload) {
    if(payload?.schema===2&&payload.definitions){
      const out=Object.create(null);
      for(const f of payload.definitions.filters){
        if(!f.enabled)continue;
        const options=[];
        if(f.editable)for(const m of f.measures)for(const c of m.categories){
          const lo=c.min===null?'−∞':format(c.min),hi=c.max===null?'+∞':format(c.max);
          const interval=c.unknown?'Donnée indisponible':m.kind==='enum'?c.values.map(v=>m.domain.find(d=>d.value===v)?.label||v).join(', '):`${c.min!==null&&c.minIncluded?'[':']'} ${lo} ; ${hi} ${c.max!==null&&c.maxIncluded?']':'['} ${m.unit}`;
          options.push({id:m.id+'::'+c.id,categoryId:c.id,measure:m.id,label:(f.measures.length>1?m.name+' · ':'')+c.name,color:c.color,range:interval,description:c.description||''});
        }
        else for(const v of f.values)options.push({id:v.id,categoryId:v.id,measure:'values',label:v.label,color:'#64748b',range:v.value===null?'Donnée indisponible':f.provenance,description:f.provenance});
        out[f.id]={label:f.name,unit:f.editable?'':f.provenance,options,configurationOnly:true};
      }
      return out;
    }
    if (!payload || !payload.categories || typeof payload.categories !== 'object') throw Error('Configuration des catégories absente');
    const result=Object.create(null);
    for (const [key,c] of Object.entries(payload.categories)) {
      if (!/^[a-z][a-z0-9_]*$/.test(key) || !c || typeof c.label!=='string' || !c.label.trim() || typeof c.unit!=='string' || !Array.isArray(c.bounds) || !Array.isArray(c.labels) || !Array.isArray(c.colors) || c.labels.length!==c.bounds.length+1 || c.colors.length!==c.labels.length || c.bounds.some((v,i)=>!Number.isFinite(v)||(i>0&&v<=c.bounds[i-1])) || c.labels.some(v=>typeof v!=='string'||!v.trim()) || c.colors.some(v=>!/^#[a-f0-9]{6}$/i.test(v))) throw Error('Configuration des catégories invalide : '+key);
      const options=c.labels.map((label,i)=>({id:'c'+i,label,color:c.colors[i],range:(i===0?'≤ '+format(c.bounds[0]):i===c.bounds.length?'> '+format(c.bounds[i-1]):'> '+format(c.bounds[i-1])+' à ≤ '+format(c.bounds[i]))+' '+c.unit}));
      if (c.unknown_label) {
        if(typeof c.unknown_label!=='string'||!/^#[a-f0-9]{6}$/i.test(c.unknown_color||'')) throw Error('Catégorie inconnue invalide : '+key);
        options.push({id:'unknown',label:c.unknown_label,color:c.unknown_color,range:'Donnée indisponible'});
      }
      result[key]={label:c.label,unit:c.unit,options};
    }
    if(!Object.keys(result).length) throw Error('Aucune catégorie configurée');
    return result;
  }
  function all(categories) {return Object.fromEntries(Object.entries(categories).map(([k,c])=>[k,c.options.map(o=>o.id)]));}
  // Ne trie, ne recalcule, ne clone ni ne modifie les lignes et leurs scores.
  function apply(rows,selections,categories) {
    if(Object.values(categories).some(c=>c.configurationOnly))return [...rows];
    return rows.filter(row=>Object.entries(categories).every(([key,c])=>{
      const selected=selections[key]||c.options.map(o=>o.id);
      if(c.options.every(o=>selected.includes(o.id))) return true;
      const id=row.categories?.[key]?.id??row.categories?.[key]??'unknown';
      return selected.includes(id);
    }));
  }
  function defaults(payload,categories){
    if(payload?.schema!==2)return all(categories);
    return Object.fromEntries(Object.entries(categories).map(([key,c])=>[key,c.options.filter(o=>{
      const s=payload.defaults.filters[key]?.[o.measure];return !s||s.mode==='all'||s.selected.includes(o.categoryId);
    }).map(o=>o.id)]));
  }
  function metadataLegacyId(mapping,key,id){
    if(mapping.groups[key].some(v=>v.id===id))return id;
    if(id==='unknown')return key==='asset'?null:'unknown';
    const norm=v=>v.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ');
    const raw=id.startsWith(key+':')?id.slice(key.length+1):id;
    const lookup=(map,key,fallback)=>Object.prototype.hasOwnProperty.call(map,key)?map[key]:fallback;
    const missing=v=>['','unknown','inconnu','inconnue','n/a','n.a.','none','null','not available','unavailable','-','—'].includes(v);
    if(key==='asset')return ['equity','etf'].includes(norm(raw))?'asset:'+norm(raw):null;
    if(key==='country')return missing(norm(raw))?'unknown':lookup(mapping.country_aliases,norm(raw),'country:other');
    if(key==='market')return lookup(mapping.mic_groups,raw.trim().toUpperCase(),'unknown');
    const match=/^(equity|etf):(.*)$/s.exec(id),value=norm(match?match[2]:raw);
    if(missing(value))return 'unknown';
    return lookup(match?.[1]==='equity'?mapping.equity_sectors:match?.[1]==='etf'?mapping.etf_categories:{},value,'sector:other');
  }
  function migrateOverrides(payload,overrides){
    const mapping=payload.metadata_mapping;if(!mapping)return {overrides,notices:[],previous:{}};
    const next={...overrides},notices=[],previous={};
    for(const [key,groups] of Object.entries(mapping.groups)){
      const own=next[key];if(!own||own.metadataVersion===mapping.version)continue;
      const map=ids=>[...new Set(ids.filter(id=>typeof id==='string').map(id=>metadataLegacyId(mapping,key,id)).filter(id=>id!==null))];
      let selected=map(own.selected);
      if(key==='asset'&&own.selected.length&&!selected.length)selected=groups.map(v=>v.id);
      // Mark the entire new domain known: new groups must not silently join a restrictive preference.
      const known=groups.map(v=>v.id);next[key]={...own,selected,known,metadataVersion:mapping.version};
      previous[key]=own;
      if(JSON.stringify(own.selected)!==JSON.stringify(selected))notices.push(key);
    }
    return {overrides:next,notices,previous};
  }
  window.ClassementTestSecondary={normalize,all,apply,defaults,migrateOverrides,metadataLegacyId};
})();
