"""Installation reproductible : bornes de requirements.txt, contrôle d'environnement, empreinte du moteur, restauration du code ET des dépendances."""

import os
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_env  # noqa: E402


def test_every_dependency_is_bounded_for_reproducible_installs():
    """Aucune dépendance sans borne haute : une version majeure future casserait l'hébergement (Python 3.9) sans changement de code."""
    for name, specs in check_env.parse((ROOT / 'requirements.txt').read_text()):
        ops = [op for op, _ in specs]
        assert '==' in ops or '<' in ops or '<=' in ops, f'{name} sans borne haute'


def test_version_comparison_and_parsing():
    assert check_env.parse('PyMySQL>=1.1,<2\n# note\n\nnumpy>=1.24,<2  # fin\nexchange_calendars==4.3') == [
        ('PyMySQL', [('>=', '1.1'), ('<', '2')]),
        ('numpy', [('>=', '1.24'), ('<', '2')]),
        ('exchange_calendars', [('==', '4.3')]),
    ]
    assert check_env.satisfies('1.26.4', [('>=', '1.24'), ('<', '2')])
    assert not check_env.satisfies('2.0.0', [('<', '2')]) and not check_env.satisfies('4.3.1', [('==', '4.3')])
    assert check_env.satisfies('4.3', [('==', '4.3.0')])


def test_environment_check_reports_missing_and_out_of_bounds():
    found = check_env.problems('paquet-qui-nexiste-pas>=1\nnumpy<1\n')
    assert any('paquet-qui-nexiste-pas : non installé' in x for x in found)
    assert any(x.startswith('numpy ') and 'hors des bornes' in x for x in found)


def test_current_environment_matches_requirements():
    assert check_env.problems((ROOT / 'requirements.txt').read_text()) == []


def engine_hash(root):
    out = subprocess.run(['bash', str(ROOT / 'scripts/release/engine_hash.sh'), str(root)], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def tree(tmp_path):
    for rel in [
        'engine/core.py',
        'db/schema.sql',
        'engine/analytics/admin/service.py',
        'engine/analytics/explorer/universe_verdicts.py',
        'engine/analytics/admin/title_sheet.py',
        'engine/analytics/market_views/market_facts.py',
        'engine/analytics/series/signals.py',
    ]:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('v1')
    return tmp_path


def test_engine_hash_ignores_display_only_files_and_bytecode(tmp_path):
    root = tree(tmp_path)
    base = engine_hash(root)
    for rel in [
        'engine/analytics/admin/service.py',
        'engine/analytics/explorer/universe_verdicts.py',
        'engine/analytics/admin/title_sheet.py',
        'engine/analytics/market_views/market_facts.py',
        'engine/analytics/series/signals.py',
    ]:
        (root / rel).write_text('modifié')
        assert engine_hash(root) == base, rel
    (root / 'engine/core.pyc').write_text('x')
    assert engine_hash(root) == base


def test_engine_hash_changes_with_producing_code_and_schema(tmp_path):
    root = tree(tmp_path)
    base = engine_hash(root)
    (root / 'engine/core.py').write_text('v2')
    changed = engine_hash(root)
    assert changed != base
    (root / 'db/schema.sql').write_text('v2')
    assert engine_hash(root) not in (base, changed)


def test_hash_exclusions_name_files_that_exist():
    """Un module déplacé sans mettre à jour la liste ferait recalculer (ou ne plus recalculer) à tort : chaque exclusion doit exister."""
    import re

    for path in re.findall(r"! -path (\S+)", (ROOT / 'scripts/release/engine_hash.sh').read_text()):
        assert (ROOT / path).is_file(), path


def test_deploy_uses_the_single_hash_script_before_and_after():
    deploy = (ROOT / 'ops/deploy.sh').read_text()
    assert deploy.count('engine_hash.sh') == 2 and '! -path engine/' not in deploy
    assert "< scripts/release/engine_hash.sh" in deploy  # « avant » : envoyé au serveur, l'ancien code ne l'a pas


RESTORE_MARK = ('# Code ET dépendances', '"$ROOT/.venv/bin/python" -c "import sys; sys.path.insert')


def restore_block():
    deploy = (ROOT / 'ops/deploy.sh').read_text()
    return deploy[deploy.index(RESTORE_MARK[0]) : deploy.index(RESTORE_MARK[1])]


def fake_server(tmp_path, installed, sha):
    """Racine factice : le « python » du venv n'indique que le dossier des paquets (le vrai venv n'est jamais touché)."""
    root, backups, site = tmp_path / 'root', tmp_path / 'backups', tmp_path / 'site'
    (root / '.venv/bin').mkdir(parents=True)
    backups.mkdir()
    site.mkdir()
    (site / 'paquet.txt').write_text(installed)
    py = root / '.venv/bin/python'
    py.write_text(f'#!/bin/sh\necho {site}\n')
    py.chmod(0o755)
    (root / 'requirements.txt').write_text('numpy<2\n')
    if sha is not None:
        (root / '.requirements.sha').write_text(sha + '\n')
    return root, backups, site


def run_restore(root, backups):
    return subprocess.run(['bash', '-c', 'set -euo pipefail\n' + restore_block()], env={**os.environ, 'ROOT': str(root), 'BACKUPS': str(backups)}, capture_output=True, text=True)


def pack(backups, site_content, name):
    src = backups / 'src'
    src.mkdir(exist_ok=True)
    (src / 'paquet.txt').write_text(site_content)
    with tarfile.open(backups / name, 'w:gz') as t:
        t.add(src / 'paquet.txt', arcname='./paquet.txt')


def test_restore_puts_back_the_dependencies_saved_before_an_upgrade(tmp_path):
    root, backups, site = fake_server(tmp_path, 'nouvelle', 'autre-empreinte')
    pack(backups, 'ancienne', 'site-packages-20260101000000.tgz')
    result = run_restore(root, backups)
    assert result.returncode == 0, result.stderr
    assert (site / 'paquet.txt').read_text() == 'ancienne'
    import hashlib

    assert (root / '.requirements.sha').read_text().strip() == hashlib.sha256(b'numpy<2\n').hexdigest()
    assert 'dépendances Python restaurées' in result.stdout


def test_restore_leaves_dependencies_alone_when_unchanged_or_first_run(tmp_path):
    import hashlib

    same = hashlib.sha256(b'numpy<2\n').hexdigest()
    root, backups, site = fake_server(tmp_path / 'a', 'actuelle', same)
    pack(backups, 'ancienne', 'site-packages-20260101000000.tgz')
    assert run_restore(root, backups).returncode == 0 and (site / 'paquet.txt').read_text() == 'actuelle'
    root, backups, site = fake_server(tmp_path / 'b', 'actuelle', None)
    pack(backups, 'ancienne', 'site-packages-20260101000000.tgz')
    assert run_restore(root, backups).returncode == 0 and (site / 'paquet.txt').read_text() == 'actuelle'


def test_restore_signals_missing_dependency_backup_without_failing_the_code_restore(tmp_path):
    root, backups, site = fake_server(tmp_path, 'nouvelle', 'autre-empreinte')
    result = run_restore(root, backups)
    assert result.returncode == 0 and 'vérification manuelle requise' in result.stderr and (site / 'paquet.txt').read_text() == 'nouvelle'


def dependency_server(tmp_path, installed):
    import hashlib

    same = hashlib.sha256(b'numpy<2\n').hexdigest()
    root, backups, site = fake_server(tmp_path, installed, same)
    py = root / '.venv/bin/python'
    py.write_text(
        '#!/bin/bash\nset -e\n'
        f'site={site}\n'
        'if [ "$1" = "-c" ]; then echo "$site"; '
        'elif [ "$1" = "scripts/check_env.py" ]; then grep -qx conforme "$site/paquet.txt"; '
        'elif [ "$*" = "-m pip --version" ]; then exit 0; '
        'elif [ "$1 $2 $3" = "-m pip install" ]; then '
        'echo installation >> "$site/paquet.txt"; '
        '[ "${FAIL_INSTALL:-0}" != 1 ] || exit 1; echo conforme > "$site/paquet.txt"; '
        'else exit 2; fi\n'
    )
    return root, backups, site


def ensure_dependencies(root, backups, fail=False):
    return subprocess.run(
        ['bash', str(ROOT / 'scripts/release/ensure_dependencies.sh'), str(root), str(backups)],
        env={**os.environ, 'FAIL_INSTALL': '1' if fail else '0'},
        capture_output=True,
        text=True,
    )


def test_deploy_repairs_a_drifted_venv_even_with_an_unchanged_manifest(tmp_path):
    root, backups, site = dependency_server(tmp_path, 'ancienne')
    result = ensure_dependencies(root, backups)
    assert result.returncode == 0, result.stderr
    assert (site / 'paquet.txt').read_text().strip() == 'conforme'
    assert (root / '.deployment-venv-backup').is_file()
    assert len(list(backups.glob('site-packages-*.tgz'))) == 1
    # Un échec plus tard doit restaurer le venv précédent, même empreinte égale.
    assert run_restore(root, backups).returncode == 0
    assert (site / 'paquet.txt').read_text() == 'ancienne'
    assert not (root / '.deployment-venv-backup').exists()


def test_deploy_keeps_an_already_conforming_venv(tmp_path):
    root, backups, site = dependency_server(tmp_path, 'conforme\n')
    result = ensure_dependencies(root, backups)
    assert result.returncode == 0, result.stderr
    assert not list(backups.glob('site-packages-*.tgz'))
    assert not (root / '.deployment-venv-backup').exists()
    assert (site / 'paquet.txt').read_text() == 'conforme\n'


def test_failed_dependency_repair_can_restore_the_original_venv(tmp_path):
    root, backups, site = dependency_server(tmp_path, 'ancienne')
    result = ensure_dependencies(root, backups, fail=True)
    assert result.returncode != 0
    assert (root / '.deployment-venv-backup').is_file()
    assert run_restore(root, backups).returncode == 0
    assert (site / 'paquet.txt').read_text() == 'ancienne'
