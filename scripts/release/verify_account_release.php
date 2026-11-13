<?php
if(PHP_SAPI!=='cli')exit(1);
require getcwd().'/app/lib/db.php';
$users=q('SELECT id,username,email,pass_hash,is_admin,active,created_at FROM users ORDER BY id')->fetchAll();
$result=['users'=>count($users),'users_fingerprint'=>hash('sha256',json_encode($users)),'sessions'=>(int)q('SELECT COUNT(*) FROM sessions')->fetchColumn()];
if(getenv('JIGO_ACCOUNT_POSTCHECK')==='1') {
 foreach(['account_tokens','account_attempts','session_policies'] as $t)$result[$t]=(int)q('SELECT COUNT(*) FROM '.$t)->fetchColumn();
 $matched=0;foreach($users as $u)if($u['email'] && q('SELECT id FROM users WHERE email=?',[$u['email']])->fetchColumn()==$u['id'])$matched++;
 $result['email_aliases_resolvable']=$matched;
 require getcwd().'/app/lib/mail.php';
 $marker=getcwd().'/logs/account-mailer-confirmed.json';
 if(!is_file($marker) || empty(json_decode(file_get_contents($marker),true)['accepted_by_hostinger'])) {
  $recipient=q('SELECT email FROM users WHERE active=1 AND is_admin=1 AND email IS NOT NULL ORDER BY id LIMIT 1')->fetchColumn();
  $accepted=$recipient?send_account_mail($recipient,'Jigobourso : service de récupération disponible',"La mise à jour de connexion de Jigobourso est déployée. Ce message vérifie l’envoi réel depuis le module de récupération. Votre mot de passe et vos portefeuilles n’ont pas été modifiés.\n"):false;
  file_put_contents($marker,json_encode(['at_utc'=>gmdate('c'),'accepted_by_hostinger'=>$accepted]));chmod($marker,0600);
 }
 $result['mail_transport']=json_decode(file_get_contents($marker),true);
 if(!$result['mail_transport']['accepted_by_hostinger']){echo json_encode($result)."\n";exit(3);}
}
echo json_encode($result)."\n";
