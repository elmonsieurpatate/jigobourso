<?php
/**
 * Colonnes, ordre, largeurs, tri et filtres initiaux des tableaux (Explorer / Scores), pour ordinateur et mobile : quatre configurations indépendantes.
 * Un seul document JSON dans `settings` (clé table_layouts), révision optimiste, jamais mélangé aux réglages financiers.
 * Le catalogue des colonnes (identifiants, libellés, tri possible) est `app/config/table_columns.json` : source unique pour la validation, l'administration et les pages.
 * Compatibilité : un identifiant inconnu du catalogue est ignoré à la lecture ; une colonne ajoutée au catalogue est rangée en fin de liste avec sa visibilité par défaut.
 */
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';

const TL_KEY = 'table_layouts';
const TL_DEVICES = ['desktop', 'mobile'];
const TL_VERDICTS = ['retained', 'excluded', 'all'];
const TL_PAGE_SIZES = [25, 50, 100];

function tl_catalog(): array {
    static $c = null;
    if ($c === null) $c = json_decode(file_get_contents(__DIR__ . '/../config/table_columns.json'), true, 512, JSON_THROW_ON_ERROR);
    return $c;
}
function tl_json($v): string { return json_encode($v, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR); }
function tl_page(string $page): array {
    $c = tl_catalog()['pages'][$page] ?? null;
    if ($c === null) throw new ApiError('Page inconnue.', 422);
    return $c;
}
function tl_device(string $d): string {
    if (!in_array($d, TL_DEVICES, true)) throw new ApiError('Affichage inconnu.', 422);
    return $d;
}
/** Configuration par défaut d'une page et d'un affichage (colonnes dans l'ordre du catalogue). */
function tl_default(string $page, string $device): array {
    $p = tl_page($page); $d = $p['defaults'][$device];
    $cols = [];
    foreach ($p['columns'] as $col) $cols[] = ['id' => $col['id'], 'visible' => in_array($col['id'], $d['visible'], true), 'width' => null];
    return ['columns' => $cols, 'sort' => $d['sort'], 'filters' => $d['filters']];
}
/**
 * Nettoie une configuration. $strict : erreur 422 si elle est incomplète ou invalide (enregistrement) ; sinon lecture tolérante (compatibilité).
 */
function tl_clean(string $page, string $device, $cfg, bool $strict): array {
    $p = tl_page($page); $byId = [];
    foreach ($p['columns'] as $col) $byId[$col['id']] = $col;
    if (!is_array($cfg)) { if ($strict) throw new ApiError('Configuration attendue.', 422); return tl_default($page, $device); }
    $def = tl_default($page, $device);
    $defVisible = []; foreach ($def['columns'] as $c) $defVisible[$c['id']] = $c['visible'];
    $cols = []; $seen = [];
    foreach (is_array($cfg['columns'] ?? null) ? $cfg['columns'] : [] as $c) {
        $id = is_array($c) ? ($c['id'] ?? null) : null;
        if (!is_string($id) || !isset($byId[$id])) { if ($strict) throw new ApiError('Colonne inconnue.', 422); continue; }
        if (isset($seen[$id])) { if ($strict) throw new ApiError('Colonne en double : ' . $id . '.', 422); continue; }
        $w = $c['width'] ?? null;
        if ($w !== null && (!is_int($w) && !(is_float($w) && floor($w) == $w) || $w < 48 || $w > 480)) { if ($strict) throw new ApiError('Largeur de ' . $id . ' : 48 à 480 pixels.', 422); $w = null; }
        $vis = $c['visible'] ?? null;
        if (!is_bool($vis)) { if ($strict) throw new ApiError('Visibilité de ' . $id . ' invalide.', 422); $vis = $defVisible[$id]; }
        $seen[$id] = true; $cols[] = ['id' => $id, 'visible' => $vis, 'width' => $w === null ? null : (int)$w];
    }
    foreach ($p['columns'] as $col) if (!isset($seen[$col['id']])) {
        if ($strict) throw new ApiError('Colonne manquante : ' . $col['id'] . '.', 422);
        $cols[] = ['id' => $col['id'], 'visible' => $defVisible[$col['id']], 'width' => null];     // colonne ajoutée depuis l'enregistrement
    }
    if (!array_filter($cols, fn($c) => $c['id'] === 'name' && $c['visible'])) {
        if ($strict) throw new ApiError('La colonne Titre doit rester visible.', 422);
        foreach ($cols as &$c) if ($c['id'] === 'name') $c['visible'] = true;
        unset($c);
    }
    $sort = []; $keys = [];
    foreach (is_array($cfg['sort'] ?? null) ? $cfg['sort'] : [] as $s) {
        $k = is_array($s) ? ($s['key'] ?? null) : null; $dir = is_array($s) ? ($s['dir'] ?? null) : null;
        if (!is_string($k) || !isset($byId[$k]) || empty($byId[$k]['sortable']) || !in_array($dir, ['asc', 'desc'], true) || isset($keys[$k]) || count($sort) >= 3) {
            if ($strict) throw new ApiError('Tri invalide : colonne triable, sens croissant ou décroissant, trois critères au plus, sans doublon.', 422);
            continue;
        }
        $keys[$k] = true; $sort[] = ['key' => $k, 'dir' => $dir];
    }
    $f = is_array($cfg['filters'] ?? null) ? $cfg['filters'] : [];
    $verdict = $f['verdict'] ?? $def['filters']['verdict'];
    if (!in_array($verdict, TL_VERDICTS, true)) { if ($strict) throw new ApiError('Statut de stratégie initial invalide.', 422); $verdict = $def['filters']['verdict']; }
    $filters = ['verdict' => $verdict];
    if (isset($def['filters']['page_size'])) {
        $ps = $f['page_size'] ?? $def['filters']['page_size'];
        if (!in_array($ps, TL_PAGE_SIZES, true)) { if ($strict) throw new ApiError('Nombre de lignes par page : 25, 50 ou 100.', 422); $ps = $def['filters']['page_size']; }
        $filters['page_size'] = $ps;
    }
    return ['columns' => $cols, 'sort' => $sort, 'filters' => $filters];
}
function tl_decode($json): array {
    $d = $json === false ? null : json_decode($json, true);
    return is_array($d) && ($d['schema'] ?? null) === 1 && is_array($d['layouts'] ?? null) ? $d : ['schema' => 1, 'revision' => 0, 'layouts' => []];
}
/** Les quatre configurations effectives (enregistrées, sinon par défaut) + le catalogue. Lisible par tout utilisateur connecté : aucune donnée de titre. */
function tl_key(?int $uid): string { return $uid ? TL_KEY . ':' . $uid : TL_KEY; }
/** $uid = null : document commun (réglage par défaut hérité de l'administration). $uid : réglages PERSONNELS ; une configuration jamais enregistrée par l'utilisateur reprend le défaut commun. */
function tl_read(?int $uid = null): array {
    $doc = tl_decode(q('SELECT value_json FROM settings WHERE name=?', [tl_key($uid)])->fetchColumn());
    $base = $uid ? tl_decode(q('SELECT value_json FROM settings WHERE name=?', [TL_KEY])->fetchColumn()) : ['layouts' => []];
    $out = []; $saved = [];
    foreach (array_keys(tl_catalog()['pages']) as $page) foreach (TL_DEVICES as $dev) {
        $k = $page . '.' . $dev;
        $out[$k] = tl_clean($page, $dev, $doc['layouts'][$k] ?? $base['layouts'][$k] ?? tl_default($page, $dev), false);
        $saved[$k] = isset($doc['layouts'][$k]);
    }
    return ['schema' => 1, 'revision' => (int)$doc['revision'], 'catalog' => tl_catalog()['pages'], 'layouts' => $out, 'saved' => $saved,
            'defaults' => array_merge(...array_map(fn($p) => array_combine(array_map(fn($d) => $p . '.' . $d, TL_DEVICES), array_map(fn($d) => tl_default($p, $d), TL_DEVICES)), array_keys(tl_catalog()['pages'])))];
}
/** action = save (config) ou reset ; ne touche que la configuration visée. */
function tl_write(array $req, ?int $uid = null): array {
    $key = tl_key($uid);
    $page = (string)($req['page'] ?? ''); $dev = tl_device((string)($req['device'] ?? '')); tl_page($page);
    $action = $req['action'] ?? 'save';
    if (!in_array($action, ['save', 'reset'], true)) throw new ApiError('Action inconnue.', 422);
    $clean = $action === 'save' ? tl_clean($page, $dev, $req['config'] ?? null, true) : null;
    tx(function () use ($key, $req, $page, $dev, $action, $clean) {
        q('INSERT IGNORE INTO settings(name,value_json,updated_at) VALUES (?,?,?)', [$key, tl_json(['schema' => 1, 'revision' => 0, 'layouts' => (object)[]]), now_utc()]);
        $doc = tl_decode(q('SELECT value_json FROM settings WHERE name=? FOR UPDATE', [$key])->fetchColumn());
        if (($req['revision'] ?? null) !== $doc['revision']) throw new ApiError('Ces réglages ont changé dans une autre session. Rechargez avant d’enregistrer.', 409);
        $k = $page . '.' . $dev;
        if ($action === 'save') $doc['layouts'][$k] = $clean; else unset($doc['layouts'][$k]);
        $doc['revision']++;
        if (!$doc['layouts']) $doc['layouts'] = (object)[];
        q('UPDATE settings SET value_json=?, updated_at=? WHERE name=?', [tl_json($doc), now_utc(), $key]);
    });
    return tl_read($uid);
}
