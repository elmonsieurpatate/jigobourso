"""Tableau comparatif des six scénarios de validation du moteur v2 (calcul pur, aucune base). Usage : PYTHONPATH=. python scripts/scenarios_performance_v2.py"""

from tests.seeds import cash_scenarios as sc


def eur(x):
    return f'{x:,.2f}'.replace(',', ' ')


def pct(x):
    return f'{x * 100:+.2f} %'


def main():
    rows = [sc.row(b) for b in sc.SCENARIOS]
    print('| Scénario | Capital | Dépôts | Retraits | Apports nets | Liquidités finales | Titres | Positions ouvertes | Valeur finale | Gain € | dont réalisé | dont latent | TWR | Jours estimés |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        open_ = ', '.join(f'{k} × {v:g}' for k, v in r['open'].items()) or 'aucune'
        print(
            f"| {r['title']} | {eur(r['capital'])} | {eur(r['deposits'])} | {eur(r['withdrawals'])} | {eur(r['net_contributions'])} | {eur(r['cash'])} | {eur(r['securities'])} | {open_} | "
            f"{eur(r['value'])} | {eur(r['gain'])} | {eur(r['realized'])} | {eur(r['latent'])} | {pct(r['twr']['central'])} | {r['estimated_days']} |"
        )
    print()
    r5 = sc.row(sc.s5)
    print('Contributions du scénario 5 (points de pourcentage du TWR) :')
    for k, v in r5['contributions'].items():
        if k != '__fees__':
            print(f'  {k} : {v * 100:+.2f} pt')
    print(f"  liquidités : +0.00 pt (200,00 € non investis, aucun rendement)  · total {r5['twr']['central'] * 100:+.2f} %")


if __name__ == '__main__':
    main()
