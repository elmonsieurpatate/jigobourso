"""Cohérence `db/schema.sql` ↔ `db/migrations/` : tout ce qu'une migration ajoute doit exister dans l'installation neuve."""
import os
import re
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA = open(os.path.join(ROOT, 'db', 'schema.sql'), encoding='utf-8').read()
MIGRATIONS = sorted(f for f in os.listdir(os.path.join(ROOT, 'db', 'migrations')) if f.endswith('.sql'))


def strip(sql):
    return re.sub(r'/\*.*?\*/', '', re.sub(r'--[^\n]*', '', sql), flags=re.S)


def tables(sql):
    """nom de table -> corps de sa définition (parenthèses équilibrées)."""
    out = {}
    for m in re.finditer(r'CREATE TABLE(?: IF NOT EXISTS)?\s+`?(\w+)`?\s*\(', sql, re.I):
        depth, i = 1, m.end()
        while depth and i < len(sql):
            depth += {'(': 1, ')': -1}.get(sql[i], 0)
            i += 1
        out[m.group(1).lower()] = sql[m.end():i - 1]
    return out


SCHEMA_TABLES = tables(strip(SCHEMA))


def column_names(body):
    return {m.group(1).lower() for m in re.finditer(r'^\s*`?(\w+)`?\s+(?!KEY\b|PRIMARY\b|UNIQUE\b|CONSTRAINT\b|INDEX\b|FOREIGN\b)\w', body, re.M)}


def index_names(body):
    return {m.group(1).lower() for m in re.finditer(r'(?:UNIQUE\s+)?(?:KEY|INDEX)\s+`?(\w+)`?', body, re.I)} | \
           {m.group(1).lower() for m in re.finditer(r'CONSTRAINT\s+`?(\w+)`?', body, re.I)}


def test_schema_declares_tables():
    assert len(SCHEMA_TABLES) > 20 and 'jobs' in SCHEMA_TABLES


@pytest.mark.parametrize('name', MIGRATIONS)
def test_migration_is_reflected_in_schema(name):
    sql = strip(open(os.path.join(ROOT, 'db', 'migrations', name), encoding='utf-8').read())
    missing = []
    for table, body in tables(sql).items():
        if table not in SCHEMA_TABLES:
            missing.append(f'table {table}')
            continue
        missing += [f'{table}.{c}' for c in column_names(body) - column_names(SCHEMA_TABLES[table])]
        missing += [f'{table} index {i}' for i in index_names(body) - index_names(SCHEMA_TABLES[table])]
    for m in re.finditer(r'ALTER\s+TABLE\s+`?(\w+)`?\s+([^;]+);', sql, re.I):
        table, clauses = m.group(1).lower(), m.group(2)
        if table not in SCHEMA_TABLES:
            missing.append(f'table {table}')
            continue
        body = SCHEMA_TABLES[table]
        for c in re.finditer(r'ADD\s+COLUMN\s+`?(\w+)`?', clauses, re.I):
            if c.group(1).lower() not in column_names(body):
                missing.append(f'{table}.{c.group(1)}')
        for c in re.finditer(r'ADD\s+(?:UNIQUE\s+)?(?:KEY|INDEX)\s+`?(\w+)`?', clauses, re.I):
            if c.group(1).lower() not in index_names(body):
                missing.append(f'{table} index {c.group(1)}')
    for m in re.finditer(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+`?(\w+)`?\s+ON\s+`?(\w+)`?', sql, re.I):
        if m.group(2).lower() not in SCHEMA_TABLES or m.group(1).lower() not in index_names(SCHEMA_TABLES[m.group(2).lower()]):
            missing.append(f'{m.group(2)} index {m.group(1)}')
    assert not missing, f'{name} : absent de db/schema.sql → {missing}'
