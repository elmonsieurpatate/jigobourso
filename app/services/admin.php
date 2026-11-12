<?php
// Administration : lecture des journaux et compteurs du catalogue.
require_once __DIR__ . '/../lib/db.php';

// Dernières lignes d'un journal (fin du fichier seulement), éventuellement filtrées par expression régulière ; chaque ligne est tronquée.
function log_tail(string $file, int $n, ?string $re): array {
    if (!is_file($file) || !is_readable($file)) return [];
    $size = filesize($file);
    $fh = @fopen($file, 'rb');
    if (!$fh) return [];
    if ($size > 65536) fseek($fh, -65536, SEEK_END);
    $lines = preg_split('/\r?\n/', (string)stream_get_contents($fh), -1, PREG_SPLIT_NO_EMPTY);
    fclose($fh);
    if ($re !== null) $lines = array_values(array_filter($lines, fn($l) => preg_match($re, $l)));
    return array_map(fn($l) => mb_substr($l, 0, 300), array_slice($lines, -$n));
}

function system_counts(): array {
    $c = [];
    foreach (q("SELECT i.kind, l.status, COUNT(*) n FROM listings l JOIN instruments i ON i.id = l.instrument_id GROUP BY i.kind, l.status")->fetchAll() as $r) $c['listings'][$r['kind']][$r['status']] = (int)$r['n'];
    $c['primary_selected'] = (int)q("SELECT COUNT(*) FROM listings WHERE status = 'selected' AND is_primary = 1")->fetchColumn();
    $c['held'] = (int)q('SELECT COUNT(DISTINCT listing_id) FROM portfolio_transactions WHERE listing_id IS NOT NULL')->fetchColumn();
    return $c;
}
