-- Lifecycle metadata only. Historical configurations and active flags are preserved.
CREATE TABLE IF NOT EXISTS explorer_states (
 user_id INT UNSIGNED NOT NULL,
 item_key VARCHAR(120) NOT NULL,
 active TINYINT(1) NOT NULL DEFAULT 0,
 archived TINYINT(1) NOT NULL DEFAULT 0,
 updated_at DATETIME NOT NULL,
 PRIMARY KEY(user_id,item_key),
 CONSTRAINT fk_explorer_state_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
