<?php
require_once __DIR__ . '/../services/secondary_filters.php';
return [
    'admin/secondary-filters' => function () { require_admin();return secondary_read(); },
    'admin/secondary-filters/save' => function () { need_post();require_admin();return secondary_write(body()); },
    'explorer/secondary-filters' => function () {
        require_user();$state=secondary_read();unset($state['proposed']);return $state;
    },
];
