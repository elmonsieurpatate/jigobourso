"""Migrations de schéma : ajouts seulement, une fois chacune, jamais de perte de données."""
import importlib.util
import os
import pytest
from engine.shared.db import connect

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

spec = importlib.util.spec_from_file_location('migrate', os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'migrate.py'))
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


def test_guard_accepts_additions_and_refuses_everything_else():
    migrate.check("CREATE TABLE IF NOT EXISTS t (a INT);\nALTER TABLE t ADD COLUMN b INT NULL;\nCREATE INDEX ix ON t (a);")
    for bad in ('DROP TABLE t', 'ALTER TABLE t DROP COLUMN a', 'ALTER TABLE t MODIFY a BIGINT', 'DELETE FROM t', 'UPDATE t SET a=1', 'TRUNCATE t', 'INSERT INTO t VALUES (1)', 'RENAME TABLE t TO u'):
        with pytest.raises(ValueError):
            migrate.check(bad)


def test_real_migrations_directory_is_admissible():
    for f in migrate.files():
        migrate.check(open(os.path.join(migrate.DIR, f), encoding='utf-8').read(), f)


def test_apply_once_keeps_existing_rows(tmp_path):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS zz_mig, schema_migrations')
        cur.execute('CREATE TABLE zz_mig (a INT PRIMARY KEY)')
        cur.execute('INSERT INTO zz_mig VALUES (1),(2)')
    conn.commit()
    (tmp_path / '20260101_add_b.sql').write_text('-- ajout\nALTER TABLE zz_mig ADD COLUMN b INT NULL;')
    assert migrate.pending(conn, str(tmp_path)) == ['20260101_add_b.sql']
    assert migrate.apply(conn, str(tmp_path)) == ['20260101_add_b.sql']
    assert migrate.apply(conn, str(tmp_path)) == []                           # une seule fois
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM zz_mig')
        assert cur.fetchone()['n'] == 2                                       # aucune ligne perdue
        cur.execute('DROP TABLE zz_mig')
    conn.commit()
    (tmp_path / '20260102_bad.sql').write_text('ALTER TABLE zz_mig DROP COLUMN a;')
    with pytest.raises(ValueError):
        migrate.apply(conn, str(tmp_path))
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS schema_migrations')
    conn.commit()
    conn.close()


def test_resume_after_a_partially_applied_migration(tmp_path):
    """DDL non transactionnel : une migration interrompue après sa première instruction doit pouvoir être reprise, sans perte ni blocage."""
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS zz_mig2, schema_migrations')
        cur.execute('CREATE TABLE zz_mig2 (a INT PRIMARY KEY)')
        cur.execute('INSERT INTO zz_mig2 VALUES (7)')
        cur.execute('ALTER TABLE zz_mig2 ADD COLUMN b INT NULL')                      # la première instruction est déjà là
    conn.commit()
    (tmp_path / '20260201_two.sql').write_text('ALTER TABLE zz_mig2 ADD COLUMN b INT NULL;\nALTER TABLE zz_mig2 ADD COLUMN c INT NULL;\nCREATE INDEX ix_zz ON zz_mig2 (c);')
    messages = []
    assert migrate.apply(conn, str(tmp_path), log=messages.append) == ['20260201_two.sql']
    assert any('colonne existante' in m for m in messages)
    with conn.cursor() as cur:
        cur.execute('SHOW COLUMNS FROM zz_mig2')
        assert {r['Field'] for r in cur.fetchall()} == {'a', 'b', 'c'}
        cur.execute('SELECT a FROM zz_mig2')
        assert cur.fetchone()['a'] == 7
        cur.execute('DROP TABLE zz_mig2')
        cur.execute('DELETE FROM schema_migrations')
    conn.commit()
    # une autre erreur n'est jamais ignorée et la migration n'est pas enregistrée
    (tmp_path / '20260201_two.sql').write_text('ALTER TABLE zz_inexistante ADD COLUMN x INT NULL;')
    with pytest.raises(Exception):
        migrate.apply(conn, str(tmp_path))
    conn.rollback()
    assert migrate.pending(conn, str(tmp_path)) == ['20260201_two.sql']
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS schema_migrations')
    conn.commit()
    conn.close()


def test_real_migrations_replay_on_a_fresh_schema_without_error():
    """Base neuve (db/schema.sql contient déjà tout) : rejouer toutes les vraies migrations ne casse rien (chaque instruction est « déjà appliquée »),
    et la base migrée et la base neuve exposent les mêmes colonnes."""
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS schema_migrations')
        cur.execute("SELECT table_name t, column_name c FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name<>'schema_migrations' ORDER BY 1,2")
        before = [(r['t'], r['c']) for r in cur.fetchall()]
    conn.commit()
    messages = []
    done = migrate.apply(conn, log=messages.append)
    assert done == migrate.files()
    with conn.cursor() as cur:
        cur.execute("SELECT table_name t, column_name c FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name<>'schema_migrations' ORDER BY 1,2")
        after = [(r['t'], r['c']) for r in cur.fetchall()]
    assert after == before
    conn.close()
