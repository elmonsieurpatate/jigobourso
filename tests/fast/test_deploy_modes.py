"""Deployment-mode regression tests: workflow gates and local mocked transport only."""
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def job_condition(job):
    source = (ROOT / '.github/workflows/deploy.yml').read_text()
    body = re.search(r'^  ' + job + r':\n(.*?)(?=^  [a-z_]+:|\Z)', source, re.M | re.S).group(1)
    condition = re.search(r'^    if: (.*)', body, re.M).group(1)
    if condition == '>-':
        condition = ' '.join(re.search(r'^    if: >-\n((?:      .+\n)+)', body, re.M).group(1).split())
    return condition


def expression_value(expression, context):
    context = {'github.event.head_commit.message': '', **context}
    for key in sorted(context, key=len, reverse=True):
        expression = expression.replace(key, repr(context[key]))
    expression = re.sub(r"contains\(('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"),\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\)", lambda m: repr(ast.literal_eval(m[2]) in ast.literal_eval(m[1])), expression)
    expression = expression.replace('always()', 'True').replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    tree = ast.parse(expression.strip(), mode='eval')
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare, ast.Eq, ast.NotEq, ast.Constant)
    assert all(isinstance(node, allowed) for node in ast.walk(tree)), expression
    return eval(compile(tree, '<workflow condition>', 'eval'), {'__builtins__': {}})


@pytest.mark.parametrize('event,operation,mode,expected', [
    ('push', '', '', True),
    ('workflow_dispatch', 'deploy', 'full', True),
    ('workflow_dispatch', 'deploy', '', True),
    ('workflow_dispatch', 'deploy', 'quick', False),
    ('workflow_dispatch', 'diagnostic', 'full', False),
    ('workflow_dispatch', 'rollback', 'full', False),
])
def test_full_tests_selection(event, operation, mode, expected):
    assert expression_value(job_condition('tests'), {'github.event_name': event, 'inputs.operation': operation, 'inputs.validation': mode}) is expected


@pytest.mark.parametrize('event,operation,mode,syntax,tests,main,cancelled,expected', [
    ('push', '', '', 'success', 'success', True, False, True),
    ('push', '', '', 'success', 'skipped', True, False, False),
    ('push', '', '', 'success', 'failure', True, False, False),
    ('workflow_dispatch', 'deploy', 'full', 'success', 'success', True, False, True),
    ('workflow_dispatch', 'deploy', 'full', 'success', 'skipped', True, False, False),
    ('workflow_dispatch', 'deploy', 'full', 'success', 'failure', True, False, False),
    ('workflow_dispatch', 'deploy', 'quick', 'success', 'skipped', True, False, True),
    ('workflow_dispatch', 'deploy', 'quick', 'failure', 'skipped', True, False, False),
    ('workflow_dispatch', 'deploy', 'quick', 'skipped', 'skipped', True, False, False),
    ('workflow_dispatch', 'deploy', 'quick', 'success', 'failure', True, False, False),
    ('workflow_dispatch', 'deploy', 'quick', 'success', 'cancelled', True, False, False),
    ('workflow_dispatch', 'deploy', 'quick', 'success', 'skipped', True, True, False),
    ('workflow_dispatch', 'deploy', 'quick', 'success', 'skipped', False, False, False),
    ('workflow_dispatch', 'deploy', 'full', 'success', 'success', False, False, False),
    ('workflow_dispatch', 'diagnostic', 'full', 'success', 'skipped', True, False, True),
    ('workflow_dispatch', 'rollback', 'full', 'success', 'skipped', True, False, True),
])
def test_production_job_gate(event, operation, mode, syntax, tests, main, cancelled, expected):
    context = {'github.event_name': event, 'inputs.operation': operation, 'inputs.validation': mode,
               'github.ref': 'refs/heads/main' if main else 'refs/heads/feature/test',
               'needs.syntax.result': syntax, 'needs.tests.result': tests, 'cancelled()': cancelled}
    assert expression_value(job_condition('hostinger'), context) is expected


def isolated_deployment(tmp_path, mode, fail_public=False):
    """Copy minimal code, mock ALL transports, never execute a remote command."""
    project = tmp_path / 'project'
    for folder in ('ops', 'scripts', 'db', 'app/public', 'app/routes', 'engine', 'docs'):
        (project / folder).mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / 'ops/deploy.sh', project / 'ops/deploy.sh')
    shutil.copy(ROOT / 'scripts/migrate.py', project / 'scripts/migrate.py')
    for script in ('check_financial_integrity.php', 'verify_account_release.php'):
        shutil.copy(ROOT / 'scripts' / script, project / 'scripts' / script)
    (project / 'db/schema.sql').write_text('CREATE TABLE example (id INT);\n')
    (project / 'app/public/index.html').write_text('<script src="assets/app.js?v=123"></script>')
    (project / 'app/routes/secondary_filters.php').write_text('<?php // fixture')
    for page in ('classement-test.html', 'admin-categories-test.html'):
        (project / 'app/public' / page).write_text('<script src="assets/app.js?v=123"></script>')
    (project / 'requirements.txt').write_text('')
    (project / 'README.md').write_text('fixture')
    commands = tmp_path / 'commands.jsonl'
    binaries = tmp_path / 'bin'; binaries.mkdir()
    transport = '''#!/usr/bin/env python3
import datetime,json,os,pathlib,sys
tool=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:];command=' '.join(args)
body=sys.stdin.read() if tool=='ssh' and ('bash -s' in command or command.endswith('php')) else ''
with open(os.environ['MOCK_COMMANDS'],'a') as f:f.write(json.dumps({'tool':tool,'command':command,'body':body})+'\\n')
if tool=='ssh':
 if 'verify_account_release.php' in command or 'users_fingerprint' in body: print(json.dumps({'users_fingerprint':'unchanged','mail_transport':'mock'}))
 elif 'check_financial_integrity.php' in command or command.endswith('php'): print(json.dumps({'fingerprint':'unchanged','portfolios':1,'transactions':1,'issues':[]}))
 elif '.sandbox_pw' in body: print('ready')
 elif 'lecture 80' in command: print('══ BILAN\\néchec  : aucun')
 elif 'tar czf "$BACKUPS/$name"' in body: print('code-fixture.tgz')
 elif 'find engine db' in command: print('unchanged')
elif tool=='curl':
 if '-o' in args and args[args.index('-o')+1]!='/dev/null':
  target=pathlib.Path(args[args.index('-o')+1]);target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text('?v='+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M'))
 if '-w' in args: print('500' if os.environ.get('MOCK_FAIL_PUBLIC') else ('401' if 'secondary-filters' in command else '200'),end='')
'''
    for tool in ('ssh', 'scp', 'rsync', 'curl'):
        executable = binaries / tool; executable.write_text(transport); executable.chmod(0o700)
    runner = tmp_path / 'runner'; runner.mkdir()
    env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'], RUNNER_TEMP=str(runner),
               JIGO_DEPLOY_VALIDATION=mode, JIGO_DEPLOY_DOMAIN='/isolated/demo.invalid',
               JIGO_DEPLOY_BASE='http://unreachable.invalid', MOCK_COMMANDS=str(commands), GITHUB_SHA='a' * 40)
    env.pop('JIGO_DEPLOY_SANDBOX', None)
    if fail_public: env['MOCK_FAIL_PUBLIC'] = '1'
    result = subprocess.run(['bash', str(project / 'ops/deploy.sh'), 'deploy'], cwd=project, env=env,
                            capture_output=True, text=True, timeout=15)
    log = [json.loads(line) for line in commands.read_text().splitlines()] if commands.exists() else []
    return result, log


@pytest.mark.parametrize('mode', ['full', 'quick'])
def test_real_shell_mode_selection_preserves_integrity_and_backup(tmp_path, mode):
    result, log = isolated_deployment(tmp_path, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    commands = '\n'.join(item['command'] + '\n' + item['body'] for item in log)
    assert ('sandbox_runner.sh' in commands) is (mode == 'full')
    assert ('prepare_financial_release.py' in commands) is (mode == 'full')
    assert ('verify_etf_release.py' in commands) is (mode == 'full')
    assert ('diagnostic Explorer' in commands) is (mode == 'full')
    assert 'financial-before.json' not in commands  # local evidence is not sent to the server
    assert 'mariadb-dump' in commands and 'tar czf "$BACKUPS/$name"' in commands
    assert 'check_financial_integrity.php' in commands and 'verify_account_release.php' in commands
    assert any(item['tool'] == 'curl' for item in log)
    assert 'menus de test 200, versions vérifiées, API filtres protégées (401)' in result.stdout
    assert 'Déploiement terminé' in result.stdout


def test_quick_mode_still_rolls_back_when_public_check_fails(tmp_path):
    result, log = isolated_deployment(tmp_path, 'quick', fail_public=True)
    assert result.returncode != 0
    assert 'retour arrière automatique du code' in result.stderr
    assert 'Code restauré' in result.stderr
    assert any('code-fixture.tgz' in item['command'] for item in log)


def test_invalid_validation_mode_stops_before_any_transport(tmp_path):
    result, log = isolated_deployment(tmp_path, 'unexpected')
    assert result.returncode == 2 and log == []


def test_explicit_push_marker_selects_quick_and_keeps_main_gate():
    context = {'github.event_name': 'push', 'github.event.head_commit.message': 'Livrer les menus [deploy quick]',
               'github.ref': 'refs/heads/main', 'needs.syntax.result': 'success', 'needs.tests.result': 'skipped',
               'inputs.operation': '', 'inputs.validation': '', 'cancelled()': False}
    assert expression_value(job_condition('tests'), context) is False
    assert expression_value(job_condition('hostinger'), context) is True
    assert expression_value(job_condition('hostinger'), {**context, 'github.ref': 'refs/heads/feature/test'}) is False
    assert expression_value(job_condition('hostinger'), {**context, 'needs.syntax.result': 'failure'}) is False
    assert expression_value(job_condition('hostinger'), {**context, 'needs.tests.result': 'failure'}) is False
