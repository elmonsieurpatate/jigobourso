<?php
/**
 * Stratégies de « Classement test », par utilisateur. Un document JSON dans `settings` (clé ct_strategies:<id>),
 * même méthode que les filtres secondaires : transaction, verrou, révision optimiste.
 * Chaque stratégie garde sa configuration et ses choix de filtres ; aucune ne touche aux autres, ni aux définitions
 * des filtres (administration), ni à explorer_saved, ni au moteur.
 * Les sept stratégies d'origine (celles des scores V4) n'ont pas de ligne tant qu'elles ne sont pas modifiées :
 * leurs valeurs par défaut sont dans la page. « Restaurer » supprime seulement leur surcharge.
 */
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';

const CT_BUILTIN = ['fast' => 'Croissance rapide', 'regular' => 'Croissance régulière', 'calm' => 'Hausse calme', 'rebound' => 'Rebond', 'mom6' => 'Momentum 6 mois (expérimental)', 'mom12' => 'Momentum 12 mois (expérimental)', 'momrisk' => 'Momentum ajusté du risque (expérimental)'];
const CT_PERIODS = ['week', 'month', 'quarter', 'half', 'year', 'two_year'];   // granularités à pente et R²
const CT_DAY = 'day';                                                           // Jour (1 séance) : facultatif, seule la variation 1J sert de critère
const CT_METRICS = ['slope', 'r2', 'volatility', 'drawdown', 'return', 'volume'];
const CT_MAX_CUSTOM = 30;
/** Présentation par défaut des stratégies d'origine (icône et explications) ; modifiable par chaque utilisateur dans « Mes stratégies ». */
const CT_DEFAULT_META = [
    'fast' => ['icon' => '🚀', 'description' => 'Les titres qui montent très vite : forte hausse moyenne par séance, sur la semaine ET sur le mois.'],
    'regular' => ['icon' => '📈', 'description' => 'Une hausse soutenue et régulière sur un mois et un trimestre : la courbe monte sans grands à-coups.'],
    'calm' => ['icon' => '🌱', 'description' => 'Une hausse douce avec peu de secousses sur un mois et un trimestre : peu de volatilité, peu de baisses.'],
    'rebound' => ['icon' => '🔄', 'description' => 'Les titres qui repartent à la hausse (semaine et mois) alors que le semestre a peu progressé.'],
    'mom6' => ['icon' => '⏳', 'description' => 'Le momentum des 6 derniers mois, dernier mois exclu : on classe les titres qui ont le mieux monté sur le semestre.'],
    'mom12' => ['icon' => '🗓️', 'description' => 'Le momentum des 12 derniers mois, dernier mois exclu : on classe les titres qui ont le mieux monté sur l’année.'],
    'momrisk' => ['icon' => '🛡️', 'description' => 'Le momentum 6 et 12 mois, corrigé du risque : la volatilité et la plus forte baisse pénalisent la note.'],
];
const CT_ICONS = ['📈', '📉', '🚀', '🛡️', '⚖️', '🎯', '⚡', '🔥', '🌱', '💎', '⏳', '💰', '🏦', '🔍', '🔄', '🗓️', '🧭', '🏆', '🌊', '🌙', '☀️', '🌳', '🍀', '🌿', '🐢', '🐇', '🦅', '🐂', '🐻', '🦁', '🧲', '🔋', '🛰️', '🏔️', '⛰️', '🏄', '🚴', '🧘', '🧠', '💡', '🔭', '🔬', '🧪', '⚙️', '🛠️', '🔧', '📊', '📌', '📍', '🔔', '⭐', '🌟', '✨', '💫', '🎲', '♟️', '🧩', '🪙', '💵', '💶', '📦', '🏗️', '🏭', '🛒', '🎢', '🌀', '🌪️', '❄️', '🧊', '🔒', '🔑', '👁️', '🧱', '⚓', '⛵', '🚦', '✅'];

function ct_key(int $uid): string { return 'ct_strategies:' . $uid; }
function ct_json($v): string { return json_encode($v, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR); }
function ct_num($v, float $lo, float $hi, string $what): float {
    if (is_bool($v) || !(is_int($v) || is_float($v)) || !is_finite((float)$v) || $v < $lo || $v > $hi) throw new ApiError($what . ' invalide.', 422);
    return (float)$v;
}
function ct_empty(): array { return ['schema' => 1, 'revision' => 0, 'selected' => 'fast', 'items' => []]; }
function ct_decode(string $json): array {
    $d = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($d) || ($d['schema'] ?? null) !== 1 || !is_array($d['items'] ?? null)) throw new ApiError('Stratégies illisibles : aucun remplacement automatique.', 503);
    return $d;
}
function ct_tree(array $n, int $depth, int &$count): array {
    if (++$count > 200 || $depth > 6) throw new ApiError('Arbre de règles trop grand.', 422);
    if (($n['kind'] ?? null) === 'group') {
        if (!in_array($n['join'] ?? null, ['and', 'or'], true) || !is_array($n['children'] ?? null) || !array_is_list($n['children']) || count($n['children']) > 50) throw new ApiError('Groupe de règles invalide.', 422);
        return ['kind' => 'group', 'join' => $n['join'], 'children' => array_map(fn($c) => is_array($c) ? ct_tree($c, $depth + 1, $count) : throw new ApiError('Règle invalide.', 422), $n['children'])];
    }
    if (($n['kind'] ?? null) !== 'rule' || !in_array($n['metric'] ?? null, CT_METRICS, true) || !in_array($n['period'] ?? null, [...CT_PERIODS, CT_DAY], true) || !in_array($n['op'] ?? null, ['>=', '<=', '>', '<', '='], true)) throw new ApiError('Règle invalide.', 422);
    return ['kind' => 'rule', 'metric' => $n['metric'], 'period' => $n['period'], 'op' => $n['op'], 'value' => ct_num($n['value'] ?? null, -1e12, 1e12, 'Valeur de règle')];
}
/** Reconstruit une configuration propre : aucun champ inconnu n'est conservé. */
function ct_config($c): array {
    if (!is_array($c) || !is_array($c['periods'] ?? null)) throw new ApiError('Configuration de stratégie attendue.', 422);
    $periods = [];
    foreach (CT_PERIODS as $k) {
        $p = $c['periods'][$k] ?? null;
        if (!is_array($p) || !is_bool($p['enabled'] ?? null)) throw new ApiError('Période invalide : ' . $k . '.', 422);
        $periods[$k] = ['enabled' => $p['enabled'], 'slope' => ct_num($p['slope'] ?? null, -1e12, 1e12, 'Pente'), 'r2' => ct_num($p['r2'] ?? null, -1e12, 1e12, 'R²')];
    }
    // Jour : absent des stratégies enregistrées avant son ajout (alors désactivé). Aucun seuil de pente ni de R² : une variation minimale facultative (en %).
    $d = $c['periods'][CT_DAY] ?? null;
    if ($d !== null && (!is_array($d) || !is_bool($d['enabled'] ?? null))) throw new ApiError('Période invalide : ' . CT_DAY . '.', 422);
    $periods = [CT_DAY => ['enabled' => (bool)($d['enabled'] ?? false), 'return' => ($d['return'] ?? null) === null ? null : ct_num($d['return'], -100, 10000, 'Variation 1J')]] + $periods;
    $extra = [];
    if (!is_array($c['extra'] ?? []) || count($c['extra'] ?? []) > 20) throw new ApiError('Seuils facultatifs invalides.', 422);
    foreach ($c['extra'] ?? [] as $x) {
        if (!is_array($x) || !in_array($x['metric'] ?? null, CT_METRICS, true) || !in_array($x['op'] ?? null, ['>=', '<='], true)) throw new ApiError('Seuil facultatif invalide.', 422);
        $extra[] = ['metric' => $x['metric'], 'op' => $x['op'], 'value' => ct_num($x['value'] ?? null, 0, 1e12, 'Seuil')];
    }
    $out = ['periods' => $periods, 'extra' => $extra, 'join' => in_array($c['join'] ?? 'and', ['and', 'or'], true) ? ($c['join'] ?? 'and') : throw new ApiError('Combinaison invalide.', 422)];
    if (isset($c['tree'])) { $n = 0; $out['tree'] = ct_tree($c['tree'], 0, $n); }
    return $out;
}
/** Choix de filtres propres à la stratégie : sélection + catégories connues au moment du choix (même format que l'ancien stockage local). */
function ct_filters($f): array {
    if ($f === null || $f === []) return [];
    if (!is_array($f) || count($f) > 40) throw new ApiError('Choix de filtres invalides.', 422);
    $out = [];
    foreach ($f as $id => $o) {
        if (!is_string($id) || !preg_match('/^[a-z][a-z0-9_]{0,40}$/', $id) || !is_array($o)) throw new ApiError('Choix de filtre invalide.', 422);
        $lists = [];
        foreach (['selected', 'known'] as $k) {
            $l = $o[$k] ?? null;
            if (!is_array($l) || !array_is_list($l) || count($l) > 400) throw new ApiError('Liste de catégories invalide.', 422);
            foreach ($l as $v) if (!is_string($v) || $v === '' || mb_strlen($v) > 120) throw new ApiError('Identifiant de catégorie invalide.', 422);
            $lists[$k] = array_values(array_unique($l));
        }
        $out[$id] = $lists;
    }
    return $out;
}
function ct_name(string $name, array $doc, ?string $exceptId): string {
    $name = trim(preg_replace('/\s+/u', ' ', $name));
    if ($name === '' || mb_strlen($name) > 60) throw new ApiError('Nom de 1 à 60 caractères requis.', 422);
    $low = mb_strtolower($name);
    foreach (CT_BUILTIN as $id => $label) if ($id !== $exceptId && mb_strtolower($label) === $low) throw new ApiError('Ce nom existe déjà.', 422);
    foreach ($doc['items'] as $it) if ($it['id'] !== $exceptId && mb_strtolower($it['name']) === $low) throw new ApiError('Ce nom existe déjà.', 422);
    return $name;
}
function ct_view(array $doc): array {
    if (!isset(CT_BUILTIN[$doc['selected']]) && !array_filter($doc['items'], fn($i) => $i['id'] === $doc['selected'])) $doc['selected'] = 'fast';
    return ['schema' => 1, 'revision' => $doc['revision'], 'selected' => $doc['selected'], 'builtin' => CT_BUILTIN, 'max_custom' => CT_MAX_CUSTOM, 'items' => $doc['items'],
            'meta' => (object)array_merge(array_map(fn($m) => $m + ['enabled' => true], CT_DEFAULT_META), $doc['meta'] ?? []), 'icons' => CT_ICONS];
}
function ct_read(int $uid): array {
    $json = q('SELECT value_json FROM settings WHERE name=?', [ct_key($uid)])->fetchColumn();
    return ct_view($json === false ? ct_empty() : ct_decode($json));
}
/** Document brut des stratégies d'un utilisateur (items seuls utiles aux autres pages). */
function ct_all(int $uid): array {
    $json = q('SELECT value_json FROM settings WHERE name=?', [ct_key($uid)])->fetchColumn();
    return $json === false ? ct_empty() : ct_decode($json);
}
/** Configuration enregistrée d'une stratégie de l'utilisateur (surcharge d'une intégrée ou stratégie personnelle) et son nom ; null si aucune ligne (une intégrée utilise alors ses valeurs par défaut du moteur). */
function ct_saved(int $uid, string $id): ?array {
    $json = q('SELECT value_json FROM settings WHERE name=?', [ct_key($uid)])->fetchColumn();
    if ($json === false) return null;
    foreach (ct_decode($json)['items'] as $it) if ($it['id'] === $id) return ['config' => $it['config'] ?? null, 'name' => $it['name'] ?? $id, 'builtin' => !empty($it['builtin'])];
    return null;
}
/** Nom affiché d'une stratégie du Classement, ou null si inconnue. */
function ct_label(int $uid, string $id): ?string {
    if (isset(CT_BUILTIN[$id])) return CT_BUILTIN[$id];
    $s = ct_saved($uid, $id);
    return $s ? $s['name'] : null;
}
/** Présentation d'une stratégie (icône, explications, active ou non), séparée de sa configuration. */
function ct_meta(array $in, array $old): array {
    $icon = $in['icon'] ?? $old['icon'] ?? CT_ICONS[0];
    if (!is_string($icon) || !in_array($icon, CT_ICONS, true)) throw new ApiError('Icône inconnue.', 422);
    $desc = $in['description'] ?? $old['description'] ?? '';
    if (!is_string($desc)) throw new ApiError('Explications invalides.', 422);
    $desc = trim(preg_replace('/[^\P{C}\n]/u', '', str_replace("\r", '', $desc)));
    if (mb_strlen($desc) > 300) throw new ApiError('Explications de 300 caractères au maximum.', 422);
    $en = $in['enabled'] ?? $old['enabled'] ?? true;
    if (!is_bool($en)) throw new ApiError('État invalide.', 422);
    return ['icon' => $icon, 'description' => $desc, 'enabled' => $en];
}
/** Identifiants actifs, dans l'ordre d'affichage. */
function ct_enabled_ids(array $doc): array {
    $ids = array_merge(array_keys(CT_BUILTIN), array_map(fn($i) => $i['id'], array_filter($doc['items'], fn($i) => !$i['builtin'])));
    return array_values(array_filter($ids, fn($id) => ($doc['meta'][$id]['enabled'] ?? true) !== false));
}
function ct_write(int $uid, array $req): array {
    for ($attempt = 0; ; $attempt++) {
        try { return ct_write_once($uid, $req); }
        catch (PDOException $e) {
            if (!in_array((int)($e->errorInfo[1] ?? 0), [1205, 1213], true)) throw $e;
            if ($attempt >= 3) throw new ApiError('Les stratégies sont occupées. Réessayez dans un instant.', 409);
            usleep(10000 * ($attempt + 1));
        }
    }
}
function ct_write_once(int $uid, array $req): array {
    $db = db(); $db->beginTransaction();
    try {
        $key = ct_key($uid);
        $json = q('SELECT value_json FROM settings WHERE name=? FOR UPDATE', [$key])->fetchColumn();
        if ($json === false) {
            q('INSERT IGNORE INTO settings(name,value_json,updated_at) VALUES (?,?,?)', [$key, ct_json(ct_empty()), now_utc()]);
            $json = q('SELECT value_json FROM settings WHERE name=? FOR UPDATE', [$key])->fetchColumn();
        }
        $doc = ct_decode($json);
        $action = $req['action'] ?? null; $id = $req['id'] ?? null;
        if (!is_string($action)) throw new ApiError('Action requise.', 422);
        if ($action !== 'select' && ($req['revision'] ?? null) !== $doc['revision']) throw new ApiError('Les stratégies ont changé dans une autre session. Rechargez avant d’enregistrer.', 409);
        $find = function (?string $sid) use (&$doc) { foreach ($doc['items'] as $i => $it) if ($it['id'] === $sid) return $i; return null; };
        $now = now_utc(); $changed = true;
        if ($action === 'select') {
            if (!is_string($id) || (!isset(CT_BUILTIN[$id]) && $find($id) === null)) throw new ApiError('Stratégie inconnue.', 404);
            if (!in_array($id, ct_enabled_ids($doc), true)) throw new ApiError('Cette stratégie est désactivée.', 422);
            $changed = $doc['selected'] !== $id; $doc['selected'] = $id;
        } elseif ($action === 'save') {
            if (!is_string($id)) throw new ApiError('Identifiant requis.', 422);
            $i = $find($id);
            if ($i === null && !isset(CT_BUILTIN[$id])) throw new ApiError('Stratégie inconnue.', 404);
            $item = ['id' => $id, 'name' => $i === null ? CT_BUILTIN[$id] : $doc['items'][$i]['name'], 'builtin' => isset(CT_BUILTIN[$id]),
                     'config' => ct_config($req['config'] ?? null), 'filters' => ct_filters($req['filters'] ?? null), 'updated_at' => $now];
            if ($i === null) $doc['items'][] = $item; else $doc['items'][$i] = $item;
        } elseif ($action === 'create') {
            if (count(array_filter($doc['items'], fn($it) => !$it['builtin'])) >= CT_MAX_CUSTOM) throw new ApiError(CT_MAX_CUSTOM . ' stratégies personnelles au maximum.', 422);
            $nid = 'cs-' . bin2hex(random_bytes(8));
            $doc['items'][] = ['id' => $nid, 'name' => ct_name((string)($req['name'] ?? ''), $doc, null), 'builtin' => false,
                               'config' => ct_config($req['config'] ?? null), 'filters' => ct_filters($req['filters'] ?? null), 'updated_at' => $now];
            $doc['meta'][$nid] = ct_meta(['icon' => $req['icon'] ?? null, 'description' => $req['description'] ?? null, 'enabled' => true], []);
            $doc['selected'] = $nid;
        } elseif ($action === 'meta') {
            $i = is_string($id) ? $find($id) : null;
            if (!is_string($id) || ($i === null && !isset(CT_BUILTIN[$id]))) throw new ApiError('Stratégie inconnue.', 404);
            if (isset($req['name']) && ($i === null || $doc['items'][$i]['builtin'])) {
                if ($req['name'] !== CT_BUILTIN[$id] && !($i !== null && $req['name'] === $doc['items'][$i]['name'] && !$doc['items'][$i]['builtin'])) throw new ApiError('Le nom d’une stratégie d’origine ne change pas.', 422);
            } elseif (isset($req['name'])) {
                $doc['items'][$i]['name'] = ct_name((string)$req['name'], $doc, $id);
            }
            $in = array_intersect_key($req, ['icon' => 1, 'description' => 1, 'enabled' => 1]);
            $doc['meta'][$id] = ct_meta($in, $doc['meta'][$id] ?? (CT_DEFAULT_META[$id] ?? []));
            if (!ct_enabled_ids($doc)) throw new ApiError('Au moins une stratégie doit rester active.', 422);
            if ($i !== null && !$doc['items'][$i]['builtin']) $doc['items'][$i]['updated_at'] = $now;
        } elseif ($action === 'rename') {
            $i = is_string($id) ? $find($id) : null;
            if ($i === null || $doc['items'][$i]['builtin']) throw new ApiError('Seules les stratégies personnelles se renomment.', 422);
            $doc['items'][$i]['name'] = ct_name((string)($req['name'] ?? ''), $doc, $id); $doc['items'][$i]['updated_at'] = $now;
        } elseif ($action === 'delete') {
            $i = is_string($id) ? $find($id) : null;
            if (is_string($id) && isset(CT_BUILTIN[$id])) throw new ApiError('Les stratégies d’origine ne se suppriment pas : utilisez « Restaurer ».', 422);
            if ($i === null) throw new ApiError('Stratégie inconnue.', 404);
            array_splice($doc['items'], $i, 1); unset($doc['meta'][$id]);
            if (!ct_enabled_ids($doc)) throw new ApiError('Au moins une stratégie doit rester active.', 422);
        } elseif ($action === 'restore') {
            if (!is_string($id) || !isset(CT_BUILTIN[$id])) throw new ApiError('Seules les stratégies d’origine ont des valeurs par défaut.', 422);
            $i = $find($id); if ($i === null) $changed = false; else array_splice($doc['items'], $i, 1);
        } else throw new ApiError('Action inconnue.', 422);
        if ($action !== 'select') { $en = ct_enabled_ids($doc); if (!in_array($doc['selected'], $en, true)) { $doc['selected'] = $en[0]; $changed = true; } }
        if ($changed) {
            if ($action !== 'select') $doc['revision']++;
            $doc['items'] = array_values($doc['items']);
            if (strlen(ct_json($doc)) > 900000) throw new ApiError('Trop de données de stratégies.', 422);
            q('UPDATE settings SET value_json=?,updated_at=? WHERE name=?', [ct_json($doc), $now, $key]);
        }
        $db->commit();
        return ct_view($doc);
    } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); throw $e; }
}
