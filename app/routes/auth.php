<?php
require_once __DIR__ . '/../lib/account.php';

return [
    'auth/me' => function () {
        $u = current_user();
        return ['user' => $u ? public_user($u) : null, 'registration_open' => (bool)setting_value('invite_code', '')];
    },
    'auth/login' => function () {
        need_post();
        $b = body();
        return ['user' => login(str_in($b, 'username', 190), password_input($b, 'password'), ($b['remember'] ?? false) === true)];
    },
    'auth/logout' => function () { need_post(); logout(); return ['ok' => true]; },
    'auth/register' => function () {
        need_post();
        $b = body();
        $code = (string)setting_value('invite_code', '');
        $key = attempt_key('register', client_ip());
        if (login_blocked($key)) throw new ApiError('Trop d’essais : réessayez plus tard', 429);
        if ($code === '' || !hash_equals(mb_strtolower($code), mb_strtolower(str_in($b, 'code', 60)))) {
            q('INSERT INTO login_attempts(username, ip, at) VALUES (?,?,?)', [$key, client_ip(), now_utc()]);
            throw new ApiError('Mot d’invitation incorrect ou inscriptions fermées', 403);
        }
        $id = create_user(str_in($b, 'username', 30), password_input($b, 'password'), str_in($b, 'email', 190, false) ?: null, false);
        return ['user_id' => $id];
    },
    'auth/password' => function () {
        need_post();
        $u = require_user();
        $b = body();
        $db=db();$db->beginTransaction();
        try {
            $fresh=q('SELECT * FROM users WHERE id=? FOR UPDATE',[$u['id']])->fetch();
            if (!password_verify(password_input($b,'current'),$fresh['pass_hash'])) throw new ApiError('Mot de passe actuel incorrect',403);
            $new=password_input($b,'new');valid_password($new);
            q('UPDATE users SET pass_hash=? WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);
            q('UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',[now_utc(),$u['id']]);
            q('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',[$u['id'],hash('sha256',$_COOKIE[COOKIE])]);
            $db->commit();
        } catch(Throwable $e) {if($db->inTransaction())$db->rollBack();throw $e;}
        notify_account_change($fresh,'password');
        return ['ok' => true];
    },
    'auth/recover' => function () {
        need_post();$b=body();$email=mb_strtolower(str_in($b,'email',190));
        account_throttle('recover',$email);
        $u=q('SELECT * FROM users WHERE email=? AND active=1',[$email])->fetch();
        // Réponse identique et immédiate que l'adresse existe ou non (ni message d'échec d'envoi, ni écart de durée) ; l'envoi se fait après la réponse.
        out_then(['ok'=>true,'message'=>'Si cette adresse correspond à un compte actif, un lien a été envoyé. Vérifiez aussi les courriers indésirables.'], function () use ($u,$email) {
            if ($u && !issue_account_link($u,'reset',$email)) error_log('account_mail: recovery link not delivered');
        });
    },
    'auth/reset' => function () {
        need_post();$b=body();account_throttle('reset',client_ip());$new=password_input($b,'new');valid_password($new);
        [$user]=consume_account_link(str_in($b,'token',64),'reset',function($u,$t) use($new) {
            q('UPDATE users SET pass_hash=? WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);
            q('DELETE FROM sessions WHERE user_id=?',[$u['id']]);
        });
        notify_account_change($user,'password');
        return ['ok'=>true];
    },
    'auth/account' => function () { need_post();return update_account(require_user(),body()); },
    'auth/verify-email' => function () {
        need_post();$b=body();account_throttle('verify',client_ip());
        [$user,$token]=consume_account_link(str_in($b,'token',64),'email',function($u,$t) {
            if (q('SELECT id FROM users WHERE email=? AND id<>?',[$t['target_email'],$u['id']])->fetch()) throw new ApiError('Cette adresse n’est plus disponible.',409);
            q('UPDATE users SET email=? WHERE id=?',[$t['target_email'],$u['id']]);
        });
        notify_account_change($user,'email',$token['target_email']); // l'ancienne adresse est prévenue du remplacement
        return ['ok'=>true];
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
