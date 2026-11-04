"""Read-only cash-flow-neutral performance, linked daily Modified Dietz.

A true event-time TWR requires portfolio valuations immediately before each flow.
Only daily valuations are guaranteed here: flow-day returns are estimates, labelled
as such. No-flow intervals are exact for those valuations. Fees remain expenses.
Cash/dividends are not recorded: purchases are contributions to the securities
sleeve, net sale proceeds withdrawals. This is not a total-account cash return.
"""
import datetime as dt
import math


def linked(dates, values, trades, invalid=False):
    factors, index, estimated = [], [], []
    growth, previous, previous_day = 1.0, 0.0, None
    pending = sorted((t for t in trades if not t.get('note')), key=lambda t: (t['trade_at'], t.get('id') or 0))
    cursor = 0
    for day, value in zip(dates, values):
        end = dt.datetime.fromisoformat(day) + dt.timedelta(days=1)
        start = previous_day or dt.datetime.fromisoformat(day)
        flows, buys, sells = [], 0.0, 0.0
        while cursor < len(pending) and pending[cursor]['date'] <= day:
            t = pending[cursor]; cursor += 1
            gross = t['quantity'] * t['unit_price'] * t['fx_to_eur']
            if t['side'] == 'buy':
                flow = gross + t['fees_eur']; buys += flow
            else:
                net = gross - t['fees_eur']; flow = -net; sells += net
            when = dt.datetime.fromisoformat(t['trade_at'].replace('T',' '))
            weight = min(1.0,max(0.0,(end-when).total_seconds()/max(1,(end-start).total_seconds())))
            flows.append((flow,weight))
        estimated.append(bool(flows))
        factor = None
        if not invalid and previous is not None and value is not None:
            net_flow = sum(f for f,_ in flows)
            gain = value - previous - net_flow
            if previous <= 1e-12 and buys > 0:
                # New holding interval: capital first enters at the purchases,
                # not at the preceding empty observation; do not annualise time.
                denominator = buys
            elif value <= 1e-12 and buys == 0 and sells > 0:
                # Full liquidation has a known final value (net proceeds).
                denominator = previous
            else:
                denominator = previous + sum(f*w for f,w in flows)
            if denominator > 1e-12:
                candidate = 1 + gain / denominator
                if math.isfinite(candidate) and candidate >= 0:
                    factor = candidate
            elif abs(gain) < 1e-9 and abs(previous) < 1e-9 and abs(value) < 1e-9 and not flows:
                factor = 1.0  # No exposure, no invented market return.
        factors.append(factor)
        growth = growth * factor if growth is not None and factor is not None else None
        index.append(growth)
        previous, previous_day = value, end
    notes = []
    if any(estimated):
        notes.append('Performance estimée les jours d’achat/vente à partir des valorisations quotidiennes, frais compris.')
    if any(x is None for x in factors):
        notes.append('Performance hors mouvements indisponible sur les passages sans valorisation fiable ; aucune liaison artificielle entre ces passages.')
    return {'method':'linked_daily_modified_dietz', 'factors':factors, 'index':index,
            'estimated':estimated, 'notes':notes}
