<?php
require __DIR__.'/../../app/services/secondary_metadata.php';
$cases=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$out=[];foreach($cases as $c)$out[]=secondary_metadata_classify($c[0],$c[1],$c[2]??null);
echo json_encode($out,JSON_THROW_ON_ERROR);
