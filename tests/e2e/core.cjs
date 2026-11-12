// Noyau JS commun (app/public/assets/core.js) : formats, signes, stockage, construction DOM. Sans navigateur.
const assert = require('assert'), fs = require('fs'), vm = require('vm'), path = require('path');
const data = {};
const ls = { getItem: k => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, removeItem: k => { delete data[k]; } };
class El { constructor(t) { this.tag = t; this.children = []; this.attrs = {}; this.style = {}; this.dataset = {}; this.id = ''; this.className = ''; this.listeners = {};
  this.classList = { add: c => { this.className += (this.className ? ' ' : '') + c; } }; }
  setAttribute(k, v) { this.attrs[k] = v; } addEventListener(e, f) { this.listeners[e] = f; } append(...c) { this.children.push(...c); } }
const win = { addEventListener() {}, localStorage: ls };
const ctx = { window: win, localStorage: ls, Node: El, document: { createElement: t => new El(t), createTextNode: t => ({ text: String(t) }) }, Intl, Date, URLSearchParams, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/public/assets/core.js'), 'utf8'), ctx);
const J = win.J;
const eq = (a, b, m) => assert.strictEqual(JSON.stringify(a), JSON.stringify(b), m);   // objets d'un autre contexte vm : comparaison par JSON
const nb = s => s.replace(/[  ]/g, ' ');           // espaces insécables de Intl

// formats
assert.strictEqual(nb(J.num(1234.5, 2)), '1 234,50');
assert.strictEqual(J.num(null), '–');  assert.strictEqual(J.num(undefined), '–');  assert.strictEqual(J.num(NaN), '–');
assert.strictEqual(J.num(1.23456, 2, 3), '1,235');  assert.strictEqual(J.num(1.2, 2, 3), '1,20');
assert.strictEqual(nb(J.int(1234.6)), '1 235');
assert.strictEqual(nb(J.eur(12.3)), '12,30 €');
assert.strictEqual(J.pctS(1.234), '+1,23 %');  assert.strictEqual(J.pctS(-1.234), '−1,23 %');  assert.strictEqual(J.pctS(0.001), '0,00 %');
assert.strictEqual(J.pctS(5, 1, false), '5,0 %');  assert.strictEqual(J.pctS(null), '–');
assert.strictEqual(J.numS(-0.4), '−0,40');  assert.strictEqual(nb(J.eurS(-12)), '−12,00 €');
assert.ok(J.isNum(0) && !J.isNum(NaN) && !J.isNum('1') && !J.isNum(Infinity));
assert.strictEqual(J.esc('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
assert.strictEqual(J.esc(null), '');

// stockage
eq(J.store.get('absent'), null);  assert.strictEqual(J.store.get('absent', 7), 7);
J.store.set('k', { a: 1 });  eq(J.store.get('k'), { a: 1 });  assert.ok(J.store.has('k'));
let seen = null; const off = J.store.subscribe('k', v => { seen = v; });
J.store.set('k', [2]);  eq(seen, [2]);  off();  J.store.set('k', [3]);  eq(seen, [2], 'désabonné');
J.store.remove('k');  assert.ok(!J.store.has('k'));
data.broken = '{pas du json';  assert.strictEqual(J.store.get('broken', 'repli'), 'repli');
const fn = J.store.fn('p_');  fn('x', { v: 1 });  eq(fn('x'), { v: 1 });  assert.ok('p_x' in data);
J.store.text.set('t', 'abc');  assert.strictEqual(J.store.text.get('t'), 'abc');
const boom = { ...ls, setItem() { throw new Error('quota'); }, getItem() { throw new Error('refus'); } };   // stockage indisponible : jamais d'exception
ctx.localStorage = boom;  win.localStorage = boom;
assert.doesNotThrow(() => { J.store.set('m', 1); });  assert.strictEqual(J.store.get('m'), 1, 'repli en mémoire');

// DOM
const el = J.dom.h('button.btn.primary#go', { type: 'button', 'aria-label': 'Aller', dataset: { id: '7' }, on: { click: () => 1 }, disabled: false }, 'Go', null, ['x', 2]);
assert.strictEqual(el.tag, 'button');  assert.strictEqual(el.id, 'go');  assert.strictEqual(el.className, 'btn primary');
assert.strictEqual(el.attrs.type, 'button');  assert.ok(!('disabled' in el.attrs));  assert.strictEqual(el.dataset.id, '7');
assert.strictEqual(el.children.map(c => c.text).join(''), 'Gox2');  assert.ok(el.listeners.click);
assert.strictEqual(J.dom.h('p', 'texte').children[0].text, 'texte', 'enfants sans attributs');
console.log('core.js : OK');
