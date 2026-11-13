<?php
// Read-only release check: never initializes settings or changes catalogue rows.
require_once __DIR__.'/../../app/services/secondary_filters.php';
$report=secondary_catalogue_report();
$instruments=(int)q('SELECT COUNT(*) FROM instruments')->fetchColumn();
$listings=(int)q('SELECT COUNT(*) FROM listings')->fetchColumn();
$unmapped=['country'=>0,'sector'=>0,'market'=>0];
foreach($report['assignments'] as $filter=>$rows){
    $expected=$filter==='market'?$listings:$instruments;$covered=0;
    $allowed=array_column($report['values'][$filter],'id');
    foreach($rows as $row){
        if(!in_array($row['id'],$allowed,true))throw new RuntimeException('Métadonnée sans groupe explicite : '.$filter);
        $covered+=(int)$row['count'];
        if(isset($unmapped[$filter])&&!in_array($row['reason'],['mapped','missing'],true))$unmapped[$filter]+=(int)$row['count'];
    }
    if($covered!==$expected)throw new RuntimeException('Couverture de métadonnées incomplète : '.$filter);
}
echo "site OK : catalogue : $instruments instruments, $listings cotations ; affectations exhaustives\n";
echo "site OK : correspondances de repli : pays {$unmapped['country']}, secteurs/ETF {$unmapped['sector']}, MIC {$unmapped['market']}\n";
