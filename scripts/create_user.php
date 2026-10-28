<?php
// Crée un compte en ligne de commande :  php scripts/create_user.php <identifiant> <mot de passe> [--admin] [--email=adresse]
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/../app/lib/auth.php';
$args = array_slice($argv, 1);
$admin = in_array('--admin', $args, true);
$email = null;
foreach ($args as $a) if (strpos($a, '--email=') === 0) $email = substr($a, 8);
$pos = array_values(array_filter($args, function ($a) { return strpos($a, '--') !== 0; }));
if (count($pos) < 2) { fwrite(STDERR, "usage: create_user.php identifiant motdepasse [--admin] [--email=…]\n"); exit(1); }
try { echo 'compte créé, id ' . create_user($pos[0], $pos[1], $email, $admin) . "\n"; } catch (ApiError $e) { fwrite(STDERR, $e->getMessage() . "\n"); exit(1); }
