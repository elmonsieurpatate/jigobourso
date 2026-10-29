<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/http.php';
function mail_available(): bool {
    return function_exists('mail') && (string)ini_get('sendmail_path') !== '';
}
function send_account_mail(string $email, string $subject, string $message): bool {
    // A file transport is available ONLY for the explicitly disposable integration DB.
    $test = cfg('JIGO_TEST_DATABASE') === '1' && cfg('JIGO_DB_NAME') === 'jigobourso_it';
    if ($test && cfg('JIGO_TEST_MAIL_DIR')) {
        $file = rtrim(cfg('JIGO_TEST_MAIL_DIR'), '/') . '/' . bin2hex(random_bytes(12)) . '.json';
        return file_put_contents($file, json_encode(['to'=>$email,'subject'=>$subject,'body'=>$message])) !== false;
    }
    if (!mail_available()) return false;
    $from = cfg('JIGO_MAIL_FROM', 'noreply@jigobourso.turnjoy.dev');
    if (!filter_var($from,FILTER_VALIDATE_EMAIL) || !filter_var($email,FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/',$subject.$from.$email)) return false;
    $headers = ['From'=>'Jigobourso <'.$from.'>', 'MIME-Version'=>'1.0', 'Content-Type'=>'text/plain; charset=UTF-8'];
    try { return mail($email, '=?UTF-8?B?'.base64_encode($subject).'?=', $message, $headers); }
    catch (Throwable $e) { error_log('account_mail: transport failure'); return false; }
}
