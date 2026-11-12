<?php
// Adaptateur de lecture seul : aucune modification de l'administration ou des scores.
require_once __DIR__ . '/../lib/http.php';
function classement_test_categories(?array $saved): array {
    $proposed = json_decode(file_get_contents(__DIR__ . '/../config/classement_test_categories.json'), true, 512, JSON_THROW_ON_ERROR);
    if ($saved === null) return $proposed;
    if (!isset($saved['categories']) || !is_array($saved['categories']) || !$saved['categories']) {
        throw new ApiError('Catégories administrateur invalides : aucun remplacement silencieux.', 503);
    }
    return ['schema' => 1, 'source' => 'admin', 'source_label' => 'Catégories enregistrées dans l’administration', 'categories' => $saved['categories']];
}
