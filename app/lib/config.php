<?php
// Configuration unique, lue dans l'environnement (jamais d'identifiant dans le code).
// Sources : variables d'environnement, puis fichier KEY=valeur hors racine web (JIGO_ENV_FILE, sinon <racine>/private/env) :
// l'hébergement mutualisé ne transmet pas d'environnement au PHP web.
function cfg(string $name, $default = null) {
    static $file = null;
    $v = getenv($name);
    if ($v !== false && $v !== '') return $v;
    if ($file === null) {
        $file = [];
        $path = getenv('JIGO_ENV_FILE') ?: dirname(__DIR__, 2) . '/private/env';
        if (is_readable($path)) {
            foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
                if ($line[0] === '#' || strpos($line, '=') === false) continue;
                [$k, $val] = explode('=', $line, 2);
                $val = trim($val);
                if (strlen($val) >= 2 && ($val[0] === "'" || $val[0] === '"') && $val[-1] === $val[0]) $val = substr($val, 1, -1);
                $file[trim($k)] = $val;
            }
        }
    }
    return ($file[$name] ?? '') !== '' ? $file[$name] : $default;
}
function engine_root(): string { return cfg('JIGO_ENGINE_ROOT', dirname(__DIR__, 2)); }
function python_bin(): string { return cfg('JIGO_PYTHON', engine_root() . '/.venv/bin/python'); }
