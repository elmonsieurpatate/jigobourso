/* Local SVG portfolio chart. Displays service results; no accounting or external dependency. */
(() => {
 const seconds=v=>typeof v==='number'?v:Date.parse(v.length===10?v+'T00:00:00Z':/[Z+-]\d?/.test(v.slice(10))?v:v.replace(' ','T')+'Z')/1000;
 J.financialTime=seconds;
 J.financialChart=(host,data,opts={})=>{
  if(host._financial)return host._financial.update(data,opts);
  host.innerHTML='<div class="fc-plot" tabindex="0" role="group" aria-label="Graphique : glisser pour agrandir, double-cliquer pour rétablir. Échap revient à la vue globale."><svg class="fc-svg" aria-label="Évolution financière"></svg><div class="fc-markers"></div><div class="fc-selection" hidden></div><div class="fc-tip" hidden role="status"></div></div>';
  const plot=host.firstElementChild,svg=plot.querySelector('svg'),layer=plot.querySelector('.fc-markers'),tip=plot.querySelector('.fc-tip'),selection=plot.querySelector('.fc-selection');
  let input,config,range,anchor=null,geometry,disposed=false,pinned=false;
  const fmtTime=t=>config.time?J.dateTime(new Date(t*1000).toISOString().slice(0,19)):J.date(new Date(t*1000).toISOString().slice(0,10));
  const esc=J.esc;
  function draw(){
   if(!input||!host.clientWidth)return;
   if(!input.times.length){svg.setAttribute('viewBox','0 0 300 240');svg.innerHTML='<text x="150" y="120" text-anchor="middle">Aucune observation disponible</text>';layer.innerHTML='';geometry=null;return}
   const w=host.clientWidth,h=config.height||300,left=w<500?56:70,right=18,top=35,bottom=32;
   const full={from:input.times[0],to:input.times.at(-1)},r=range||full,n=Math.max(1,r.to-r.from),x=t=>left+(t-r.from)/n*(w-left-right);
   const values=input.series.flatMap(s=>s.values.filter((v,i)=>Number.isFinite(v)&&input.times[i]>=r.from&&input.times[i]<=r.to));
   let lo=Math.min(0,...values),hi=Math.max(0,...values);if(hi===lo){hi+=1;lo-=1}
   const selected=input.series.find(s=>config.selected?.has(s.id));
   // Explicit focus fits the selected curve; other curves are clipped, never relabelled.
   if(selected){const v=selected.values.filter((v,i)=>Number.isFinite(v)&&input.times[i]>=r.from&&input.times[i]<=r.to);if(v.length){lo=Math.min(0,...v);hi=Math.max(0,...v);if(lo===hi){lo-=1;hi+=1}}}
   const pad=(hi-lo)*.08;lo-=pad;hi+=pad;const y=v=>h-bottom-(v-lo)/(hi-lo)*(h-top-bottom);
   geometry={w,h,left,right,top,bottom,x,y,r};svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.style.height=h+'px';plot.style.height=h+'px';
   let html='<defs><clipPath id="pf-clip"><rect x="'+left+'" y="'+top+'" width="'+(w-left-right)+'" height="'+(h-top-bottom)+'"/></clipPath></defs>';
   for(let k=0;k<5;k++){const v=lo+(hi-lo)*k/4,Y=y(v);html+=`<line x1="${left}" x2="${w-right}" y1="${Y}" y2="${Y}" stroke="var(--line)"/><text x="${left-7}" y="${Y+4}" text-anchor="end">${esc(config.format(v))}</text>`}
   for(let k=0;k<3;k++){const t=r.from+n*k/2;html+=`<text x="${x(t)}" y="${h-9}" text-anchor="${k===0?'start':k===2?'end':'middle'}">${esc(fmtTime(t))}</text>`}
   const ordered=[...input.series].sort((a,b)=>Number(config.selected?.has(a.id))-Number(config.selected?.has(b.id)));
   for(const s of ordered){let d='',pen=false;for(let i=0;i<input.times.length;i++){const t=input.times[i],v=s.values[i];if(!Number.isFinite(v)){pen=false;continue}d+=(pen?'L':'M')+x(t).toFixed(2)+' '+y(v).toFixed(2);pen=true}html+=`<path data-curve="${esc(s.id)}" d="${d}" clip-path="url(#pf-clip)" fill="none" stroke="${s.color}" stroke-width="${s.width||2}" vector-effect="non-scaling-stroke"/>`;const last=input.times.findLastIndex((t,i)=>t>=r.from&&t<=r.to&&Number.isFinite(s.values[i]));if(last>=0){html+=`<circle cx="${x(input.times[last])}" cy="${y(s.values[last])}" r="${config.selected?.has(s.id)?4:2.5}" fill="${s.color}" clip-path="url(#pf-clip)"/>`;if(config.selected?.has(s.id))html+=`<text x="${w-right-5}" y="${Math.max(top+12,Math.min(h-bottom-8,y(s.values[last])-8))}" text-anchor="end" fill="${s.color}">${esc(s.label)}</text>`}}
   if(!values.length)html+=`<text x="${w/2}" y="${h/2}" text-anchor="middle">Données indisponibles sur cette plage</text>`;
   svg.innerHTML=html;layer.innerHTML='';
   const groups=new Map();for(const m of config.markers||[]){const t=seconds(m.x);if(t<r.from||t>r.to)continue;if(!groups.has(t))groups.set(t,[]);groups.get(t).push(m)}
   let lane=0;for(const[t,items]of groups){const sell=items.some(m=>m.kind==='sell'),buy=items.some(m=>m.kind==='buy'),active=!config.selected?.size||items.some(m=>config.selected.has(m.key));const line=document.createElement('div');line.className='fc-trade-line'+(active?'':' dim');line.style.left=x(t)+'px';line.style.borderColor=sell?'#dc2626':'#15803d';if(sell&&buy)line.classList.add('mixed');const b=document.createElement('button');b.type='button';b.className='fc-buy-label'+(active?'':' dim');b.dataset.time=t;b.style.left=Math.max(left,Math.min(w-94,x(t)-18))+'px';b.style.top=(lane++%2?18:0)+'px';b.textContent=(buy?'Achat':'')+(buy&&sell?' / ':'')+(sell?'Vente':'')+' '+[...new Set(items.map(m=>m.symbol))].join(', ');b.style.color=sell?'#b91c1c':'#15803d';b.style.borderColor=b.style.color;b.setAttribute('aria-label',fmtTime(t)+' · '+b.textContent);const show=()=>{pinned=true;tip.innerHTML='<b>'+fmtTime(t)+'</b>'+items.map(m=>'<div><b>'+esc(m.label)+'</b><br>'+esc(m.detail)+'<br><button type="button" data-tx="'+Number(m.id)+'">Voir dans l’historique</button></div>').join('');tip.hidden=false;tip.style.left=Math.max(0,Math.min(w-tip.offsetWidth,x(t)))+'px';tip.querySelectorAll('[data-tx]').forEach(btn=>btn.onclick=()=>config.onTransaction?.(+btn.dataset.tx))};b.onclick=e=>{e.stopPropagation();show()};b.onmouseenter=show;b.onfocus=show;layer.append(line,b)}
  }
  const local=e=>({x:e.clientX-plot.getBoundingClientRect().left,y:e.clientY-plot.getBoundingClientRect().top});
  const commit=r=>{range=r;config.onRange?.(r);draw()};
  plot.onpointerdown=e=>{if(!geometry||e.target.closest('button,.fc-tip')||e.button>0)return;const p=local(e);if(p.x<geometry.left||p.y>geometry.h-geometry.bottom)return;pinned=false;tip.hidden=true;anchor={...p,curve:e.target.dataset.curve};plot.setPointerCapture(e.pointerId)};
  plot.onpointermove=e=>{const p=local(e);if(anchor){selection.hidden=false;selection.style.left=Math.min(anchor.x,p.x)+'px';selection.style.width=Math.abs(p.x-anchor.x)+'px';return}if(pinned||!geometry)return;const {r,x}=geometry,t=r.from+(p.x-geometry.left)/(geometry.w-geometry.left-geometry.right)*(r.to-r.from);let i=input.times.findIndex(v=>v>=t);if(i<0)i=input.times.length-1;if(i>0&&t-input.times[i-1]<input.times[i]-t)i--;if(i<0)return;tip.innerHTML='<b>'+fmtTime(input.times[i])+'</b>'+input.series.filter(s=>Number.isFinite(s.values[i])).map(s=>'<div><i style="background:'+s.color+'"></i>'+esc(s.label)+' <b>'+esc(config.format(s.values[i]))+'</b></div>').join('');tip.hidden=false;tip.style.left=Math.max(0,Math.min(geometry.w-tip.offsetWidth,p.x+8))+'px'};
  plot.onpointerup=e=>{if(!anchor)return;const p=local(e),a=anchor;anchor=null;selection.hidden=true;if(Math.abs(p.x-a.x)>12){const {r,left,right,w}=geometry,toTime=X=>r.from+(Math.max(left,Math.min(w-right,X))-left)/(w-left-right)*(r.to-r.from);commit({from:toTime(Math.min(a.x,p.x)),to:toTime(Math.max(a.x,p.x))});return}let nearest=a.curve||null,distance=15;for(const s of input.series)for(let i=0;i<input.times.length;i++){if(!Number.isFinite(s.values[i]))continue;const d=Math.hypot(geometry.x(input.times[i])-p.x,geometry.y(s.values[i])-p.y);if(d<distance){distance=d;nearest=s.id}}config.onSelect?.(nearest==='portfolio'?null:nearest)};
  plot.onpointercancel=()=>{anchor=null;selection.hidden=true};
  plot.ondblclick=e=>{if(e.target.closest('button'))return;pinned=false;range=null;config.onReset?.();draw()};
  plot.onkeydown=e=>{if(e.key==='Escape'){pinned=false;tip.hidden=true;config.onSelect?.(null)}if(e.key==='Home'){range=null;config.onReset?.();draw()}};
  plot.onpointerleave=()=>{if(!pinned)tip.hidden=true};
  const resize=new ResizeObserver(draw);resize.observe(host);
  const api={getRange:()=>range||{from:input.times[0],to:input.times.at(-1)},getState:()=>({range:api.getRange(),data:input}),destroy:()=>{disposed=true;resize.disconnect();host.innerHTML='';delete host._financial},update(next,options){if(disposed)return;input={...next,times:next.times.map(seconds)};config=options;range=options.view||null;pinned=false;tip.hidden=true;draw();return api}};
  host._financial=api;return api.update(data,opts);
 };
})();
