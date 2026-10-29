<?php
require_once __DIR__ . '/auth.php';
require_once __DIR__ . '/mail.php';
function password_input(array $b, string $key): string {
    if (!isset($b[$key]) || !is_string($b[$key]) || strlen($b[$key]) > 200 || strpos($b[$key], "\0") !== false) throw new ApiError('Mot de passe invalide',422);
    return $b[$key];
}
function account_throttle(string $purpose, string $identity): void {
    foreach ([['ip:'.client_ip(),20],['identity:'.mb_strtolower($identity),in_array($purpose,['reset','verify'],true)?20:3]] as [$value,$limit]) {
        $hash=hash('sha256',$purpose.':'.$value);
        if ((int)q('SELECT COUNT(*) FROM account_attempts WHERE scope_hash=? AND at>?',[$hash,gmdate('Y-m-d H:i:s',time()-3600)])->fetchColumn()>=$limit)
            throw new ApiError('Trop de demandes : réessayez plus tard.',429);
        q('INSERT INTO account_attempts(scope_hash,at) VALUES (?,?)',[$hash,now_utc()]);
    }
}
function account_stamp(array $u): string { return hash('sha256',$u['pass_hash']."\0".($u['email'] ?? '')); }
function issue_account_link(array $u, string $purpose, string $email): bool {
    $raw=bin2hex(random_bytes(32));$hash=hash('sha256',$raw);
    q('INSERT INTO account_tokens(token_hash,user_id,purpose,target_email,auth_stamp,created_at,expires_at) VALUES (?,?,?,?,?,?,?)',
      [$hash,$u['id'],$purpose,$email,account_stamp($u),now_utc(),gmdate('Y-m-d H:i:s',time()+1800)]);
    // Fragments never travel in HTTP request URLs, proxy logs or Referer headers.
    $url='https://jigobourso.turnjoy.dev/'.($purpose==='reset'?'reset.html':'verify-email.html').'#token='.$raw;
    $message=($purpose==='reset'?'Vous avez demandé à réinitialiser votre mot de passe.':'Confirmez votre nouvelle adresse e-mail.')."\n\n".$url."\n\nCe lien expire dans 30 minutes et ne fonctionne qu’une fois. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message.\nJigobourso";
    if (!send_account_mail($email,$purpose==='reset'?'Réinitialiser votre mot de passe Jigobourso':'Confirmer votre adresse Jigobourso',$message)) {
        q('UPDATE account_tokens SET used_at=? WHERE token_hash=?',[now_utc(),$hash]);
        return false;
    }
    return true;
}
function consume_account_link(string $raw, string $purpose, callable $change): void {
    if (!preg_match('/^[a-f0-9]{64}$/D',$raw)) throw new ApiError('Lien invalide ou expiré. Demandez un nouveau lien.',422);
    $hash=hash('sha256',$raw);$db=db();$db->beginTransaction();
    try {
        $t=q('SELECT * FROM account_tokens WHERE token_hash=? AND purpose=?',[$hash,$purpose])->fetch();
        if (!$t) throw new ApiError('Lien invalide ou expiré. Demandez un nouveau lien.',422);
        // Same lock ordering for password changes and both token purposes.
        $u=q('SELECT * FROM users WHERE id=? FOR UPDATE',[$t['user_id']])->fetch();
        $t=q('SELECT * FROM account_tokens WHERE token_hash=? FOR UPDATE',[$hash])->fetch();
        if (!$u || !$u['active'] || $t['used_at'] || $t['expires_at']<=now_utc() || !hash_equals($t['auth_stamp'],account_stamp($u)))
            throw new ApiError('Lien invalide ou expiré. Demandez un nouveau lien.',422);
        $change($u,$t);
        q('UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',[now_utc(),$u['id']]);
        $db->commit();
    } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); throw $e; }
}
function update_account(array $u,array $b): array {
    if (!password_verify(password_input($b,'current'),$u['pass_hash'])) throw new ApiError('Mot de passe actuel incorrect',403);
    $name=str_in($b,'username',30);if (!preg_match('/^[A-Za-z0-9_.-]{3,30}$/D',$name)) throw new ApiError('Pseudo : 3 à 30 caractères, lettres, chiffres, point, tiret ou soulignement.',422);
    $email=mb_strtolower(str_in($b,'email',190));if (!filter_var($email,FILTER_VALIDATE_EMAIL)) throw new ApiError('Adresse e-mail invalide',422);
    if (q('SELECT id FROM users WHERE id<>? AND (username=? OR email=?)',[$u['id'],$name,$email])->fetch()) throw new ApiError('Ces coordonnées ne sont pas disponibles.',409);
    $changing=mb_strtolower($u['email'] ?? '')!==$email;
    if ($changing) {
        account_throttle('email',$email);
        if (!issue_account_link($u,'email',$email)) throw new ApiError('Envoi impossible pour le moment. Votre adresse actuelle est conservée.',503);
    }
    q('UPDATE users SET username=? WHERE id=?',[$name,$u['id']]);
    return ['ok'=>true,'email_pending'=>$changing,'message'=>$changing?'Pseudo enregistré. Confirmez la nouvelle adresse depuis le lien envoyé ; votre adresse actuelle reste active.':'Compte mis à jour.'];
}
