"""Dépendances du moteur Python (F11) : aucun cycle d'import (imports différés compris) et couches respectées.

Graphe construit par analyse statique de tous les `import` de engine/ (en tête de module ou dans une fonction)."""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENGINE = os.path.join(ROOT, 'engine')


def modules():
    out = {}
    for base, _, files in os.walk(ENGINE):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(base, f)
                name = os.path.relpath(path, ROOT)[:-3].replace(os.sep, '.')
                out[name[:-9] if name.endswith('.__init__') else name] = path
    return out


MODS = modules()


def imports(name, path):
    """{module importé} ; les imports de paquets (from . import x) sont résolus vers le sous-module x s'il existe."""
    tree = ast.parse(open(path, encoding='utf-8').read())
    is_pkg = path.endswith('__init__.py')
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = name.split('.') if is_pkg else name.split('.')[:-1]
                parts = parts[:len(parts) - (node.level - 1)]
                base = '.'.join(parts + ([base] if base else []))
            for a in node.names:
                found.add(base + '.' + a.name if base + '.' + a.name in MODS else base)
    return found


GRAPH = {n: {t for t in imports(n, p) if t in MODS} for n, p in MODS.items()}
RAW = {n: imports(n, p) for n, p in MODS.items()}


def cycles():
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]

    def visit(v):
        index[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on.add(v)
        for w in GRAPH[v]:
            if w not in index:
                visit(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))
    for v in GRAPH:
        if v not in index:
            visit(v)
    return out


def test_no_import_cycle_even_with_deferred_imports():
    assert cycles() == []


def edges(src_prefix, dst_prefix):
    return sorted((s, t) for s, ts in GRAPH.items() if s.startswith(src_prefix) for t in ts if t.startswith(dst_prefix))


def test_calculation_packages_do_not_depend_on_administration():
    for pkg in ('series', 'scoring', 'explorer', 'market_views', 'portfolio'):
        assert edges('engine.analytics.' + pkg, 'engine.analytics.admin') == [], pkg


def test_providers_and_shared_code_do_not_depend_on_analytics_or_jobs():
    allowed = {('engine.market.splits', 'engine.analytics.series.series')}      # le fournisseur de splits applique le même ajustement de série que le calcul
    assert [e for e in edges('engine.market', 'engine.analytics') if e not in allowed] == []
    assert edges('engine.market', 'engine.jobs') == []
    assert edges('engine.shared', 'engine.analytics') == [] and edges('engine.shared', 'engine.jobs') == []


def test_pure_calculation_modules_use_neither_database_nor_network_nor_admin():
    pure = ['engine.analytics.series.series', 'engine.analytics.series.measures', 'engine.analytics.scoring.scores', 'engine.analytics.scoring.criteria',
            'engine.analytics.scoring.configurable_score', 'engine.analytics.explorer.explorer_config', 'engine.analytics.explorer.strategy',
            'engine.shared.units']
    forbidden = ('engine.shared.db', 'engine.market.yahoo', 'engine.analytics.admin', 'pymysql', 'urllib', 'socket', 'requests', 'http')
    bad = [(m, t) for m in pure for t in RAW[m] if t == 'http' or any(t == f or t.startswith(f + '.') for f in forbidden)]
    assert bad == []


def test_no_function_grows_beyond_the_current_ceiling():
    """Plafond de longueur des fonctions (lignes) : les plus longues font environ 100 lignes (strategy.rank, history.build, etf.build) ; aucune fonction ne doit dépasser 105."""
    longest = []
    for name, path in MODS.items():
        for node in ast.walk(ast.parse(open(path, encoding='utf-8').read())):
            if isinstance(node, ast.FunctionDef):
                longest.append((node.end_lineno - node.lineno + 1, name, node.name))
    assert max(longest)[0] <= 105, sorted(longest, reverse=True)[:3]
