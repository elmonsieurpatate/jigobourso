<?php
if(PHP_SAPI!=='cli')exit(1);
require getcwd().'/app/lib/db.php';
$keys=[];$path=getcwd().'/private/env';
if(is_readable($path))foreach(file($path,FILE_IGNORE_NEW_LINES) as $line)if(preg_match('/^(JIGO_[A-Z_]*(?:MAIL|SMTP)[A-Z_]*)=/',trim($line),$m))$keys[]=$m[1];
$u=q('SELECT COUNT(*) n,SUM(email IS NOT NULL AND email<>\'\') with_email FROM users')->fetch();
echo json_encode(['mail_function'=>function_exists('mail'),'sendmail_path'=>ini_get('sendmail_path'),'mail_variable_names'=>$keys,'users'=>$u,'configured_sender'=>getenv('JIGO_MAIL_FROM')!==false],JSON_PRETTY_PRINT)."\n";
if(getenv('JIGO_SEND_MAIL_PROBE')==='1') {
 $marker=getcwd().'/logs/account-mail-probe.json';
 if(is_file($marker)){echo file_get_contents($marker);exit;}
 $recipient=q('SELECT email FROM users WHERE active=1 AND is_admin=1 AND email IS NOT NULL ORDER BY id LIMIT 1')->fetchColumn();
 $from=cfg('JIGO_MAIL_FROM','noreply@jigobourso.turnjoy.dev');
 $ok=false;
 if($recipient && filter_var($recipient,FILTER_VALIDATE_EMAIL)) {
  try {$ok=mail($recipient,'Test technique Jigobourso',"Vérification demandée du service d’envoi de Jigobourso. Aucune modification de votre compte ou de votre mot de passe.\n",['From'=>'Jigobourso <'.$from.'>','Content-Type'=>'text/plain; charset=UTF-8']);}catch(Throwable $e){$ok=false;}
 }
 $result=json_encode(['probe_at'=>gmdate('c'),'accepted_by_hostinger'=>$ok,'recipient_found'=>(bool)$recipient])."\n";
 file_put_contents($marker,$result);chmod($marker,0600);echo $result;
}
