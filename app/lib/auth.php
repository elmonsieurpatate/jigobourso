<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/http.php';

const SESSION_DAYS = 30;
const COOKIE = 'jigo_s';

function client_ip(): string { return substr($_SERVER['REMOTE_ADDR'] ?? '', 0, 45); }
function https(): bool { return (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https'; }

function login_blocked(string $username): bool {
    $n = q('SELECT COUNT(*) FROM login_attempts WHERE username = ? AND at > ?', [$username, gmdate('Y-m-d H:i:s', time() - 900)])->fetchColumn();
    return (int)$n >= 5;
}
function login(string $username, string $password): array {
    $username = mb_substr($username, 0, 30);
    if (login_blocked($username)) throw new ApiError('Trop d’essais : réessayez dans quelques minutes', 429);
    $u = q('SELECT * FROM users WHERE username = ? AND active = 1', [$username])->fetch();
    // Même coût de vérification que l'utilisateur existe ou non.
    $hash = $u ? $u['pass_hash'] : '$2y$10$usesomesillystringforsalt$';
    if (!$u || !password_verify($password, $hash)) {
        q('INSERT INTO login_attempts(username, ip, at) VALUES (?, ?, ?)', [$username, client_ip(), now_utc()]);
        throw new ApiError('Identifiant ou mot de passe incorrect', 401);
    }
    q('DELETE FROM login_attempts WHERE username = ?', [$username]);
    $token = bin2hex(random_bytes(32));
    $now = now_utc();
    q('INSERT INTO sessions(token_hash, user_id, created_at, last_seen, expires_at, ip, ua) VALUES (?,?,?,?,?,?,?)',
      [hash('sha256', $token), $u['id'], $now, $now, gmdate('Y-m-d H:i:s', time() + SESSION_DAYS * 86400), client_ip(), substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 190)]);
    q('UPDATE users SET last_login = ? WHERE id = ?', [$now, $u['id']]);
    setcookie(COOKIE, $token, ['expires' => time() + SESSION_DAYS * 86400, 'path' => '/', 'secure' => https(), 'httponly' => true, 'samesite' => 'Lax']);
    return public_user($u);
}
function logout(): void {
    if (!empty($_COOKIE[COOKIE])) q('DELETE FROM sessions WHERE token_hash = ?', [hash('sha256', $_COOKIE[COOKIE])]);
    setcookie(COOKIE, '', ['expires' => 1, 'path' => '/', 'secure' => https(), 'httponly' => true, 'samesite' => 'Lax']);
}
function public_user(array $u): array {
    return ['id' => (int)$u['id'], 'username' => $u['username'], 'email' => $u['email'], 'is_admin' => (bool)$u['is_admin'], 'prefs' => $u['prefs_json'] ? json_decode($u['prefs_json'], true) : new stdClass()];
}
function current_user(): ?array {
    static $cache = false;
    if ($cache !== false) return $cache;
    $cache = null;
    if (empty($_COOKIE[COOKIE]) || !is_string($_COOKIE[COOKIE])) return null;
    $row = q('SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1',
             [hash('sha256', $_COOKIE[COOKIE]), now_utc()])->fetch();
    if (!$row) return null;
    q('UPDATE sessions SET last_seen = ?, expires_at = ? WHERE token_hash = ?', [now_utc(), gmdate('Y-m-d H:i:s', time() + SESSION_DAYS * 86400), hash('sha256', $_COOKIE[COOKIE])]);
    return $cache = $row;
}
function require_user(): array {
    $u = current_user();
    if (!$u) throw new ApiError('Connexion requise', 401);
    return $u;
}
function require_admin(): array {
    $u = require_user();
    if (!$u['is_admin']) throw new ApiError('Réservé à l’administrateur', 403);
    return $u;
}
function valid_password(string $p): void {
    if (mb_strlen($p) < 10) throw new ApiError('Mot de passe : 10 caractères minimum');
    if (mb_strlen($p) > 200) throw new ApiError('Mot de passe trop long');
}
function create_user(string $username, string $password, ?string $email, bool $admin): int {
    if (!preg_match('/^[A-Za-z0-9_.-]{3,30}$/', $username)) throw new ApiError('Identifiant : 3 à 30 caractères (lettres, chiffres, _ . -)');
    valid_password($password);
    if ($email !== null && $email !== '' && !filter_var($email, FILTER_VALIDATE_EMAIL)) throw new ApiError('Adresse e-mail invalide');
    if (q('SELECT 1 FROM users WHERE username = ?', [$username])->fetch()) throw new ApiError('Identifiant déjà pris', 409);
    q('INSERT INTO users(username, email, pass_hash, is_admin, active, created_at) VALUES (?,?,?,?,1,?)',
      [$username, $email ?: null, password_hash($password, PASSWORD_DEFAULT), $admin ? 1 : 0, now_utc()]);
    return (int)db()->lastInsertId();
}
