<?php
if(PHP_SAPI!=='cli')exit(1);
require getcwd().'/app/lib/db.php';
$keys=[];$path=getcwd().'/private/env';
if(is_readable($path))foreach(file($path,FILE_IGNORE_NEW_LINES) as $line)if(preg_match('/^(JIGO_[A-Z_]*(?:MAIL|SMTP)[A-Z_]*)=/',trim($line),$m))$keys[]=$m[1];
$u=q('SELECT COUNT(*) n,SUM(email IS NOT NULL AND email<>\'\') with_email FROM users')->fetch();
echo json_encode(['mail_function'=>function_exists('mail'),'sendmail_path'=>ini_get('sendmail_path'),'mail_variable_names'=>$keys,'users'=>$u,'configured_sender'=>getenv('JIGO_MAIL_FROM')!==false],JSON_PRETTY_PRINT)."\n";
