<?php
// Adaptateur pur : pas de connexion DB, ni d’écriture.
require __DIR__.'/../../app/lib/http.php';
require __DIR__.'/../../app/services/classement_test_categories.php';
$check = function ($ok, $message) { if (!$ok) throw new RuntimeException($message); };
$proposed = classement_test_categories(null);
$check($proposed['source'] === 'proposed', 'Origine des valeurs proposées explicite');
$check(count($proposed['categories']) === 17, 'Instantané V4 complet');
$saved = ['categories' => ['volatility' => $proposed['categories']['volatility']]];
$saved['categories']['volatility']['bounds'] = [0.5, 1, 2];
$saved['categories']['volatility']['labels'][0] = 'Catégorie administrateur';
$actual = classement_test_categories($saved);
$check($actual['source'] === 'admin', 'Origine enregistrée');
$check($actual['categories'] === $saved['categories'], 'Bornes, libellés et couleurs repris sans transformation');
try { classement_test_categories(['categories' => []]); throw new RuntimeException('Configuration invalide acceptée'); }
catch (ApiError $e) { $check($e->status === 503, 'Pas de remplacement silencieux'); }
echo "PASS: source proposée/admin, configuration préservée, erreur explicite, aucun accès DB.\n";
