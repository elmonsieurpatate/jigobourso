<?php
require_once __DIR__ . '/../lib/auth.php';

return [
    'auth/me' => function () {
        $u = current_user();
        return ['user' => $u ? public_user($u) : null, 'registration_open' => (bool)setting_value('invite_code', '')];
    },
    'auth/login' => function () {
        need_post();
        $b = body();
        return ['user' => login(str_in($b, 'username', 30), str_in($b, 'password', 200))];
    },
    'auth/logout' => function () { need_post(); logout(); return ['ok' => true]; },
    'auth/register' => function () {
        need_post();
        $b = body();
        $code = (string)setting_value('invite_code', '');
        $key = 'register:' . client_ip();
        if (login_blocked($key)) throw new ApiError('Trop d’essais : réessayez plus tard', 429);
        if ($code === '' || !hash_equals(mb_strtolower($code), mb_strtolower(str_in($b, 'code', 60)))) {
            q('INSERT INTO login_attempts(username, ip, at) VALUES (?,?,?)', [$key, client_ip(), now_utc()]);
            throw new ApiError('Mot d’invitation incorrect ou inscriptions fermées', 403);
        }
        $id = create_user(str_in($b, 'username', 30), str_in($b, 'password', 200), str_in($b, 'email', 190, false) ?: null, false);
        return ['user_id' => $id];
    },
    'auth/password' => function () {
        need_post();
        $u = require_user();
        $b = body();
        if (!password_verify(str_in($b, 'current', 200), $u['pass_hash'])) throw new ApiError('Mot de passe actuel incorrect', 403);
        $new = str_in($b, 'new', 200);
        valid_password($new);
        q('UPDATE users SET pass_hash = ? WHERE id = ?', [password_hash($new, PASSWORD_DEFAULT), $u['id']]);
        q('DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?', [$u['id'], hash('sha256', $_COOKIE[COOKIE])]);
        return ['ok' => true];
    },
    'auth/prefs' => function () {
        need_post();
        $u = require_user();
        $b = body();
        $allowed = ['mode' => ['simple', 'advanced'], 'theme' => ['light', 'dark', 'auto']];
        $prefs = $u['prefs_json'] ? json_decode($u['prefs_json'], true) : [];
        foreach ($allowed as $k => $values) if (isset($b[$k]) && in_array($b[$k], $values, true)) $prefs[$k] = $b[$k];
        q('UPDATE users SET prefs_json = ? WHERE id = ?', [json_encode($prefs), $u['id']]);
        return ['prefs' => $prefs];
    },
];

function setting_value(string $name, $default) {
    $r = q('SELECT value_json FROM settings WHERE name = ?', [$name])->fetch();
    return $r ? json_decode($r['value_json'], true) : $default;
}
