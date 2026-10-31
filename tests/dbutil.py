"""Remise à zéro des données de la base jetable, dans l'ordre des clés étrangères."""
TABLES = ('etf_analysis', 'split_log', 'account_attempts', 'account_tokens', 'session_policies', 'funnel_steps', 'job_steps', 'catalogue_raw', 'saved_searches', 'saved_presets', 'position_levels', 'ranking_outcomes', 'universe_outcomes', 'ranking_snapshots', 'result_cache', 'job_logs', 'jobs', 'price_gaps', 'portfolio_transactions', 'portfolios', 'sessions', 'login_attempts', 'users', 'strategy_metrics',
          'series_state', 'corporate_events', 'etf_profiles', 'intraday_prices', 'daily_prices', 'latest_prices', 'fx_rates', 'listings',
          'instruments', 'catalogue_loads', 'settings')


def reset_data(conn):
    with conn.cursor() as cur:
        for t in TABLES:
            cur.execute(f'DELETE FROM {t}')
    conn.commit()
