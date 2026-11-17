<?php
// Validation pure des périodes privées d'une stratégie, sans accès à la base.
require __DIR__ . '/../../app/services/ct_strategies.php';
$periods = [];
foreach (CT_PERIODS as $id) $periods[$id] = ['enabled' => false, 'slope' => 0.1, 'r2' => 0.75];
$periods['three_year']['enabled'] = true;
$periods['five_year']['enabled'] = true;
$periods['custom_alpha'] = ['sessions' => 100, 'enabled' => true, 'slope' => 0.2, 'r2' => 0.8];
$periods['custom_beta'] = ['sessions' => 400, 'enabled' => true, 'slope' => 0.1, 'r2' => 0.7];
$config = ct_config(['periods' => $periods, 'tree' => ['kind' => 'rule', 'metric' => 'slope', 'period' => 'custom_alpha', 'op' => '>=', 'value' => 0.2]]);
if ($config['periods']['custom_alpha']['sessions'] !== 100 || $config['periods']['custom_beta']['sessions'] !== 400 || !$config['periods']['five_year']['enabled']) throw new RuntimeException('Périodes perdues');
try {
    $bad = $periods;
    $bad['custom_alpha']['sessions'] = 1261;
    ct_config(['periods' => $bad]);
    throw new RuntimeException('Durée invalide acceptée');
} catch (ApiError $e) {
    if ($e->status !== 422) throw $e;
}
echo "PASS: périodes prédéfinies et personnalisées validées.\n";
