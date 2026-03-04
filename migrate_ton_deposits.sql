-- ================================================================
-- MIGRACIÓN TON DEPOSITS — SALLY-E
-- Ejecuta esto en la consola MySQL de Railway
-- ================================================================

-- 1. Agregar columna memo en users
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS ton_deposit_memo VARCHAR(50) DEFAULT NULL;

-- 2. Crear tabla ton_deposits
CREATE TABLE IF NOT EXISTS ton_deposits (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    deposit_id      VARCHAR(100)  NOT NULL UNIQUE,
    user_id         VARCHAR(50)   NOT NULL,
    ton_amount      DECIMAL(20,9) NOT NULL DEFAULT 0,
    ton_wallet_from VARCHAR(100)  NOT NULL DEFAULT '',
    ton_tx_hash     VARCHAR(200)  DEFAULT NULL,
    memo            VARCHAR(50)   DEFAULT NULL,
    status          ENUM('pending','credited','failed') DEFAULT 'pending',
    admin_note      TEXT          DEFAULT NULL,
    created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    credited_at     DATETIME      DEFAULT NULL,
    INDEX idx_user_id  (user_id),
    INDEX idx_status   (status),
    INDEX idx_tx_hash  (ton_tx_hash),
    INDEX idx_memo     (memo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Insertar config en tabla config (solo si no existen)
INSERT IGNORE INTO config (config_key, config_value) VALUES
    ('ton_wallet_address',   ''),   -- << PON TU WALLET TON AQUÍ
    ('ton_min_deposit',      '0.1'),
    ('ton_deposits_enabled', '1'),
    ('toncenter_api_key',    '');   -- << PON TU API KEY DE TONCENTER AQUÍ

-- 4. Verificar
-- SHOW TABLES;
-- DESCRIBE ton_deposits;
-- SELECT config_key, config_value FROM config WHERE config_key LIKE 'ton%';
