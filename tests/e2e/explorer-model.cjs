// Logique pure du classement (explorer-model.js) sous Node, sans navigateur : arbre de règles, projection Simple, sauvegarde locale, filtres, lignes.
const assert = require('assert'), fs = require('fs'), vm = require('vm'), path = require('path');
const win = {}; const ctx = { window: win, console }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/public/assets/explorer-model.js'), 'utf8'), ctx);
const M = win.ExplorerModel, eq = (a, b, m) => assert.strictEqual(JSON.stringify(a), JSON.stringify(b), m); // JSON : les objets du contexte vm n'ont pas les mêmes prototypes

// profils : valeurs du moteur reprises, périodes actives sans critère à 0
const profiles = M.profilesFrom({ fast: { periods: { week: { slope: .3, r2: .5 }, month: { slope: .2, r2: .4, max_volatility: 3 } } } });
eq(profiles.fast.per, { week: [.3, .5], month: [.2, .4] });
eq(profiles.fast.extra, [['volatility', '<=', 3, 'month']]);
eq(profiles.regular.per, { month: [0, 0], quarter: [0, 0] }, 'repli quand le moteur ne répond pas');

// configuration d'origine : seules les périodes du profil sont actives, « Jour » toujours éteint
const c = M.fresh(profiles, 'fast');
assert.ok(c.periods.week.enabled && c.periods.month.enabled && !c.periods.day.enabled && !c.periods.year.enabled);
assert.strictEqual(c.extra.length, 1);

// arbre : construit depuis les périodes actives, stable, projeté sur les curseurs du mode Simple
const t = M.ensureTree(c);
assert.strictEqual(t.kind, 'group'); assert.strictEqual(M.ensureTree(c), t);
assert.strictEqual(M.leaves(t).length, 5, '2 périodes × (pente, R²) + 1 règle de volatilité');
assert.ok(M.simpleCompatible(c));
M.setSimpleValue(c, 'week', 'slope', .9);
assert.strictEqual(c.periods.week.slope, .9);
assert.strictEqual(M.at(t, '0').value, .9);
M.activatePeriod(c, 'week', false);
assert.ok(!c.periods.week.enabled && M.leaves(t).every(l => l.node.period !== 'week' || !M.isPrimary(l.node)));
M.activatePeriod(c, 'day', true);
assert.ok(c.periods.day.enabled);

// un OU parmi les critères principaux ne se représente plus par deux minimums
M.at(t, '').join = 'or'; assert.ok(!M.simpleCompatible(c));
M.at(t, '').join = 'and';
assert.ok(M.isTreeValid(t));
t.children.push(M.group([]));
assert.ok(!M.isTreeValid(t), 'groupe vide');
assert.ok(!M.validTree({ kind: 'rule', metric: 'inconnue', op: '>=', period: 'week', value: 1 }));

// sauvegarde locale : reprise seulement si complète et dans les bornes
const full = M.profilesFrom(Object.fromEntries(Object.keys(profiles).map(id => [id, { periods: Object.fromEntries(Object.keys(profiles[id].per).map(k => [k, { slope: .3, r2: .5 }])) }])));   // seuils > 0 : une pente nulle n'est pas une sauvegarde valide
const mk = () => ({ mode: 'simple', strategy: 'fast', selected: 'week', filters: {}, profiles: Object.fromEntries(Object.keys(full).map(id => [id, M.fresh(full, id)])) });
assert.ok(M.isValidSaved(mk(), full));
const bad = mk(); bad.profiles.fast.periods.week.slope = 5; assert.ok(!M.isValidSaved(bad, full));
assert.ok(!M.isValidSaved(null, full));
const noFilters = mk(); delete noFilters.filters; assert.ok(!M.isValidSaved(noFilters, full));

// filtres : un choix enregistré garde ses ids ; les catégories nouvelles suivent les défauts de l'administration
const cats = { vol: { options: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] } };
eq(M.filtersFor({ vol: { selected: ['a'], known: ['a', 'b'] } }, cats, { vol: ['b', 'c'] }).vol.sort(), ['a', 'c']);
eq(M.filtersFor({}, cats, { vol: ['b'] }).vol, ['b']);
assert.strictEqual(M.number('', 0, 5, 3), 3); assert.strictEqual(M.number('1,5', 0, 5, 3), 1.5); assert.strictEqual(M.number('9', 0, 5, 3), 5);

// catégories : une mesure à seuils, un groupe
const cat = M.categories([{ id: 'f', editable: true, measures: [{ id: 'm', kind: 'range', categories: [{ id: 'lo', min: null, max: 10, maxIncluded: false }, { id: 'hi', min: 10, minIncluded: true, max: null }, { id: 'na', unknown: true }] }] }, { id: 'country', measures: [] }]);
assert.strictEqual(cat.categoryOf('m', 5).id, 'lo'); assert.strictEqual(cat.categoryOf('m', 10).id, 'hi'); assert.strictEqual(cat.categoryOf('m', null).id, 'na'); assert.strictEqual(cat.categoryOf('zzz', 1), null);
const row = { secondary: { m: 12 }, group: { country: 'FR' } };
eq(cat.rowOptions(row, 'f'), ['m::hi']); eq(cat.rowOptions(row, 'country'), ['FR']);

// lignes : champs du serveur → champs d'affichage, valeur absente = null (jamais 0)
const r = M.toRow({ id: 7, symbol: 'AB', name: 'Ab', rank_complex: 3, rank_simple: 4, pos_simple: 2, pos_complex: 1, price_eur: 10, perf: { month: 2 }, extra: {}, simple: 50, complex: 60 });
assert.strictEqual(r.rankComplex, 3); assert.strictEqual(r.status, 'undetermined'); assert.strictEqual(r.perfMonth, 2); assert.strictEqual(r.secondary['perf-week'], null); assert.strictEqual(r.secondary.up_fraction, null);
assert.ok(/^hsl\(/.test(r.color)); assert.strictEqual(M.ctxKey('abc'), M.ctxKey('abc'));

// tri : « simple »/« complex » classent par position (la meilleure d'abord) ; les rangs suivent la clé choisie
const REG = M.registry(() => 'rankSimple');
assert.strictEqual(REG.rank.val({ rankSimple: 9 }), 9); assert.strictEqual(REG.simple.val({ posSimple: 2 }), -2); assert.strictEqual(REG.simple.val({ posSimple: null }), null);
assert.ok(REG.trend.nosort); assert.strictEqual(REG.slope_quarter.val({ periods: { 63: { slope: .4 } } }), .4);
assert.strictEqual(REG.status.val({ status: 'excluded' }), 2);
console.log('explorer-model.js : OK');
