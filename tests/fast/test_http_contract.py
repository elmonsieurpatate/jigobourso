"""Contrat HTTP de l'API (app/lib/http.php) : encodage avant statut (F03), taille bornée (F17), identifiant de requête."""
import json
import os
import shutil
import subprocess
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytestmark = pytest.mark.skipif(not shutil.which('php'), reason='php absent')


def cgi(tmp_path, snippet, stdin='', content_type='application/json', content_length=None):
    """Exécute un extrait PHP en CLI avec un corps simulé ; renvoie (stdout, stderr)."""
    script = tmp_path / 't.php'
    script.write_text('<?php require ' + json.dumps(ROOT + '/app/lib/http.php') + ';\n' + textwrap.dedent(snippet))
    return subprocess.run(['php', str(script)], input=stdin, capture_output=True, text=True, timeout=30)


def test_unencodable_data_is_a_500_not_a_success(tmp_path):
    # NAN n'est pas encodable en JSON : avant correction, le statut 200 était déjà parti.
    r = cgi(tmp_path, "$s = 200; $j = json_text(['x' => NAN], $s); echo $s, '|', $j;")
    status, body = r.stdout.split('|', 1)
    assert status == '500'
    d = json.loads(body)
    assert 'illisible' in d['error'] and len(d['ref']) == 8


def test_invalid_utf8_is_substituted_not_dropped(tmp_path):
    r = cgi(tmp_path, "$s = 200; echo $s, '|', json_text(['x' => \"a\\xFFb\"], $s);")
    status, body = r.stdout.split('|', 1)
    assert status == '200' and json.loads(body)['x'].startswith('a') and json.loads(body)['x'].endswith('b')


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    """Serveur PHP intégré avec une seule route : renvoie body() ; php://input n'est lisible qu'en contexte HTTP."""
    import socket
    import time
    import urllib.request
    d = tmp_path_factory.mktemp('srv')
    (d / 'index.php').write_text('<?php require ' + json.dumps(ROOT + '/app/lib/http.php') + ';\n'
                                 'try { out(["body" => body()]); } catch (ApiError $e) { out(["error" => $e->getMessage()], $e->status); }')
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1)
            break
        except Exception as e:
            if getattr(e, 'code', None):
                break
            time.sleep(0.1)
    yield f'http://127.0.0.1:{port}/'
    proc.terminate()


def post(url, data, ctype='application/json'):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=data, method='POST', headers={'Content-Type': ctype})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read()), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), e.headers


def test_body_over_the_limit_is_413(server):
    status, d, _ = post(server, b'{"a":"' + b'x' * (2 * 1024 * 1024) + b'"}')
    assert status == 413 and 'volumineuse' in d['error']


def test_small_json_body_is_read_and_response_carries_request_id(server):
    status, d, headers = post(server, b'{"a":1}')
    assert status == 200 and d == {'body': {'a': 1}} and len(headers['X-Request-Id']) == 8
    import re
    assert re.fullmatch(r'app;dur=\d+', headers['Server-Timing'])             # durée totale, lisible dans l'onglet Réseau


def test_non_json_content_type_is_415_and_bad_json_is_400(server):
    assert post(server, b'{"a":1}', 'text/plain')[0] == 415
    assert post(server, b'{oops')[0] == 400


def test_request_id_is_stable_within_a_request(tmp_path):
    r = cgi(tmp_path, "echo request_id() === request_id() ? 'same' : 'diff', strlen(request_id());")
    assert r.stdout == 'same8'


def raw_post(url, data, accept=None):
    import urllib.request
    headers = {'Content-Type': 'application/json'}
    if accept:
        headers['Accept-Encoding'] = accept
    with urllib.request.urlopen(urllib.request.Request(url, data=data, method='POST', headers=headers), timeout=20) as r:
        return r.read(), r.headers


def test_large_json_is_gzipped_only_when_accepted_and_worthwhile(server):
    import gzip
    big = json.dumps({'a': 'x' * 200000}).encode()
    body, headers = raw_post(server, big, 'gzip, deflate')
    assert headers['Content-Encoding'] == 'gzip' and 'Accept-Encoding' in headers['Vary']
    assert len(body) < 5000 and json.loads(gzip.decompress(body))['body']['a'] == 'x' * 200000
    assert 'gzip' in headers['Server-Timing']                                   # coût de compression attribuable
    body, headers = raw_post(server, big)                                       # client sans gzip : réponse brute
    assert headers.get('Content-Encoding') is None and len(body) > 200000
    body, headers = raw_post(server, b'{"a":1}', 'gzip')                         # petite réponse : pas de compression
    assert headers.get('Content-Encoding') is None and json.loads(body) == {'body': {'a': 1}}
