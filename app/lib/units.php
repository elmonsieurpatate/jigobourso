<?php
// Unités de prix : devise principale + diviseur. Règle miroir de engine/shared/units.py (parité testée : tests/fast/test_units_parity.py).
// Pence (GBp/GBX), cents du rand (ZAc/ZAC), agorot (ILA) : le taux est enregistré pour la devise principale (GBP, ZAR, ILS), le facteur vers l'euro d'une unité = taux / diviseur.
const PRICE_SUBUNITS = ['GBp' => ['GBP', 100], 'GBX' => ['GBP', 100], 'ZAc' => ['ZAR', 100], 'ZAC' => ['ZAR', 100], 'ILA' => ['ILS', 100]];
function unit_split(?string $unit): array {
    if ($unit === null || $unit === '') return ['', 1];
    return PRICE_SUBUNITS[$unit] ?? PRICE_SUBUNITS[strtoupper($unit)] ?? [strtoupper($unit), 1];
}
