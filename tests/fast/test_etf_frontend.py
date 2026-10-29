"""Rendu sans données, inconnues, échappement et accessibilité (un mot toujours accompagné de la couleur), sans navigateur réseau."""
import pathlib
import subprocess


def test_fund_pastilles_groups_and_portfolio_render_without_fabricating():
    path = pathlib.Path(__file__).resolve().parents[2] / 'app/public/assets/etf.js'
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const J={esc:s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),num:(x)=>String(x),date:s=>s,eur:x=>String(x)+' EUR'};
const ctx={window:{},J};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const E=ctx.window.JEtf;
let html=E.fund(null,{data:{holdings:[{name:'<script>',weight:null}],expense_ratio:null},fetched_at:'2026-10-29'});
assert(html.includes('Poids inconnu'));assert(html.includes('Non disponibles'));assert(html.includes('&lt;script&gt;'));assert(!html.includes('<script>'));
assert(html.includes('Dans quoi investit cet ETF ?'));assert(html.includes('Participations disponibles (1)'));assert(html.includes('ETF aux mouvements similaires'));
assert(E.similar(null).includes('pas encore préparée'));
// pastilles : toujours un mot visible, jamais la couleur seule
const s={key:'r',level:'warn',label:'Moyennement régulière',text:'La courbe suit une droite à 62 %.',tip:'Seuil 0,56'};
const dot=E.dot(s);assert(dot.includes('Moyennement régulière'));assert(dot.includes('sig warn'));assert(dot.includes('title='));
assert(E.rowSignals([s,s,s,s]).split('class="sig').length-1===3, 'trois pastilles au maximum par ligne');
assert(E.reading([s]).includes('Lecture rapide'));assert(E.reading([])==='');
// familles
const c={sample:10,analysed:8,groups:[{id:'A',size:6,symbols:['X','Y'],label:'Énergie',min_coefficient:.93,unstable:true}]};
html=E.concentration(c);assert(html.includes('6 des 10'));assert(html.includes('Groupe A'));assert(html.includes('instable'));assert(html.includes('2 ETF de la sélection sans analyse'));
assert(E.concentration({sample:10,groups:[]})==='');
// comparaison de jumeaux : inconnus affichés comme tels
const cmp={note:'n',rows:[{id:1,symbol:'A',mic:'XETR',currency:'EUR',expense_ratio:null,liquidity_eur_day:null,total_assets:null,yield:null,family:null},{id:2,symbol:'B',mic:'XETR',currency:'EUR',coefficient:.99,expense_ratio:.15,liquidity_eur_day:2e6,total_assets:1e9,yield:2.1,gap_log:.004,overlap:{shared_weight:52}}]};
html=E.compare(cmp);assert(html.includes('inconnus'));assert(html.includes('inconnue'));assert(html.includes('borne basse'));assert(html.includes('+0.4 pts'));
// portefeuille : part inconnue visible, familles pesées en valeur
html=E.portfolio({valuation_basis:'EUR',known_eur:25,unknown_eur:75,unknown_percent:75,unpriced_positions:0,sectors:[],similar_pairs:[],unavailable_pairs:1,families:[{symbols:['A','B'],value_eur:60,percent:60,min_coefficient:.95}],signals:[{key:'family',level:'bad',label:'Famille dominante',text:'60 %',tip:'t'}],etf_without_composition:[{symbol:'Z'}]});
assert(html.includes('75 %'));assert(html.includes('1 paire(s)'));assert(html.includes('ne démontre pas'));assert(html.includes('60 % du portefeuille'));assert(html.includes('Famille dominante'));assert(html.includes('Composition inconnue'));
'''
    subprocess.run(['node', '-e', script, str(path)], check=True, capture_output=True, text=True)
