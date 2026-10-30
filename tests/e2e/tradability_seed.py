"""Négociabilité : volumes synthétiques sur les titres déjà semés (mêmes cours, donc mêmes scores) — base jetable du runner seulement."""
import os
assert os.environ.get('JIGO_TEST_DATABASE') == '1' and os.environ.get('JIGO_DB_NAME') == 'jigobourso_it'
from engine.shared.db import connect
c = connect()
with c.cursor() as q:
    # cours 149 € : volume 2 000 -> 298 k€/jour (limitée), 20 000 -> 2,98 M€ (à surveiller), 100 000 -> 14,9 M€ (facile), NULL -> non déterminée
    for ids, volume in ((range(3, 9), 2000), (range(9, 13), 20000), (range(13, 46), 100000), ((1001,), 1000), ((1002,), 5000), ((1003,), 20000)):
        for i in ids:
            q.execute('UPDATE latest_prices SET avg_volume_3m=%s, quote_at=NOW() WHERE listing_id=%s', (volume, i))
c.commit()
c.close()
