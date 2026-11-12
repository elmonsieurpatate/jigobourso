<?php
require_once __DIR__ . '/../lib/http.php';
require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../services/table_layouts.php';
return [
    // colonnes, tris et filtres initiaux : PERSONNELS (un document par utilisateur, défaut commun hérité)
    'table-layouts' => function () { $u = require_user(); return tl_read((int)$u['id']); },
    'table-layouts/save' => function () { need_post(); $u = require_user(); return tl_write(body(), (int)$u['id']); },
    // défaut commun (administration technique) : n'écrase jamais les réglages personnels
    'admin/table-layouts' => function () { require_admin(); return tl_read(); },
    'admin/table-layouts/save' => function () { need_post(); require_admin(); return tl_write(body()); },
];
