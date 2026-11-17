<?php
// Exécuté depuis la racine, y compris par stdin sur le serveur : SELECT uniquement.
require_once getcwd() . '/app/lib/db.php';
$term = trim((string)base64_decode(getenv('JIGO_CATALOGUE_QUERY_B64') ?: '', true));
if ($term === '' || strlen($term) > 100) throw new RuntimeException('ISIN ou symbole requis (100 caractères maximum)');
$rows = q("SELECT r.symbol, r.mic, r.isin, r.name, r.group_key, r.removed_step, r.removed_reason,
                  l.id, l.status, l.is_primary, l.excluded_reason, l.primary_reason,
                  p.id AS primary_id, p.symbol AS primary_symbol, p.mic AS primary_mic, p.status AS primary_status
           FROM catalogue_raw r
           LEFT JOIN instruments i ON i.group_key = r.group_key
           LEFT JOIN listings l ON l.instrument_id = i.id AND l.mic = r.mic AND l.symbol = LEFT(r.symbol,24)
           LEFT JOIN listings p ON p.instrument_id = i.id AND p.is_primary = 1
           WHERE r.group_key IN (SELECT group_key FROM catalogue_raw WHERE isin = ? OR symbol = ?)
           ORDER BY r.group_key, r.mic, r.symbol LIMIT 100", [$term, $term])->fetchAll();
require_once getcwd() . '/app/services/explore_actions.php';
$lookups = [];
foreach (array_slice(array_unique(array_merge([$term], array_column($rows, 'symbol'))), 0, 12) as $symbol) {
    $lookups[$symbol] = array_map(function ($r) {
        return ['id' => $r['id'], 'symbol' => $r['symbol'], 'status' => $r['status'],
                'in_catalogue' => $r['in_catalogue'] ?? null, 'primary' => $r['primary'] ?? null];
    }, listings_search(['q' => $symbol])['results']);
}
echo json_encode(['catalogue_query' => $term, 'rows' => $rows, 'lookups' => $lookups], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT) . "\n";
