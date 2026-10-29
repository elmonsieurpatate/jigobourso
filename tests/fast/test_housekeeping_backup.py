"""Sauvegarde quotidienne des données utilisateur : outil de dump simulé, aucune base."""
import datetime as dt
import os
import stat

import pytest

from engine.jobs import tasks

FAKE_DUMP = """#!/bin/sh
echo "-- fake dump of: $@"
echo "MYSQL_PWD_SEEN=${MYSQL_PWD:+yes}"
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    tool = tmp_path / 'bin'
    tool.mkdir()
    dump = tool / 'mariadb-dump'
    dump.write_text(FAKE_DUMP)
    dump.chmod(0o755)
    monkeypatch.setenv('PATH', f'{tool}:{os.environ["PATH"]}')
    for k, v in dict(JIGO_DB_HOST='h', JIGO_DB_PORT='3306', JIGO_DB_USER='u', JIGO_DB_PASSWORD='secret', JIGO_DB_NAME='db').items():
        monkeypatch.setenv(k, v)
    return tmp_path / 'backups'


def test_backup_is_private_complete_and_once_a_day(env):
    import gzip
    now = dt.datetime(2026, 10, 29, 3, 0)
    path = tasks.backup_user_data(now, str(env))
    assert path.endswith('userdata-20261029.sql.gz')
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600 and stat.S_IMODE(os.stat(env).st_mode) == 0o700
    text = gzip.open(path, 'rt').read()
    assert all(t in text for t in tasks.BACKUP_TABLES) and 'MYSQL_PWD_SEEN=yes' in text
    assert 'secret' not in text                                   # le mot de passe passe par l'environnement, jamais par la ligne de commande
    assert tasks.backup_user_data(now, str(env)) is None          # déjà faite aujourd'hui
    assert not list(env.glob('*.part'))


def test_backup_keeps_only_the_last_fourteen(env):
    start = dt.datetime(2026, 10, 1)
    for i in range(20):
        tasks.backup_user_data(start + dt.timedelta(days=i), str(env))
    names = sorted(p.name for p in env.glob('userdata-*.sql.gz'))
    assert len(names) == tasks.BACKUP_KEEP and names[0] == 'userdata-20261007.sql.gz' and names[-1] == 'userdata-20261020.sql.gz'


def test_backup_failure_leaves_no_partial_file(env, monkeypatch, tmp_path):
    bad = tmp_path / 'bin' / 'mariadb-dump'
    bad.write_text('#!/bin/sh\necho boom >&2\nexit 3\n')
    with pytest.raises(RuntimeError, match='boom'):
        tasks.backup_user_data(dt.datetime(2026, 10, 29), str(env))
    assert not list(env.glob('*'))
