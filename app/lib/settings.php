<?php
require_once __DIR__ . '/db.php';
// Lecture d'un réglage global (table settings) ; $default si absent.
function setting_value(string $name, $default) {
    $r = q('SELECT value_json FROM settings WHERE name = ?', [$name])->fetch();
    return $r ? json_decode($r['value_json'], true) : $default;
}