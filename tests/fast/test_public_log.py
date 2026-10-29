"""ops/public-log.sh : le journal publié ne contient que titres d'étapes et verdicts, et le filtre n'échoue jamais (régression du 29/10 : aucun match = échec de la CI)."""
import os
import subprocess

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'ops', 'public-log.sh')


def run(text):
    p = subprocess.run(['bash', '-c', 'set -euo pipefail; bash "$0"', SCRIPT], input=text, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_keeps_step_titles_and_verdicts_only():
    out = run('== Transfert du code\nIntégrité : 9 transactions ; anomalies [{id 14}]\nSauvegarde : db-1.sql.gz (57M)\nPython 3.9.25\nsite OK : accueil 200, version 1\nDéploiement terminé : abc\n')
    assert out.splitlines() == ['== Transfert du code', 'site OK : accueil 200, version 1', 'Déploiement terminé : abc']


def test_never_fails_when_nothing_matches():
    assert run('{"ok": true, "at_utc": "2026-10-29"}\n') == ''
    assert run('') == ''
