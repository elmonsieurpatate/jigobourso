<?php
// Cas d’usage auth : entrées explicites, autorisations métier conservées.
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/account.php';
require_once __DIR__ . '/../lib/settings.php';

function auth_change_password(array $u, array $b, string $sessionToken): array {
    $fresh=tx(function () use ($u,$b,$sessionToken) {
        $fresh=q('SELECT * FROM users WHERE id=? FOR UPDATE',[$u['id']])->fetch();
        if (!password_verify(password_input($b,'current'),$fresh['pass_hash'])) throw new ApiError('Mot de passe actuel incorrect',403);
        $new=password_input($b,'new');valid_password($new);
        q('UPDATE users SET pass_hash=? WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);
        q('UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',[now_utc(),$u['id']]);
        q('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',[$u['id'],hash('sha256',$sessionToken)]);
        return $fresh;
    });
    notify_account_change($fresh,'password');
    return ['ok' => true];
}

function auth_reset_password(array $b, string $ip): array {
    account_throttle('reset',$ip);$new=password_input($b,'new');valid_password($new);
    [$user]=consume_account_link(str_in($b,'token',64),'reset',function($u,$t) use($new) {
        q('UPDATE users SET pass_hash=? WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);
        q('DELETE FROM sessions WHERE user_id=?',[$u['id']]);
    });
    notify_account_change($user,'password');
    return ['ok'=>true];
}

function auth_verify_email(array $b, string $ip): array {
    account_throttle('verify',$ip);
    [$user,$token]=consume_account_link(str_in($b,'token',64),'email',function($u,$t) {
        if (q('SELECT id FROM users WHERE email=? AND id<>?',[$t['target_email'],$u['id']])->fetch()) throw new ApiError('Cette adresse n’est plus disponible.',409);
        q('UPDATE users SET email=? WHERE id=?',[$t['target_email'],$u['id']]);
    });
    notify_account_change($user,'email',$token['target_email']); // l'ancienne adresse est prévenue du remplacement
    return ['ok'=>true];
}

function auth_save_preferences(array $u, array $b): array {
    $allowed = ['mode' => ['simple', 'advanced'], 'theme' => ['light', 'dark', 'auto'], 'help_level' => ['beginner', 'expert']];
    $prefs = $u['prefs_json'] ? json_decode($u['prefs_json'], true) : [];
    foreach ($allowed as $k => $values) if (isset($b[$k]) && in_array($b[$k], $values, true)) $prefs[$k] = $b[$k];
    if (isset($b['help_last']) && is_string($b['help_last']) && preg_match('/^[a-z0-9-]{1,40}$/', $b['help_last'])) $prefs['help_last'] = $b['help_last']; // dernier chapitre de l'aide
    q('UPDATE users SET prefs_json = ? WHERE id = ?', [json_encode($prefs), $u['id']]);
    return ['prefs' => $prefs];
}

function auth_register(array $b, string $ip): array {
    $code = (string)setting_value('invite_code', '');
    $key = attempt_key('register', $ip);
    if (login_blocked($key)) throw new ApiError('Trop d’essais : réessayez plus tard', 429);
    if ($code === '' || !hash_equals(mb_strtolower($code), mb_strtolower(str_in($b, 'code', 60)))) {
        q('INSERT INTO login_attempts(username, ip, at) VALUES (?,?,?)', [$key, $ip, now_utc()]);
        throw new ApiError('Mot d’invitation incorrect ou inscriptions fermées', 403);
    }
    $email = mb_strtolower(trim(str_in($b, 'email', 190, false)));
    if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) throw new ApiError('Une adresse e-mail valide est nécessaire pour créer un compte', 422);
    if (q('SELECT 1 FROM users WHERE email = ?', [$email])->fetch()) throw new ApiError('Cette adresse e-mail est déjà utilisée', 409);
    $username = str_in($b, 'username', 30);
    $id = create_user($username, password_input($b, 'password'), $email, false);
    return ['id' => $id, 'username' => $username, 'email' => $email];
}

function auth_recovery_user(string $email): ?array {
    account_throttle('recover',$email);
    $u=q('SELECT * FROM users WHERE email=? AND active=1',[$email])->fetch();
    return $u ?: null;
}
