"""Vérifie le rendu sans données, les inconnues et l'échappement, sans navigateur réseau."""
import pathlib
import subprocess


def test_fund_and_portfolio_render_without_fabricating_weights():
    path = pathlib.Path(__file__).resolve().parents[2] / 'app/public/assets/etf.js'
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const J={esc:s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;'),num:(x)=>String(x),date:s=>s,eur:x=>String(x)+' EUR'};
const ctx={window:{},J};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const E=ctx.window.JEtf;
let html=E.fund(null,{data:{holdings:[{name:'<script>',weight:null}],expense_ratio:null},fetched_at:'2026-10-29'});
assert(html.includes('Poids inconnu'));assert(html.includes('Non disponibles'));assert(html.includes('&lt;script&gt;'));assert(!html.includes('<script>'));
assert(E.similar(null).includes('pas encore préparée'));
html=E.portfolio({valuation_basis:'EUR',known_eur:25,unknown_eur:75,unknown_percent:75,unpriced_positions:0,sectors:[],similar_pairs:[],unavailable_pairs:1});
assert(html.includes('75 %'));assert(html.includes('1 paire(s)'));assert(html.includes('ne démontre pas'));
assert(E.concentration({sample:10,alerts:[{count:7,label:'Énergie (actions)',symbols:['A','B']}]}).includes('7 des 10'));
'''
    subprocess.run(['node', '-e', script, str(path)], check=True, capture_output=True, text=True)
