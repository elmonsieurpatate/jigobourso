<?php
require_once __DIR__ . '/../services/table_layouts.php';
return [
    'table-layouts' => function () { require_user(); return tl_read(); },
    'admin/table-layouts' => function () { require_admin(); return tl_read(); },
    'admin/table-layouts/save' => function () { need_post(); require_admin(); return tl_write(body()); },
];
