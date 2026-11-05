/* Modèle local de maquette. Les contrôles ne modifient aucune mesure ni aucun score. */
(() => {
  'use strict';
  const copy = x => JSON.parse(JSON.stringify(x));
  function validate(indicator,categories) {
    const errors={},warnings=[];
    const add=(id,field,message)=>{errors[id]=errors[id]||{};errors[id][field]=message;};
    const names=new Map();let unknownCount=0;
    for(const c of categories){
      const name=typeof c.name==='string'?c.name.trim():'';
      if(!name||name.length>80)add(c.id,'name','Saisissez un nom de 1 à 80 caractères.');
      const normalized=name.toLocaleLowerCase('fr');
      if(names.has(normalized)){add(c.id,'name','Ce nom est déjà utilisé pour cet indicateur.');add(names.get(normalized),'name','Ce nom est utilisé par plusieurs catégories.');}else names.set(normalized,c.id);
      if(c.description!==undefined&&(typeof c.description!=='string'||c.description.length>180))add(c.id,'description','L’explication doit comporter au maximum 180 caractères.');
      if(!/^#[0-9a-f]{6}$/i.test(c.color||''))add(c.id,'color','Utilisez une couleur #RRGGBB.');
      if(c.unknown){unknownCount++;if(!indicator.supportsUnknown)add(c.id,'unknown','Cet indicateur ne prévoit pas de catégorie inconnue.');if(c.min!==null||c.max!==null||(c.values||[]).length)add(c.id,'unknown','Une catégorie inconnue ne possède ni borne ni valeur.');continue;}
      if(indicator.kind==='enum'){
        if(!Array.isArray(c.values)||!c.values.length||c.values.some(v=>!indicator.domain.some(d=>d.value===v)))add(c.id,'values','Sélectionnez au moins une valeur disponible.');
      }else{
        if(c.min!==null&&!Number.isFinite(c.min))add(c.id,'min','Saisissez un nombre valide ou laissez la borne vide.');
        if(c.max!==null&&!Number.isFinite(c.max))add(c.id,'max','Saisissez un nombre valide ou laissez la borne vide.');
        if(Number.isFinite(c.min)&&Number.isFinite(c.max)&&(c.min>c.max||(c.min===c.max&&!(c.minIncluded&&c.maxIncluded)))){add(c.id,'min','Le minimum doit précéder le maximum (ou former un point fermé).');add(c.id,'max','Intervalle vide ou inversé.');}
      }
    }
    if(unknownCount>1)categories.filter(c=>c.unknown).forEach(c=>add(c.id,'unknown','Une seule catégorie « Inconnue » est autorisée.'));
    if(indicator.supportsUnknown&&!categories.some(c=>c.unknown&&c.active))warnings.push('Les données absentes ne disposent d’aucune catégorie inconnue active.');
    const active=categories.filter(c=>c.active&&!c.unknown);
    if(indicator.kind==='enum'){
      for(const d of indicator.domain){const own=active.filter(c=>(c.values||[]).includes(d.value));if(own.length>1)own.forEach(c=>add(c.id,'values',`La valeur « ${d.label} » est également utilisée ailleurs.`));else if(!own.length)warnings.push(`Valeur non couverte : ${d.label}.`);}
    }else{
      const valid=active.filter(c=>(c.min===null||Number.isFinite(c.min))&&(c.max===null||Number.isFinite(c.max))&&!errors[c.id]?.min&&!errors[c.id]?.max);
      for(let i=0;i<valid.length;i++)for(let j=i+1;j<valid.length;j++){
        const a=valid[i],b=valid[j],lo=Math.max(a.min??-Infinity,b.min??-Infinity),hi=Math.min(a.max??Infinity,b.max??Infinity);
        const includes=(c,v)=>(c.min===null||v>c.min||(v===c.min&&c.minIncluded))&&(c.max===null||v<c.max||(v===c.max&&c.maxIncluded));
        if(lo<hi||(lo===hi&&Number.isFinite(lo)&&includes(a,lo)&&includes(b,lo))){for(const c of[a,b]){const other=c===a?b:a;add(c.id,'min',`Chevauchement avec « ${other.name} ».`);add(c.id,'max',`Chevauchement avec « ${other.name} ».`);}}
      }
      const sorted=[...valid].sort((a,b)=>(a.min??-Infinity)-(b.min??-Infinity));
      if(!sorted.length)warnings.push('Aucune plage numérique active.');
      else{
        if(sorted[0].min!==null)warnings.push(`Valeurs inférieures à ${sorted[0].min} non couvertes${sorted[0].minIncluded?'':' (borne comprise)'}.`);
        let edge=sorted[0].max??Infinity,included=sorted[0].maxIncluded;
        for(const c of sorted.slice(1)){const lo=c.min??-Infinity;if(lo>edge||(lo===edge&&!included&&!c.minIncluded))warnings.push(`Intervalle non couvert entre ${edge} et ${lo}.`);const hi=c.max??Infinity;if(hi>edge){edge=hi;included=c.maxIncluded;}else if(hi===edge)included=included||c.maxIncluded;}
        if(edge!==Infinity)warnings.push(`Valeurs supérieures à ${edge} non couvertes${included?'':' (borne comprise)'}.`);
      }
    }
    return {valid:Object.keys(errors).length===0,errors,warnings:[...new Set(warnings)]};
  }
  const format = n => new Intl.NumberFormat('fr-FR',{maximumFractionDigits:6}).format(n);
  function interval(c,indicator){
    if(c.unknown)return 'Donnée absente';
    if(indicator.kind==='enum')return (c.values||[]).map(v=>indicator.domain.find(d=>d.value===v)?.label||v).join(', ');
    return `${c.min!==null&&c.minIncluded?'[':']'} ${c.min===null?'−∞':format(c.min)} ; ${c.max===null?'+∞':format(c.max)} ${c.max!==null&&c.maxIncluded?']':'['}`;
  }
  window.AdminCategoryModel={copy,validate,interval,format};
})();
