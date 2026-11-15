<?php
require_once __DIR__ . '/../lib/db.php';
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/settings.php';
require_once __DIR__ . '/../lib/account.php';

require_once __DIR__ . '/../services/auth_actions.php';

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
        $registered = auth_register($b, client_ip());
        $id = $registered['id']; $username = $registered['username']; $email = $registered['email'];
        // Réponse immédiate, puis envoi des courriers (bienvenue + alerte aux administrateurs) : le transport SMTP ne retarde plus l'inscription.
        out_then(['user_id' => $id, 'welcome_mail' => 'queued'], function () use ($username, $email) {
            send_welcome_mail($username, $email);
            notify_admins_new_account($username, $email);
        });
        return [];
    },
    'auth/password' => function () { need_post(); $u = require_user(); return auth_change_password($u, body(), (string)($_COOKIE[COOKIE] ?? '')); },
    'auth/recover' => function () {
        need_post();$b=body();$email=mb_strtolower(str_in($b,'email',190));
        $u = auth_recovery_user($email);
        // Réponse identique et immédiate que l'adresse existe ou non (ni message d'échec d'envoi, ni écart de durée) ; l'envoi se fait après la réponse.
        out_then(['ok'=>true,'message'=>'Si cette adresse correspond à un compte actif, un lien a été envoyé. Vérifiez aussi les courriers indésirables.'], function () use ($u,$email) {
            if ($u && !issue_account_link($u,'reset',$email)) error_log('account_mail: recovery link not delivered');
        });
    },
    'auth/reset' => function () { need_post(); return auth_reset_password(body(), client_ip()); },
    'auth/account' => function () { need_post();return update_account(require_user(),body()); },
    'auth/verify-email' => function () { need_post(); return auth_verify_email(body(), client_ip()); },
    'auth/prefs' => function () { need_post(); $u = require_user(); return auth_save_preferences($u, body()); },
];
