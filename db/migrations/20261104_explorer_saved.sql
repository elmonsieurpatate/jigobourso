-- Separate financial strategies, universes and complete searches. Existing saves are unchanged.
CREATE TABLE IF NOT EXISTS explorer_saved (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
 user_id INT UNSIGNED NOT NULL,
 kind ENUM('strategy','universe','search') NOT NULL,
 name VARCHAR(80) NOT NULL,
 payload JSON NOT NULL,
 active TINYINT(1) NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL,
 updated_at DATETIME NOT NULL,
 PRIMARY KEY(id),
 UNIQUE KEY uq_explorer_saved(user_id,kind,name),
 CONSTRAINT fk_explorer_saved_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
