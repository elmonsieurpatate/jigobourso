"""Sérialisation des résultats mis en cache (table result_cache) : JSON compressé. Partagée par le calcul des scores et des verdicts ;
ne dépend ni de l'administration ni du calcul."""
import base64
import json
import zlib


def packed(payload):
    text=json.dumps(payload,separators=(',',':'))
    return json.dumps({'compressed':base64.b64encode(zlib.compress(text.encode())).decode()})


def unpacked(payload):
    data=json.loads(payload)
    return json.loads(zlib.decompress(base64.b64decode(data['compressed']))) if isinstance(data,dict) and 'compressed' in data else data
