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
          if(!c.active)continue;
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
  window.ClassementTestSecondary={normalize,all,apply,defaults};
})();
