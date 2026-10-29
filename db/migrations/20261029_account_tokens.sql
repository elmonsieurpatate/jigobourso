CREATE TABLE IF NOT EXISTS account_tokens (
 token_hash CHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,
 user_id INT UNSIGNED NOT NULL,
 purpose ENUM('reset','email') NOT NULL,
 target_email VARCHAR(190) NULL,
 auth_stamp CHAR(64) CHARACTER SET ascii NOT NULL,
 created_at DATETIME NOT NULL,
 expires_at DATETIME NOT NULL,
 used_at DATETIME NULL,
 KEY ix_account_token_user (user_id,purpose),
 CONSTRAINT fk_account_token_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS account_attempts (
 scope_hash CHAR(64) CHARACTER SET ascii NOT NULL,
 at DATETIME NOT NULL,
 KEY ix_account_attempt (scope_hash,at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS session_policies (
 token_hash CHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,
 persistent TINYINT(1) NOT NULL,
 absolute_expiry DATETIME NOT NULL,
 CONSTRAINT fk_session_policy FOREIGN KEY (token_hash) REFERENCES sessions(token_hash) ON DELETE CASCADE
) ENGINE=InnoDB;
