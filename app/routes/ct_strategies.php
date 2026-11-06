<?php
require_once __DIR__ . '/../services/ct_strategies.php';
return [
    'classement-test/strategies' => function () { $u = require_user(); return ct_read((int)$u['id']); },
    'classement-test/strategies/save' => function () { need_post(); $u = require_user(); return ct_write((int)$u['id'], body()); },
];
