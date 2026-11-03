/* Portfolio-only adapter for TradingView Lightweight Charts 5.0.9 (Apache-2.0).
   Prices/results are supplied by the existing services; this module never calculates returns. */
(() => {
  const seconds=value=>{
    if(typeof value==='number')return value;
    const iso=value.length===10?value+'T00:00:00Z':value.replace(' ','T');
    return Math.floor(Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(iso)?iso:iso+'Z')/1000);
  };
  J.financialTime=seconds;
  J.financialChart=(host,data,opts={})=>{
    if(host._financial)return host._financial.update(data,opts);
    host.innerHTML='<div class="fc-toolbar"><button type="button" data-act="in" aria-label="Zoom avant">＋</button><button type="button" data-act="out" aria-label="Zoom arrière">−</button><button type="button" data-act="left" aria-label="Déplacer vers le passé">←</button><button type="button" data-act="right" aria-label="Déplacer vers le présent">→</button><button type="button" data-act="zone" aria-pressed="false">Zone</button><button type="button" data-act="reset">Réinitialiser</button></div><div class="fc-plot" role="group" aria-label="Graphique financier interactif"><div class="fc-canvas"></div><div class="fc-markers"></div><div class="fc-selection" hidden></div><div class="fc-tip" hidden role="status"></div></div><div class="fc-credit">TradingView Lightweight Charts™ · Copyright © 2025 <a href="https://www.tradingview.com/" target="_blank" rel="noopener">TradingView, Inc.</a></div>';
    const LC=window.LightweightCharts,plot=host.querySelector('.fc-plot'),canvas=host.querySelector('.fc-canvas'),layer=host.querySelector('.fc-markers'),tip=host.querySelector('.fc-tip'),selection=host.querySelector('.fc-selection');
    const chart=LC.createChart(canvas,{width:Math.max(240,host.clientWidth),height:300,layout:{background:{color:getComputedStyle(document.body).getPropertyValue('--surface').trim()||'#ffffff'},textColor:'#64748b',fontSize:11,attributionLogo:true},grid:{vertLines:{visible:false},horzLines:{color:'#e8edf5'}},rightPriceScale:{borderVisible:false},timeScale:{borderVisible:false,timeVisible:false,fixLeftEdge:true,fixRightEdge:true},crosshair:{mode:LC.CrosshairMode.Normal},handleScale:{mouseWheel:true,pinch:true,axisPressedMouseMove:true},handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false}});
    let config={},input={times:[],series:[]},series=new Map(),blocked=false,pinned=false,zone=false,anchor=null,rangeTimer;
    const timeScale=chart.timeScale();
    const fmtTime=t=>{const d=new Date(t*1000).toISOString();return config.time?J.dateTime(d.slice(0,19)):J.date(d.slice(0,10))};
    function getRange(){const r=timeScale.getVisibleLogicalRange();if(!r||!input.times.length)return null;const a=Math.max(0,Math.ceil(r.from)),b=Math.min(input.times.length-1,Math.floor(r.to));return a<=b?{from:input.times[a],to:input.times[b]}:null}
    function markerX(t){let x=timeScale.timeToCoordinate(t);if(x!==null)return x;const after=input.times.findIndex(v=>v>t);if(after<1)return null;const a=input.times[after-1],b=input.times[after];return timeScale.logicalToCoordinate(after-1+(t-a)/(b-a))}
    function showMarker(items,button){pinned=true;tip.innerHTML='<b>'+fmtTime(seconds(items[0].x))+'</b>'+items.map(m=>'<div><strong>'+J.esc(m.label)+'</strong><br>'+J.esc(m.detail||'')+'</div>').join('');tip.hidden=false;tip.style.left=Math.max(0,Math.min(plot.clientWidth-tip.offsetWidth,button.offsetLeft))+'px'}
    function markers(){
      const visible=timeScale.getVisibleLogicalRange();layer.innerHTML='';if(!visible)return;
      const groups=new Map();for(const m of config.markers||[]){const t=seconds(m.x);if(!groups.has(t))groups.set(t,[]);groups.get(t).push(m)}
      let lane=0;for(const[t,items]of groups){const x=markerX(t);if(x===null||x<0||x>plot.clientWidth-55)continue;
        const line=document.createElement('div');line.className='fc-buy-line';line.style.left=x+'px';
        const selected=(config.selected||new Set()),active=!selected.size||items.some(m=>selected.has(m.key));line.classList.toggle('dim',!active);
        const button=document.createElement('button');button.type='button';button.className='fc-buy-label';button.dataset.time=t;button.style.left=Math.max(0,Math.min(plot.clientWidth-130,x-30))+'px';button.style.top=(lane++%2?24:2)+'px';button.textContent='Achat '+[...new Set(items.map(m=>m.symbol))].join(', ');button.setAttribute('aria-label',fmtTime(t)+' · '+button.textContent);button.title=fmtTime(t);button.onclick=e=>{e.stopPropagation();showMarker(items,button)};button.onfocus=()=>showMarker(items,button);button.onkeydown=e=>{if(e.key==='Escape'){pinned=false;tip.hidden=true}};
        layer.append(line,button);
      }
    }
    chart.subscribeCrosshairMove(p=>{if(pinned)return;if(!p.time||!p.point){tip.hidden=true;return}const rows=[];for(const[id,s]of series){const v=p.seriesData.get(s);if(v&&Number.isFinite(v.value)){const item=input.series.find(x=>x.id===id);rows.push('<div><i style="background:'+item.color+'"></i>'+J.esc(item.label)+' <b>'+(config.format?config.format(v.value):J.num(v.value,2))+'</b></div>')}}tip.innerHTML='<b>'+fmtTime(p.time)+'</b>'+rows.join('');tip.hidden=!rows.length;tip.style.left=Math.max(0,Math.min(plot.clientWidth-tip.offsetWidth,p.point.x+12))+'px'});
    timeScale.subscribeVisibleLogicalRangeChange(()=>{markers();if(blocked)return;clearTimeout(rangeTimer);rangeTimer=setTimeout(()=>{const r=getRange();if(r&&config.onRange)config.onRange(r)},90)});
    function changeRange(factor,shift=0){const r=timeScale.getVisibleLogicalRange();if(!r)return;const n=r.to-r.from,center=(r.from+r.to)/2+shift*n;timeScale.setVisibleLogicalRange({from:center-n*factor/2,to:center+n*factor/2})}
    host.querySelectorAll('[data-act]').forEach(b=>b.onclick=()=>{pinned=false;tip.hidden=true;switch(b.dataset.act){case'in':changeRange(.65);break;case'out':changeRange(1.5);break;case'left':changeRange(1,-.25);break;case'right':changeRange(1,.25);break;case'reset':if(config.onReset)config.onReset();else timeScale.fitContent();break;case'zone':zone=!zone;b.setAttribute('aria-pressed',String(zone));chart.applyOptions({handleScroll:!zone});break}});
    plot.addEventListener('pointerdown',e=>{if(e.target.closest('button,.fc-tip'))return;pinned=false;tip.hidden=true;if(!zone)return;e.preventDefault();e.stopPropagation();anchor=e.clientX-plot.getBoundingClientRect().left;selection.hidden=false;selection.style.left=anchor+'px';selection.style.width='0px';plot.setPointerCapture(e.pointerId)},true);
    plot.addEventListener('pointermove',e=>{if(anchor===null)return;e.preventDefault();e.stopPropagation();const x=e.clientX-plot.getBoundingClientRect().left;selection.style.left=Math.min(anchor,x)+'px';selection.style.width=Math.abs(x-anchor)+'px'},true);
    plot.addEventListener('pointerup',e=>{if(anchor===null)return;const x=e.clientX-plot.getBoundingClientRect().left,a=timeScale.coordinateToLogical(Math.min(anchor,x)),b=timeScale.coordinateToLogical(Math.max(anchor,x));anchor=null;selection.hidden=true;zone=false;host.querySelector('[data-act="zone"]').setAttribute('aria-pressed','false');chart.applyOptions({handleScroll:true});if(a!==null&&b!==null&&b-a>1)timeScale.setVisibleLogicalRange({from:a,to:b});e.stopPropagation()},true);
    const resize=new ResizeObserver(()=>{if(host.isConnected&&host.clientWidth){chart.resize(host.clientWidth,config.height||300);markers()}});resize.observe(host);
    const api={chart,getRange,getState:()=>({range:getRange(),data:input}),destroy:()=>{clearTimeout(rangeTimer);resize.disconnect();chart.remove();delete host._financial},update(next,options){
      blocked=true;const previous=timeScale.getVisibleLogicalRange();config=options;input={...next,times:next.times.map(seconds)};pinned=false;tip.hidden=true;
      plot.style.height=(config.height||300)+'px';
      chart.applyOptions({height:config.height||300,timeScale:{timeVisible:!!config.time},localization:{locale:'fr-FR',priceFormatter:config.format||String}});
      for(const[id,s]of series){if(!next.series.some(x=>x.id===id)){chart.removeSeries(s);series.delete(id)}}
      const plotted=next.series.length?next.series:[{id:'empty',label:'Données indisponibles',color:'#94a3b8',values:[]}];
      for(const item of plotted){let s=series.get(item.id);if(!s){s=chart.addSeries(LC.LineSeries,{title:item.label,color:item.color,lineWidth:2,priceLineVisible:false,lastValueVisible:true});series.set(item.id,s)}s.applyOptions({color:item.color,lineWidth:Math.min(4,Math.round(item.width||2)),title:item.label,priceFormat:{type:'custom',minMove:.0001,formatter:config.format||String}});s.setData(input.times.map((t,i)=>Number.isFinite(item.values[i])?{time:t,value:item.values[i]}:{time:t}));}
      if(config.keepRange&&previous)timeScale.setVisibleLogicalRange(previous);else if(config.view)timeScale.setVisibleRange(config.view);else timeScale.fitContent();
      markers();setTimeout(()=>{blocked=false},0);return api;
    }};host._financial=api;return api.update(data,opts);
  };
})();
