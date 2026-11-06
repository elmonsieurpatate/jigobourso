/* Un seul stockage persistant : API PHP -> settings. L'export hors ligne reste explicite. */
(() => {
  'use strict';
  let state=null;
  const copy=x=>JSON.parse(JSON.stringify(x));
  function offlineState(){
    const filters=copy(window.AdminCategoryDemo.filters),defaults={schema:1,revision:1,filters:{}};
    for(const f of filters){
      if(!f.group)f.group=['volatility','liquidity','volume','positive','spikes','concentration'].includes(f.id)?'main':'other';
      defaults.filters[f.id]={};
      for(const m of f.measures)defaults.filters[f.id][m.id]={mode:'all',selected:[]};
      if(!f.editable){if(!Array.isArray(f.values))f.values=(f.examples||[]).map((x,i)=>({id:'demo-'+i,label:x,value:x}));delete f.examples;defaults.filters[f.id].values={mode:'all',selected:[]};}
    }
    return {schema:2,source:'offline',definitions:{schema:1,revision:1,filters},defaults};
  }
  async function load(){state=window.JigoSecondaryOffline?offlineState():await J.api('admin/secondary-filters');return copy(state);}
  async function write(request){
    if(!window.JigoSecondaryOffline){state=await J.post('admin/secondary-filters/save',request);return copy(state);}
    const id=request.filter_id,index=state.definitions.filters.findIndex(f=>f.id===id);
    if(request.action==='save'){const f=copy(request.filter);if(!f.editable)f.values=state.definitions.filters[index].values;state.definitions.filters[index]=f;state.definitions.revision++;}
    else if(request.action==='defaults'){state.defaults.filters[id][request.measure_id]=copy(request.selection);state.defaults.revision++;}
    else if(request.action==='restore'){
      const f=copy(window.AdminCategoryDemo.filters.find(f=>f.id===id));
      if(!f.editable){f.values=state.definitions.filters[index].values;delete f.examples;}
      state.definitions.filters[index]=f;state.defaults.filters[id]={};
      for(const m of f.measures)state.defaults.filters[id][m.id]={mode:'all',selected:[]};
      if(!f.editable)state.defaults.filters[id].values={mode:'all',selected:[]};
      state.definitions.revision++;state.defaults.revision++;
    }
    return copy(state);
  }
  const strip=f=>{const c=copy(f);delete c.values;delete c.examples;return c;};
  window.SecondaryFilterStore={load,
    save:filter=>write({action:'save',filter_id:filter.id,filter:strip(filter),revision:state.definitions.revision}),
    defaults:(id,measure,selection)=>write({action:'defaults',filter_id:id,measure_id:measure,selection,defaults_revision:state.defaults.revision}),
    restore:id=>write({action:'restore',filter_id:id,revision:state.definitions.revision,defaults_revision:state.defaults.revision})};
})();
