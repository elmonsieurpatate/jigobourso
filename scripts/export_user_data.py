"""Export LECTURE SEULE des données utilisateur de l'ancien Jigobourso (comptes, portefeuilles, transactions, anciens registres).

Exécuté sur le serveur par stdin SSH depuis le dossier de l'application ; rien n'est déposé sur le serveur :
    ssh -p 65002 USER@HOST 'cd ~/domains/jigobourso.turnjoy.dev/public_html && .venv/bin/python -' < scripts/export_user_data.py > migration/private/user_data.json
Le résultat contient des hash de mots de passe : fichier privé (chmod 600), jamais affiché ni versionné.
"""
import datetime, decimal, json, sys
sys.path.insert(0, ".")
from tools.yahoo_pipeline.worker import connect

TABLES = ["jb_users", "jb_sessions_count", "jb_portfolios", "jb_portfolio_transactions", "jb_positions", "jb_settings", "jb_etf_profiles_count"]


def plain(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat(sep=" ") if isinstance(v, datetime.datetime) else v.isoformat()
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


con = connect(); cur = con.cursor()
cur.execute("SET SESSION TRANSACTION READ ONLY")
out = {"exported_at": datetime.datetime.utcnow().isoformat(sep=" ")}
for table in ("jb_users", "jb_portfolios", "jb_portfolio_transactions", "jb_positions", "jb_settings"):
    cur.execute("SHOW TABLES LIKE %s", (table,))
    if not cur.fetchall():
        out[table] = None
        continue
    cur.execute("SELECT * FROM " + table)
    out[table] = [{k: plain(v) for k, v in row.items()} for row in cur.fetchall()]
# Cotations détenues : identité du catalogue (lecture seule)
ids = sorted({int(r["listing_id"]) for r in (out.get("jb_portfolio_transactions") or []) if r.get("listing_id")})
out["listings"] = []
if ids:
    marks = ",".join(["%s"] * len(ids))
    cur.execute("SELECT * FROM fdp_listings WHERE listing_id IN (" + marks + ")", ids)
    out["listings"] = [{k: plain(v) for k, v in row.items()} for row in cur.fetchall()]
con.rollback()
json.dump(out, sys.stdout, separators=(",", ":"), ensure_ascii=False)
