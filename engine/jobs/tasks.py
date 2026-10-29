"""Traitements. Deux familles bien séparées :

1. Construction du catalogue, À LA MAIN depuis l'administration, dans l'ordre :
   fdb_import (télécharge et stocke) → fdb_filter (règles FinanceDatabase) → yahoo_info (cours, volumes) → yahoo_filter (règles Yahoo)
   = catalogue final → history (importer / mettre à jour les historiques).
2. Entretien AUTOMATIQUE (cron, `tick`) : uniquement les historiques et cotations du catalogue final (plus les titres détenus).
   Le cron n'importe jamais FinanceDatabase, ne filtre jamais, ne change jamais le catalogue.
"""
import datetime
import glob
import gzip
import os
import shutil
import subprocess
import tempfile
import time

from engine.analytics import compute, funnel, tracking
from engine.catalogue import loader
from engine.market import catchup, collect, hours, splits
from engine.market.yahoo import RateLimited
from engine.shared import settings
from . import schedule
from .runner import recover_interrupted, run_job

FDB_URL = 'https://github.com/JerBouma/FinanceDatabase.git'


def _step(log, name, fn, detail=None):
    """Étape chronométrée si le traitement est suivi par le journal, sinon simple appel (tests, appels directs)."""
    return log.step(name, fn, detail) if hasattr(log, 'step') else fn()


def _progress(log, label, total):
    done = [0]

    def cb(n):
        done[0] += n
        if hasattr(log, 'progress'):
            log.progress(f'{label} : {min(done[0], total)} / {total} titres')
    return cb


def _now_iso(now):
    return now.astimezone(datetime.timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=' ')


def save_stats(conn, key, now, **values):
    """Résultat structuré de la dernière exécution d'un type de traitement (affiché dans l'administration)."""
    all_ = settings.get(conn, 'last_stats', {})
    all_[key] = dict(values, at=_now_iso(now))
    settings.put(conn, 'last_stats', all_)


def add_stats(conn, key, now, round_id, **numbers):
    """Cumule les chiffres des traitements d'un même passage du cron (une ligne par place)."""
    all_ = settings.get(conn, 'last_stats', {})
    cur = all_.get(key) if (all_.get(key) or {}).get('round') == round_id else {'round': round_id}
    for k, v in numbers.items():
        cur[k] = cur.get(k, 0) + v
    cur['at'] = _now_iso(now)
    all_[key] = cur
    settings.put(conn, 'last_stats', all_)


# ───────── 1. construction du catalogue (manuelle) ─────────
def fdb_import(conn, log, now=None):
    """Télécharge FinanceDatabase et stocke les données brutes (rien n'est filtré ni supprimé : on pourra re-filtrer sans retélécharger).
    JIGO_FDB_SOURCE : dossier local déjà téléchargé (tests, hors ligne) ; sinon clone git superficiel. JIGO_FDB_REF : commit ou étiquette à utiliser (catalogue reproductible)."""
    now = now or hours.utcnow()
    local = os.environ.get('JIGO_FDB_SOURCE')
    root = local or os.path.join(os.environ.get('JIGO_DATA_DIR', 'data'), 'financedatabase')

    ref = os.environ.get('JIGO_FDB_REF', '').strip()          # version épinglée (commit complet ou étiquette) ; vide = dernière version, notée dans catalogue_loads

    def head(path):
        return subprocess.run(['git', '-C', path, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or '0' * 40

    def download():
        if local:
            return head(local)
        shutil.rmtree(root, ignore_errors=True)
        os.makedirs(os.path.dirname(root), exist_ok=True)
        if ref:
            if not all(c.isalnum() or c in '._-/' for c in ref) or ref.startswith('-'):
                raise RuntimeError('JIGO_FDB_REF invalide')
            steps = (['git', 'init', '-q', root], ['git', '-C', root, 'fetch', '-q', '--depth', '1', FDB_URL, ref], ['git', '-C', root, 'checkout', '-q', 'FETCH_HEAD'])
        else:
            steps = (['git', 'clone', '--depth', '1', FDB_URL, root],)
        for cmd in steps:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if done.returncode != 0:
                raise RuntimeError('Téléchargement de FinanceDatabase impossible : ' + done.stderr.strip()[-200:])
        return head(root)
    commit = _step(log, 'Téléchargement de FinanceDatabase', download, lambda r: f'version {r[:8]}')
    try:
        read = _step(log, 'Stockage des données brutes', lambda: loader.store_raw(conn, root), lambda r: f'{r} lignes')
    finally:
        if not local:
            shutil.rmtree(root, ignore_errors=True)
    loader.record_load(conn, read, commit)
    save_stats(conn, 'fdb_import', now, rows=read, commit=commit[:8])
    return read, 0, f'{read} lignes importées · version {commit[:8]}'


def fdb_filter(conn, log, now=None):
    """Applique les règles FinanceDatabase aux données brutes déjà stockées (aucun téléchargement) et met à jour les cotations."""
    now = now or hours.utcnow()
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        if not cur.fetchone()['n']:
            raise RuntimeError('Aucune donnée FinanceDatabase en base : lancez d’abord « Importer FinanceDatabase »')
    changed = _step(log, 'Application des filtres', lambda: loader.apply_rules(conn), lambda r: f'{r} lignes dont le résultat a changé')
    _step(log, 'Mise à jour des produits et des cotations', lambda: loader.sync_listings(conn),
          lambda r: f'{r["cotations"]} cotations, {r["exclues"]} exclues, {r["principales"]} principales')
    steps = _step(log, 'Résultats par étape (figés)', lambda: funnel.snapshot(conn, 'catalogue', getattr(log, 'job_id', None)))
    kept = steps[-1]['kept']
    save_stats(conn, 'fdb_filter', now, kept=kept, raw=steps[0]['kept'])
    return kept, 0, f'{steps[0]["kept"]} lignes → {kept} titres transmis à Yahoo ({changed} lignes modifiées)'


def info_set(conn):
    """Titres issus du filtrage FinanceDatabase à interroger chez Yahoo : cotation principale de chaque produit, plus les titres détenus."""
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id AS listing_id, l.mic, l.symbol FROM listings l
                       WHERE (l.is_primary=1 AND (l.status IN ('candidate','selected') OR l.excluded_reason LIKE 'préfiltre%'))
                          OR l.id IN (SELECT listing_id FROM portfolio_transactions WHERE listing_id IS NOT NULL)""")
        return cur.fetchall()


def yahoo_info(conn, client, now, log):
    """Récupère chez Yahoo les informations de sélection (cours, devise, volume moyen) pour les titres issus du filtrage FinanceDatabase.
    Ne sélectionne rien et ne télécharge aucun historique."""
    rows = info_set(conn)
    if not rows:
        raise RuntimeError('Aucun titre à interroger : filtrez d’abord FinanceDatabase')
    stats = {}
    ok, err = _step(log, 'Informations de cotation (Quote)', lambda: collect.refresh_quotes(conn, client, rows, now, _progress(log, 'Informations Yahoo', len(rows)), stats),
                    lambda r: f'{r[0]} reçues sur {len(rows)} demandées')
    _step(log, 'Taux de change', lambda: collect.refresh_fx(conn, client, now))
    errors = stats.get('errors', 0)
    missing = err - errors
    save_stats(conn, 'yahoo_info', now, requested=len(rows), recovered=ok, missing=missing, errors=errors)
    return ok, err, f'{ok} reçues · {missing} sans information · {errors} en erreur (sur {len(rows)} demandées)'


def yahoo_filter(conn, log, now=None):
    """Applique les règles Yahoo (prix, ancienneté du dernier cours, liquidité, volume) aux informations déjà stockées (aucun appel à Yahoo) : le résultat est le catalogue final."""
    now = now or hours.utcnow()
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM latest_prices WHERE quote_at IS NOT NULL')
        if not cur.fetchone()['n']:
            raise RuntimeError('Aucune information Yahoo en base : lancez d’abord « Importer les informations Yahoo »')
    changed = _step(log, 'Application des filtres', lambda: collect.apply_prefilter(conn, now), lambda r: f'{r["selected"]} retenus, {r["excluded"]} écartés (changements)')
    _step(log, 'Cotation principale de chaque produit', lambda: loader.assign_primaries(conn), lambda r: f'{r} cotations principales')
    settings.mark_applied(conn, 'prefilter', settings.prefilter_rules(conn))
    steps = _step(log, 'Résultats par étape (figés)', lambda: funnel.snapshot(conn, 'yahoo', getattr(log, 'job_id', None)))
    final = steps[-1]['kept']
    save_stats(conn, 'yahoo_filter', now, final=final)
    return final, 0, f'catalogue final : {final} titres ({changed["selected"]} retenus, {changed["excluded"]} écartés ce passage)'


# ───────── historiques : même code pour le bouton de l'administration et pour le cron ─────────
def _count(conn, table, ids):
    n = 0
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = ids[i:i + 2000]
            cur.execute(f"SELECT COUNT(*) n FROM {table} WHERE listing_id IN ({','.join(['%s'] * len(part))})", part)
            n += cur.fetchone()['n']
    return n


def fetch_daily(conn, client, rows, now, cb=None, allowed=None):
    """Clôtures quotidiennes manquantes : une fenêtre adaptée par titre, rien pour un titre déjà à jour. Renvoie les chiffres."""
    ids = [r['listing_id'] for r in rows]
    plan, fresh = collect.daily_plan(conn, rows, now)
    forced = set(splits.due_ids(conn, ids, collect.naive_utc(now).date()))
    if allowed is not None:                       # rattrapage : seulement les titres dont le délai de nouvelle tentative est écoulé
        plan = {rng: [r for r in group if r['listing_id'] in allowed] for rng, group in plan.items()}
        plan = {rng: group for rng, group in plan.items() if group}
    before = _count(conn, 'daily_prices', ids)
    answered = lines = err = 0
    replied = set()
    for rng, group in plan.items():
        ok, ln, er = collect.collect_daily(conn, client, group, now, range_=rng, progress=cb, answered=replied)
        answered, lines, err = answered + ok, lines + ln, err + er
        if rng == '2y':
            collect.mark_backfill_tried(conn, group, now)
    if cb and fresh:
        cb(fresh)
    added = max(0, _count(conn, 'daily_prices', ids) - before)
    asked = forced & {r['listing_id'] for g in plan.values() for r in g}
    refetched = sorted(asked & replied)
    outcome = splits.resolve(conn, refetched, now) if refetched else {'confirmed': 0, 'real_move': 0}
    if asked - replied:                                         # Yahoo n'a rien répondu pour ces titres : on ne conclut pas, nouvel essai demain
        splits.postpone(conn, sorted(asked - replied), collect.naive_utc(now).date() + datetime.timedelta(days=1))
    return {'titles': len(rows), 'up_to_date': fresh, 'asked': sum(len(g) for g in plan.values()), 'answered': answered, 'errors': err, 'added': added, 'present': max(0, lines - added),
            'splits_confirmed': outcome['confirmed'], 'splits_real_move': outcome['real_move']}


def fetch_intraday(conn, client, rows, now, cb=None, previous=True, failed=None):
    """Barres de 15 minutes des deux dernières séances de chaque place : uniquement celles qui manquent ou doivent être actualisées."""
    ids = [r['listing_id'] for r in rows]
    plan, summary = collect.intraday_plan(conn, rows, now, previous)
    before = _count(conn, 'intraday_prices', ids)
    answered = lines = err = 0
    for rng, group in plan.items():
        ok, ln, er = collect.collect_intraday(conn, client, group, now, range_=rng, progress=cb, failed=failed)
        answered, lines, err = answered + ok, lines + ln, err + er
    done = sum(len(g) for g in plan.values())
    if cb and len(rows) > done:
        cb(len(rows) - done)
    added = max(0, _count(conn, 'intraday_prices', ids) - before)
    return {'titles': len(rows), 'up_to_date': summary['complete'], 'unknown_hours': summary['unknown_hours'], 'asked': done, 'answered': answered, 'errors': err, 'added': added, 'present': max(0, lines - added)}


def history_coverage(conn):
    """Historique quotidien du catalogue final : complet (≥ 400 séances), incomplet, absent ; date de dernière donnée."""
    with conn.cursor() as cur:
        cur.execute("""SELECT COALESCE(SUM(n=0),0) absent, COALESCE(SUM(n BETWEEN 1 AND %s),0) partial, COALESCE(SUM(n>=%s),0) complete, MAX(last_day) last_day FROM
                       (SELECT c.listing_id, COUNT(d.price_date) n, MAX(d.price_date) last_day FROM v_collect_set c LEFT JOIN daily_prices d ON d.listing_id=c.listing_id GROUP BY c.listing_id) t""",
                    (collect.FULL_SESSIONS - 1, collect.FULL_SESSIONS))
        r = cur.fetchone()
    return {'absent': int(r['absent']), 'partial': int(r['partial']), 'complete': int(r['complete']), 'last_day': r['last_day'].isoformat() if r['last_day'] else None}


def history(conn, client, now, log):
    """« Importer / Mettre à jour les historiques » : travaille sur le catalogue final (plus les titres détenus), sans jamais changer la sélection."""
    rows = collect.collection_set(conn)
    if not rows:
        raise RuntimeError('Le catalogue final est vide : filtrez d’abord Yahoo Finance')
    total = len(rows)
    d = _step(log, 'Historiques quotidiens (séances manquantes)', lambda: fetch_daily(conn, client, rows, now, _progress(log, 'Historiques quotidiens', total)),
              lambda r: f'{r["asked"]} titres interrogés, {r["up_to_date"]} déjà à jour, {r["added"]} clôtures ajoutées, {r["errors"]} sans réponse')
    i = _step(log, 'Barres de 15 minutes (deux dernières séances)', lambda: fetch_intraday(conn, client, rows, now, _progress(log, 'Barres de 15 minutes', total)),
              lambda r: f'{r["asked"]} titres interrogés, {r["up_to_date"]} déjà complets, {r["added"]} barres ajoutées, {r["errors"]} sans réponse' + (f', {r["unknown_hours"]} sans horaires connus' if r['unknown_hours'] else ''))
    _step(log, 'Indicateurs et classements', lambda: compute.compute_all(conn, now), lambda r: f'{r[0]} séries, {r[1]} lignes de mesures')
    _step(log, 'Détection des splits', lambda: splits.detect(conn, now), lambda r: f'{r} nouveaux sauts à vérifier auprès de Yahoo')
    cov = history_coverage(conn)
    save_stats(conn, 'history', now, daily=d, intraday=i, coverage=cov, titles=total)
    errors = d['errors'] + i['errors']
    return total - min(total, errors), errors, f'{total} titres · quotidien +{d["added"]} · 15 min +{i["added"]} · {errors} sans réponse'


# ───────── entretien : purges et sauvegarde ─────────
BACKUP_TABLES = ('users', 'portfolios', 'portfolio_transactions', 'position_levels', 'saved_searches', 'settings')     # ce qui n'est pas reconstructible depuis Yahoo
BACKUP_KEEP = 14


def housekeeping(conn, now):
    """Purge les tables d'exploitation qui grossiraient sans fin (tentatives, sessions et jetons périmés, anciens traitements). Renvoie le nombre de lignes par table."""
    naive = collect.naive_utc(now)
    day, week, quarter = (naive - datetime.timedelta(days=d) for d in (1, 7, 90))
    plan = (('login_attempts', 'at < %s', day), ('account_attempts', 'at < %s', day), ('sessions', 'expires_at < %s', naive),
            ('account_tokens', 'expires_at < %s', week), ('job_steps', 'started_at < %s', quarter),
            ('jobs', "started_at < %s AND status NOT IN ('queued','running')", quarter))
    out = {}
    for table, cond, arg in plan:
        try:
            with conn.cursor() as cur:
                cur.execute(f'DELETE FROM {table} WHERE {cond}', (arg,))
                out[table] = cur.rowcount
            conn.commit()
        except Exception:                                                        # noqa: BLE001 : table absente (base pas encore migrée) ou verrou : on passe à la suivante
            conn.rollback()
            out[table] = None
    return out


def backup_user_data(now, directory=None):
    """Une sauvegarde par jour (UTC) des tables irremplaçables (comptes, portefeuilles, transactions, réglages), hors racine web, droits 600,
    14 exemplaires conservés. Renvoie le chemin créé, ou None si celle du jour existe déjà. Lève RuntimeError si l'outil ou le dump échoue."""
    directory = directory or os.environ.get('JIGO_BACKUP_DIR') or os.path.join(os.environ.get('JIGO_DATA_DIR', 'data'), 'backups')
    target = os.path.join(directory, f'userdata-{now.strftime("%Y%m%d")}.sql.gz')
    if os.path.exists(target):
        return None
    dump = shutil.which('mariadb-dump') or shutil.which('mysqldump')
    if not dump:
        raise RuntimeError('mariadb-dump introuvable')
    os.makedirs(directory, mode=0o700, exist_ok=True)
    env = dict(os.environ, MYSQL_PWD=os.environ.get('JIGO_DB_PASSWORD', ''))
    cmd = [dump, f'-h{os.environ["JIGO_DB_HOST"]}', f'-P{os.environ.get("JIGO_DB_PORT", "3306")}', f'-u{os.environ["JIGO_DB_USER"]}',
           '--single-transaction', '--quick', os.environ['JIGO_DB_NAME'], *BACKUP_TABLES]
    part = target + '.part'
    try:
        with open(part, 'wb') as out, tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, env=env)
            with gzip.GzipFile(fileobj=out, mode='wb') as gz:
                shutil.copyfileobj(proc.stdout, gz)
            code = proc.wait(timeout=600)
            err.seek(0)
            detail = err.read()[-200:].decode('utf-8', 'replace')
        if code != 0:
            raise RuntimeError(f'mariadb-dump a échoué ({code}) : {detail}')
        os.chmod(part, 0o600)
        os.replace(part, target)
    finally:
        if os.path.exists(part):
            os.remove(part)
    for old in sorted(glob.glob(os.path.join(directory, 'userdata-*.sql.gz')))[:-BACKUP_KEEP]:
        os.remove(old)
    return target


# ───────── 2. entretien automatique (cron) ─────────
def maintenance(conn, client, now, log):
    """Après la collecte quotidienne : cours et devises du catalogue final, indicateurs, suivi, rétention (les trous sont rattrapés à chaque passage : catchup.py). Ne sélectionne rien."""
    settings.put(conn, 'maintenance_pending', False)           # une clôture ajoutée pendant la maintenance la redéclenchera
    rows = collect.collection_set(conn)
    ok, err = _step(log, 'Cours de référence (Quote)', lambda: collect.refresh_quotes(conn, client, rows, now), lambda r: f'{r[0]} reçus sur {len(rows)}')
    _step(log, 'Taux de change', lambda: collect.refresh_fx(conn, client, now))

    def fx_history():
        try:
            return collect.backfill_fx(conn, client, now)
        except RateLimited:
            raise
        except Exception as e:                                                   # noqa: BLE001 : l'historique de change ne doit jamais empêcher le recalcul
            conn.rollback()
            log('warning', f'historique de change impossible : {e}')
            return 0
    _step(log, 'Historique des taux de change', fx_history, lambda r: f'{r} taux ajoutés')
    n_series, n_metrics = _step(log, 'Indicateurs et classements', lambda: compute.compute_all(conn, now), lambda r: f'{r[0]} séries, {r[1]} lignes de mesures')
    _step(log, 'Détection des splits', lambda: splits.detect(conn, now), lambda r: f'{r} nouveaux sauts à vérifier auprès de Yahoo')
    snap_day, snap_rows = _step(log, 'Suivi des classements', lambda: tracking.record_snapshot(conn), lambda r: f'{r[0]} ({r[1]} titres)')
    outcomes = _step(log, 'Résultats du suivi', lambda: tracking.update_outcomes(conn), lambda r: f'{r} résultats')
    _step(log, 'Rétention des clôtures et des barres', lambda: (collect.prune_daily(conn, now), collect.prune_intraday(conn, now)))
    _step(log, 'Purge des tables d’exploitation', lambda: housekeeping(conn, now))

    def backup():
        try:
            return backup_user_data(now)
        except Exception as e:                                                   # noqa: BLE001 : ne fait jamais échouer la maintenance, mais reste visible dans les journaux
            log('warning', f'sauvegarde des données utilisateur impossible : {e}')
            return '(échec : voir les avertissements)'
    _step(log, 'Sauvegarde des données utilisateur', backup, lambda r: 'déjà faite aujourd’hui' if r is None else os.path.basename(r))
    return ok, err, f'cours {ok}/{ok + err}, séries {n_series}, mesures {n_metrics}, suivi {snap_day} ({snap_rows} titres, {outcomes} résultats)'


def _ran_within(conn, job_type, minutes, now):
    """Garde-fou : un cron appelé plus souvent que prévu ne refait pas la même collecte."""
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM jobs WHERE job_type=%s AND started_at >= %s', (job_type, now.replace(tzinfo=None) - datetime.timedelta(minutes=minutes)))
        return cur.fetchone()['n'] > 0


def _just_closed(mic, now):
    """Jusqu'à 30 minutes après la fermeture : dernier passage pour finaliser le dernier créneau."""
    return not hours.is_open(mic, now) and hours.is_open(mic, now - datetime.timedelta(minutes=30))


def _maintenance_due(conn, now):
    """La maintenance (indicateurs, suivi, rétention : ~2 minutes) suit une collecte quotidienne qui a AJOUTÉ des clôtures, pas chaque nouvelle tentative qui n'apporte rien.
    Après un échec, elle attend 30 minutes avant de se représenter."""
    return bool(settings.get(conn, 'maintenance_pending', False)) and not _ran_within(conn, 'maintenance', 30, now)


def _daily(conn, client, rows, now, log, round_id=None, due=None, mic=None):
    d = fetch_daily(conn, client, rows, now, _progress(log, 'Clôtures', len(rows)), allowed=due)
    if due is not None and mic:
        catchup.daily_after(conn, mic, due, now)               # retient les clôtures toujours absentes pour les redemander plus tard
    if d['errors']:
        log('warning', f'{d["errors"]} cotations sans réponse : nouvelle tentative automatique plus tard')
    if d['added'] or d.get('splits_confirmed') or d.get('splits_real_move'):
        settings.put(conn, 'maintenance_pending', True)             # l'historique d'un titre a été réécrit ou de nouvelles clôtures sont arrivées : recalcul
    add_stats(conn, 'daily', now, round_id or _now_iso(now), titles=d['titles'], up_to_date=d['up_to_date'], answered=d['answered'], errors=d['errors'], added=d['added'], present=d['present'])
    return d['answered'], d['errors'], f'{d["added"]} clôtures ajoutées, {d["up_to_date"]} titres déjà à jour'


def _intraday(conn, client, rows, now, log, round_id=None, mic=None):
    failed = []
    try:
        d = fetch_intraday(conn, client, rows, now, _progress(log, 'Barres 15 min', len(rows)), previous=False, failed=failed)
    except RateLimited:
        if mic:
            catchup.note_failed(conn, mic, hours.session_date(mic, now), None, now)
        raise
    if failed and mic:
        catchup.note_failed(conn, mic, hours.session_date(mic, now), failed, now)   # ces titres seront redemandés après la clôture
    if d['errors']:
        log('warning', f'{d["errors"]} cotations sans réponse : rattrapage automatique prévu')
    add_stats(conn, 'intraday', now, round_id or _now_iso(now), titles=d['titles'], up_to_date=d['up_to_date'], answered=d['answered'], errors=d['errors'], added=d['added'], present=d['present'])
    return d['answered'], d['errors'], f'{d["added"]} barres ajoutées, {d["up_to_date"]} titres déjà complets'


def tick(conn, client, now=None, trigger='cron'):
    """Passage du cron (toutes les 5 minutes en production) : décide seul quoi faire, d'après la planification enregistrée.
    N'agit QUE sur le catalogue final et les titres détenus : jamais d'import, de filtre ni de reconstruction du catalogue.
    Seul un passage déclenché par le cron laisse le battement qui prouve que le cron fonctionne (un test manuel ne compte pas)."""
    now = now or hours.utcnow()
    t0 = time.monotonic()
    recover_interrupted(conn)                                                    # un traitement tué (hébergeur, panne) ne garde pas son verrou
    sched = schedule.get(conn)
    schedule.beat(conn, now, trigger)
    round_id = _now_iso(now)
    done = []

    def guarded(where, fn):
        """Une erreur sur une place ne doit jamais empêcher les autres : elle est notée (visible dans l'administration) et le passage continue."""
        try:
            return fn()
        except Exception as e:                                                   # noqa: BLE001
            conn.rollback()
            schedule.record_error(conn, now, where, e)

    # 1. collectes normales, toujours prioritaires
    for mic in sorted({r['mic'] for r in collect.collection_set(conn)}):
        rows = collect.collection_set(conn, mic)
        if sched['intraday']['enabled'] and hours.known(mic) and (hours.is_open(mic, now) or _just_closed(mic, now)) \
                and not _ran_within(conn, 'intraday:' + mic, max(1, sched['intraday']['interval_minutes'] - 3), now):
            done.append(('intraday', mic, guarded(f'intraday:{mic}', lambda: run_job(conn, 'intraday:' + mic, lambda log: _intraday(conn, client, rows, now, log, round_id, mic), trigger=trigger))))
        # clôtures : dès la publication, puis nouvelles tentatives espacées tant qu'il en manque (panne de Yahoo, passage manqué, titre en retard)
        due = guarded(f'daily:{mic}', lambda: catchup.daily_due(conn, mic, rows, now)) if sched['daily']['enabled'] else None
        if due:
            done.append(('daily', mic, guarded(f'daily:{mic}', lambda: run_job(conn, 'daily:' + mic, lambda log: _daily(conn, client, rows, now, log, round_id, due, mic), trigger=trigger))))
    if sched['daily']['enabled'] and _maintenance_due(conn, now):
        done.append(('maintenance', None, guarded('maintenance', lambda: run_job(conn, 'maintenance', lambda log: maintenance(conn, client, now, log), trigger=trigger))))
    # 2. rattrapage : séances de 15 min incomplètes ou titres sans réponse, y compris après une panne de plusieurs heures ou jours
    if sched['intraday']['enabled']:
        work = guarded('rattrapage', lambda: catchup.plan_intraday(conn, now))
        if work:
            done.append(('catchup', None, guarded('rattrapage', lambda: run_job(conn, 'catchup', lambda log: catchup.execute(conn, client, work, now, log), trigger=trigger))))
    summary = ', '.join(f'{k}{":" + m if m else ""}' for k, m, _ in done) or 'rien à faire'
    schedule.beat(conn, now, trigger, done=summary[:200], duration=round(time.monotonic() - t0, 1))
    return done


JOBS = ('fdb_import', 'fdb_filter', 'yahoo_info', 'yahoo_filter', 'history')
MANUAL_LABELS = {'fdb_import': 'Import FinanceDatabase', 'fdb_filter': 'Filtrage FinanceDatabase', 'yahoo_info': 'Import des informations Yahoo',
                 'yahoo_filter': 'Filtrage Yahoo', 'history': 'Import / mise à jour des historiques'}


def precheck(conn, name):
    """Message clair si l'étape précédente n'a pas été faite (ValueError)."""
    if name not in JOBS:
        raise ValueError('Traitement inconnu')
    with conn.cursor() as cur:
        if name == 'fdb_filter':
            cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
            if not cur.fetchone()['n']:
                raise ValueError('Importez d’abord FinanceDatabase (étape 1).')
        if name == 'yahoo_filter':
            cur.execute('SELECT COUNT(*) n FROM latest_prices WHERE quote_at IS NOT NULL')
            if not cur.fetchone()['n']:
                raise ValueError('Importez d’abord les informations Yahoo (étape 3).')
        cur.execute("SELECT job_type FROM jobs WHERE status IN ('queued','running') AND job_type IN %s LIMIT 1", (JOBS,))
        busy = cur.fetchone()
    if name == 'yahoo_info' and not info_set(conn):
        raise ValueError('Aucun titre à interroger : filtrez d’abord FinanceDatabase (étape 2).')
    if name == 'history' and not collect.collection_set(conn):
        raise ValueError('Le catalogue final est vide : filtrez d’abord Yahoo Finance (étape 4).')
    if busy:
        raise ValueError(f'« {MANUAL_LABELS[busy["job_type"]]} » est déjà en cours : attendez sa fin.')


def run_manual(conn, client, name, now=None, trigger='admin'):
    """Lance un traitement de construction du catalogue (ou la collecte manuelle). Renvoie l'identifiant du traitement."""
    now = now or hours.utcnow()
    fns = {'fdb_import': lambda log: fdb_import(conn, log, now), 'fdb_filter': lambda log: fdb_filter(conn, log, now), 'yahoo_info': lambda log: yahoo_info(conn, client, now, log),
           'yahoo_filter': lambda log: yahoo_filter(conn, log, now), 'history': lambda log: history(conn, client, now, log)}
    return run_job(conn, name, fns[name], trigger=trigger)
