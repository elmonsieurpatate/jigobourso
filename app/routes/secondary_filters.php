<?php
require_once __DIR__ . '/../services/personal_secondary_filters.php';
return [
    'explorer/secondary-filters/manage' => function () { $u=require_user();return secondary_user_read((int)$u['id']); },
    'explorer/secondary-filters/save' => function () { need_post();$u=require_user();return secondary_user_write((int)$u['id'],body()); },
    'admin/secondary-filters' => function () { require_admin();return secondary_read(); },
    'admin/secondary-filters/save' => function () { need_post();require_admin();return secondary_write(body()); },
    'explorer/secondary-filters' => function () {
        $u=require_user();$state=secondary_user_read((int)$u['id']);unset($state['proposed']);return $state;
    },
];
