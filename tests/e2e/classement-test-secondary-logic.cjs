const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.join(__dirname,'../..'),sandbox={window:{},Intl};
vm.runInNewContext(fs.readFileSync(path.join(root,'app/public/assets/classement-test-filters.js'),'utf8'),sandbox);
const F=sandbox.window.ClassementTestSecondary,payload=JSON.parse(fs.readFileSync(path.join(root,'app/config/classement_test_categories.json'),'utf8')),cats=F.normalize(payload);
const freeze=x=>{if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
const rows=freeze([
 {id:1,rank:1,score:92,complex:81,categories:{volatility:{id:'c0'},turnover_eur:{id:'c0'}}},
 {id:2,rank:2,score:87,complex:90,categories:{volatility:{id:'c1'},turnover_eur:{id:'c1'}}},
 {id:3,rank:3,score:84,complex:null,categories:{volatility:{id:'c3'},turnover_eur:{id:'c1'}}},
 {id:4,rank:4,score:75,complex:70,categories:{}}
]);
const ids=rs=>Array.from(rs,r=>r.id),all=F.all(cats),before=JSON.stringify(rows);
assert.deepEqual(ids(F.apply(rows,all,cats)),[1,2,3,4]);
const selection=F.all(cats);selection.volatility=['c0','c1'];assert.deepEqual(ids(F.apply(rows,selection,cats)),[1,2]);
selection.turnover_eur=['c1'];let visible=F.apply(rows,selection,cats);assert.deepEqual(ids(visible),[2]);assert.equal(visible[0],rows[1]);
selection.volatility=['unknown'];selection.turnover_eur=cats.turnover_eur.options.map(o=>o.id);assert.deepEqual(ids(F.apply(rows,selection,cats)),[4]);
selection.volatility=[];assert.equal(F.apply(rows,selection,cats).length,0);
const changed=structuredClone(payload);changed.categories.volatility.bounds=[.5,1,2];changed.categories.volatility.labels[0]='Personnalisée admin';changed.categories.volatility.colors[0]='#abcdef';
const newCats=F.normalize(changed);assert.equal(newCats.volatility.options[0].label,'Personnalisée admin');assert.equal(newCats.volatility.options[0].color,'#abcdef');assert.match(newCats.volatility.options[0].range,/0,5/);
assert.deepEqual(ids(F.apply(rows,F.all(newCats),newCats)),[1,2,3,4]);assert.equal(JSON.stringify(rows),before);
const invalid=structuredClone(payload);invalid.categories.volatility.colors[0]='url(javascript:bad)';assert.throws(()=>F.normalize(invalid));
console.log('PASS: toutes catégories, OU intra-indicateur, ET inter-indicateurs, inconnu, sélection vide, configuration admin, scores/ordre/identité immuables, validation des couleurs.');
