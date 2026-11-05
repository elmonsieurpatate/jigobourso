/* Jeu entièrement fictif et déterministe. Aucune source de cours ni formule de score. */
(() => {
  'use strict';
  const examples = [
    ['NVDA','NVIDIA',149.32,2.84,1.21,.98,1.84,8.2,92],
    ['MSFT','Microsoft',414.67,1.56,.78,.97,1.69,9.1,88],
    ['AAPL','Apple',208.14,1.23,.62,.95,1.76,9.8,85],
    ['AMZN','Amazon',176.21,1.11,.55,.93,1.91,12.3,82],
    ['GOOGL','Alphabet',152.33,.98,.48,.92,1.78,13.1,79],
    ['META','Meta Platforms',512.67,.91,.44,.91,2.01,13.9,77],
    ['TSLA','Tesla',239.50,.87,.41,.89,2.87,14.5,75],
    ['AVGO','Broadcom',1287.40,.80,.39,.88,2.19,9.9,73],
    ['ASML','ASML',684.10,.74,.36,.87,2.25,12.6,71],
    ['MC.PA','LVMH',698.20,.69,.33,.86,1.86,10.2,69],
    ['SAP.DE','SAP',193.80,.64,.30,.85,1.35,6.4,68],
    ['OR.PA','L’Oréal',354.70,.58,.28,.84,1.48,7.1,67],
    ['AIR.PA','Airbus',142.32,.52,.26,.83,1.72,11.3,66],
    ['SU.PA','Schneider Electric',224.15,.44,.24,.82,1.54,8.4,65],
    ['V','Visa',278.45,.38,.22,.81,1.18,5.8,64],
    ['MA','Mastercard',467.20,.31,.20,.80,1.26,6.2,63],
    ['COST','Costco',878.40,.24,.18,.79,1.43,8.7,62],
    ['LLY','Eli Lilly',812.75,.18,.16,.78,2.12,15.6,61],
    ['NFLX','Netflix',674.10,.12,.14,.77,2.46,18.2,60],
    ['ADBE','Adobe',428.30,.05,.12,.76,2.78,22.1,59],
    ['RMS.PA','Hermès',2028.00,0,.10,.75,1.61,9.4,58],
    ['SAN.PA','Sanofi',93.25,-.14,.08,.73,1.09,6.8,56],
    ['TTE.PA','TotalEnergies',58.64,-.28,.06,.70,1.83,12.7,54],
    ['NKE','Nike',76.80,-.43,.04,.67,2.34,24.8,52],
    ['DIS','Walt Disney',96.32,-.61,.02,.62,2.08,17.6,49],
    ['PFE','Pfizer',26.84,-.82,-.03,.58,2.55,28.4,46],
    ['INTC','Intel',22.41,-1.14,-.08,.53,3.81,36.5,42],
    ['BA','Boeing',156.48,-1.62,-.14,.48,3.26,31.2,38],
    ['BABA','Alibaba',84.25,-2.08,-.22,.43,4.12,42.6,33],
    ['DEMO','Exemple données incomplètes',null,null,null,null,null,null,27]
  ];
  const freeze = x => { if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x; };
  function rows(payload) {
    return freeze(examples.map(([symbol,name,price,change,slope,r2,volatility,drawdown,score],i)=>{
      const avgVolume=i===29?null:[12500000,2400000,450000,65000,8000][i%5];
      const turnover=price!==null?price*avgVolume:null;
      const secondary={volatility,turnover_eur:turnover,quoted_turnover:null,avg_volume:avgVolume,up_fraction:i===29?null:.8-i*.015,largest_day:i===29?null:2.8+(i%7),worst_day:i===29?null:-2.2-i*.19,gain_share:i===29?null:12+i*1.7,gain_net_share:i===29?null:18+i*3.1,log_net_share:i===29?null:17+i*2.8,drawdown,current_drawdown:i===29?null:drawdown*.45,er:i===29?null:.86-i*.038,perf:i===29?null:25-i*1.4,coverage:i===29?.6:1,freshness:i===29?1:0,quality:i===29?1:0};
      const categories={};
      for(const [key,c] of Object.entries(payload.categories)) {
        const value=secondary[key];
        const index=Number.isFinite(value)?c.bounds.findIndex(b=>value<=b):-1;
        categories[key]={id:Number.isFinite(value)?'c'+(index<0?c.bounds.length:index):'unknown'};
      }
      const points=i===29?[]:Array.from({length:21},(_,n)=>100+(slope>0?1:-1)*n*(.25+Math.abs(slope)) + [0,.5,-.3,.7,-.2][(n+i)%5]);
      return {id:i+1,rank:i+1,symbol,name,price,change,slope,r2,volatility,drawdown,turnover,avgVolume,score,categories,secondary,points,color:['#76b900','#2875dc','#68758c','#dc9234','#4285c7','#4267d5','#c43d4a','#bd3f4e','#2855a2','#433c68'][i%10]};
    }));
  }
  window.ClassementTestDemo={rows};
})();
