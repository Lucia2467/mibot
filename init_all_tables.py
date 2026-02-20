"""
init_all_tables.py
==================
Crea TODAS las tablas de la app automáticamente al iniciar.
Incluye todas las tablas encontradas en el código fuente.

USO:
  python init_all_tables.py          → ejecutar manualmente
  from init_all_tables import init_all_tables  → llamar desde web.py o main.py
"""

import logging
from db import execute_query, get_cursor, test_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# TODAS LAS TABLAS
# ─────────────────────────────────────────────
ALL_TABLES = [

    # ── USUARIOS ──────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        username VARCHAR(100) DEFAULT NULL,
        first_name VARCHAR(100) DEFAULT 'Usuario',
        last_name VARCHAR(100) DEFAULT NULL,
        language_code VARCHAR(10) DEFAULT NULL,
        photo_url TEXT DEFAULT NULL,
        se_balance DECIMAL(20,8) DEFAULT 0.00000000,
        usdt_balance DECIMAL(20,8) DEFAULT 0.00000000,
        doge_balance DECIMAL(20,8) DEFAULT 0.00000000,
        ton_balance DECIMAL(20,9) DEFAULT 0.000000000,
        mining_power DECIMAL(10,4) DEFAULT 1.0000,
        mining_level INT DEFAULT 1,
        total_mined DECIMAL(20,8) DEFAULT 0.00000000,
        last_claim DATETIME DEFAULT NULL,
        referral_count INT DEFAULT 0,
        referred_by VARCHAR(50) DEFAULT NULL,
        pending_referrer VARCHAR(50) DEFAULT NULL,
        referral_validated TINYINT(1) DEFAULT 0,
        wallet_address VARCHAR(200) DEFAULT NULL,
        wallet_linked_at DATETIME DEFAULT NULL,
        banned TINYINT(1) DEFAULT 0,
        ban_reason VARCHAR(255) DEFAULT NULL,
        last_ip VARCHAR(50) DEFAULT NULL,
        is_admin TINYINT(1) DEFAULT 0,
        completed_tasks JSON DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        last_interaction DATETIME DEFAULT NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_username (username),
        INDEX idx_banned (banned)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── REFERIDOS ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS referrals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        referrer_id VARCHAR(50) NOT NULL,
        referred_id VARCHAR(50) NOT NULL,
        referred_username VARCHAR(100) DEFAULT NULL,
        referred_first_name VARCHAR(100) DEFAULT 'Usuario',
        validated TINYINT(1) DEFAULT 0,
        bonus_paid DECIMAL(10,4) DEFAULT 0.0000,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        validated_at DATETIME DEFAULT NULL,
        UNIQUE KEY unique_referral (referrer_id, referred_id),
        INDEX idx_referrer_id (referrer_id),
        INDEX idx_referred_id (referred_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── TAREAS ────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id VARCHAR(50) NOT NULL UNIQUE,
        title VARCHAR(200) NOT NULL,
        description TEXT DEFAULT NULL,
        reward DECIMAL(10,4) DEFAULT 0.0000,
        url VARCHAR(500) DEFAULT NULL,
        task_type VARCHAR(50) DEFAULT 'link',
        active TINYINT(1) DEFAULT 1,
        requires_channel_join TINYINT(1) DEFAULT 0,
        channel_username VARCHAR(100) DEFAULT NULL,
        max_completions INT DEFAULT NULL,
        current_completions INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_task_id (task_id),
        INDEX idx_active (active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── RETIROS ───────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        withdrawal_id VARCHAR(100) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        currency VARCHAR(10) NOT NULL DEFAULT 'USDT',
        amount DECIMAL(20,8) NOT NULL,
        fee DECIMAL(20,8) DEFAULT 0.00000000,
        wallet_address VARCHAR(200) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        tx_hash VARCHAR(200) DEFAULT NULL,
        error_message TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        processed_at DATETIME DEFAULT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── CÓDIGOS PROMO ─────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        reward DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
        currency VARCHAR(10) DEFAULT 'SE',
        max_uses INT DEFAULT 100,
        current_uses INT DEFAULT 0,
        active TINYINT(1) DEFAULT 1,
        expires_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_code (code),
        INDEX idx_active (active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── CANJES PROMO ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS promo_redemptions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        code VARCHAR(50) NOT NULL,
        reward DECIMAL(10,4) NOT NULL,
        currency VARCHAR(10) DEFAULT 'SE',
        redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_redemption (user_id, code),
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── CONFIGURACIÓN ─────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        config_key VARCHAR(100) NOT NULL UNIQUE,
        config_value TEXT DEFAULT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_config_key (config_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── ESTADÍSTICAS ─────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        stat_key VARCHAR(100) NOT NULL UNIQUE,
        stat_value BIGINT DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_stat_key (stat_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── IPs DE USUARIOS ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS user_ips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        ip_address VARCHAR(50) NOT NULL,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        times_seen INT DEFAULT 1,
        UNIQUE KEY unique_user_ip (user_id, ip_address),
        INDEX idx_ip_address (ip_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── BANS DE IP ────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ip_bans (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ip_address VARCHAR(50) NOT NULL UNIQUE,
        reason VARCHAR(255) DEFAULT NULL,
        banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_ip_address (ip_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── HISTORIAL DE BALANCE ──────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS balance_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        action VARCHAR(100) NOT NULL,
        currency VARCHAR(10) DEFAULT 'SE',
        amount DECIMAL(20,8) NOT NULL,
        balance_before DECIMAL(20,8) DEFAULT 0.00000000,
        balance_after DECIMAL(20,8) DEFAULT 0.00000000,
        description TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── SESIONES ADMIN ────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS admin_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        admin_id VARCHAR(50) NOT NULL,
        session_token VARCHAR(255) NOT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        INDEX idx_session_token (session_token)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── HISTORIAL DE GAME (juego de minas) ────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS game_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(64) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        game_type VARCHAR(50) DEFAULT 'mines',
        bet_amount DECIMAL(20,8) NOT NULL,
        mine_count INT DEFAULT 3,
        mine_positions JSON DEFAULT NULL,
        revealed_cells JSON DEFAULT NULL,
        gems_found INT DEFAULT 0,
        current_multiplier DECIMAL(10,4) DEFAULT 1.0000,
        status VARCHAR(20) DEFAULT 'active',
        winnings DECIMAL(20,8) DEFAULT 0.00000000,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        ended_at DATETIME DEFAULT NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS game_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        game_type VARCHAR(50) DEFAULT 'mines',
        bet_amount DECIMAL(20,8) NOT NULL,
        mine_count INT DEFAULT NULL,
        gems_found INT DEFAULT 0,
        multiplier DECIMAL(10,4) DEFAULT 1.0000,
        result VARCHAR(20) NOT NULL,
        winnings DECIMAL(20,8) DEFAULT 0.00000000,
        profit DECIMAL(20,8) DEFAULT 0.00000000,
        played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_played_at (played_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── DEPÓSITOS ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS user_deposit_addresses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        deposit_address VARCHAR(100) NOT NULL,
        deposit_memo VARCHAR(100) DEFAULT NULL,
        derivation_index INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_deposit_address (deposit_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS deposits (
        id INT AUTO_INCREMENT PRIMARY KEY,
        deposit_id VARCHAR(100) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        currency VARCHAR(10) NOT NULL DEFAULT 'DOGE',
        network VARCHAR(20) NOT NULL DEFAULT 'BEP20',
        amount DECIMAL(20,8) NOT NULL,
        deposit_address VARCHAR(100) NOT NULL,
        tx_hash VARCHAR(200) NOT NULL UNIQUE,
        confirmations INT DEFAULT 0,
        status VARCHAR(20) DEFAULT 'pending',
        credited TINYINT(1) DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        confirmed_at DATETIME DEFAULT NULL,
        credited_at DATETIME DEFAULT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_status (status),
        INDEX idx_tx_hash (tx_hash),
        INDEX idx_deposit_address (deposit_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS deposit_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        config_key VARCHAR(100) NOT NULL UNIQUE,
        config_value TEXT DEFAULT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_config_key (config_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── DEPÓSITOS MANUALES ────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS manual_deposits (
        id INT AUTO_INCREMENT PRIMARY KEY,
        deposit_id VARCHAR(100) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        amount DECIMAL(20,8) NOT NULL,
        currency VARCHAR(20) NOT NULL DEFAULT 'DOGE',
        method VARCHAR(50) NOT NULL DEFAULT 'wallet',
        proof_image VARCHAR(500) NOT NULL,
        tx_hash VARCHAR(200) DEFAULT NULL,
        status VARCHAR(50) DEFAULT 'pending',
        admin_notes TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        processed_at DATETIME DEFAULT NULL,
        processed_by VARCHAR(50) DEFAULT NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_status (status),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── DEPÓSITOS TON ─────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ton_deposits (
        id INT AUTO_INCREMENT PRIMARY KEY,
        deposit_id VARCHAR(100) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        wallet_origin VARCHAR(100) NOT NULL,
        wallet_destination VARCHAR(100) NOT NULL,
        tx_hash VARCHAR(100) UNIQUE,
        lt BIGINT DEFAULT NULL,
        amount DECIMAL(20,9) NOT NULL,
        status ENUM('pending','confirming','confirmed','failed','expired') DEFAULT 'pending',
        error_message TEXT DEFAULT NULL,
        credited_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_tx_hash (tx_hash),
        INDEX idx_status (status),
        INDEX idx_wallet_origin (wallet_origin)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── PAGOS TON ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ton_payments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        payment_id VARCHAR(100) NOT NULL UNIQUE,
        withdrawal_id VARCHAR(100) DEFAULT NULL,
        user_id VARCHAR(50) NOT NULL,
        amount DECIMAL(20,9) NOT NULL,
        fee DECIMAL(20,9) DEFAULT 0.000000000,
        net_amount DECIMAL(20,9) NOT NULL,
        from_address VARCHAR(100) DEFAULT NULL,
        to_address VARCHAR(100) NOT NULL,
        tx_hash VARCHAR(200) DEFAULT NULL,
        status VARCHAR(30) DEFAULT 'pending',
        payment_type VARCHAR(50) DEFAULT 'withdrawal',
        memo VARCHAR(255) DEFAULT NULL,
        error_message TEXT DEFAULT NULL,
        created_by VARCHAR(50) DEFAULT 'system',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        sent_at DATETIME DEFAULT NULL,
        confirmed_at DATETIME DEFAULT NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_status (status),
        INDEX idx_payment_id (payment_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS ton_payment_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        config_key VARCHAR(100) NOT NULL UNIQUE,
        config_value TEXT DEFAULT NULL,
        config_type VARCHAR(30) DEFAULT 'string',
        updated_by VARCHAR(50) DEFAULT 'system',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_config_key (config_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS ton_payment_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        payment_id VARCHAR(100) NOT NULL,
        action VARCHAR(100) NOT NULL,
        old_status VARCHAR(30) DEFAULT NULL,
        new_status VARCHAR(30) DEFAULT NULL,
        actor_type VARCHAR(30) DEFAULT 'system',
        actor_id VARCHAR(50) DEFAULT NULL,
        details TEXT DEFAULT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_payment_id (payment_id),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS ton_wallet_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        wallet_address VARCHAR(100) NOT NULL UNIQUE,
        total_sent DECIMAL(20,9) DEFAULT 0.000000000,
        total_received DECIMAL(20,9) DEFAULT 0.000000000,
        tx_count INT DEFAULT 0,
        last_tx_at DATETIME DEFAULT NULL,
        last_checked_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_wallet_address (wallet_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── MÁQUINAS MINERAS ──────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS mining_machines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        machine_type VARCHAR(50) DEFAULT 'doge_miner_pro',
        price_paid DECIMAL(20,8) NOT NULL,
        total_earnings DECIMAL(20,8) NOT NULL,
        duration_days INT NOT NULL DEFAULT 30,
        daily_rate DECIMAL(20,8) NOT NULL,
        earned_so_far DECIMAL(20,8) DEFAULT 0.00000000,
        last_claim_at DATETIME DEFAULT NULL,
        started_at DATETIME NOT NULL,
        ends_at DATETIME NOT NULL,
        is_active TINYINT(1) DEFAULT 1,
        is_completed TINYINT(1) DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_is_active (is_active),
        INDEX idx_ends_at (ends_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── BOOSTS DE MINERÍA ─────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS mining_boosts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        multiplier FLOAT DEFAULT 2.0,
        activated_at DATETIME NOT NULL,
        expires_at DATETIME NOT NULL,
        source VARCHAR(50) DEFAULT 'adsgram',
        INDEX idx_user_expires (user_id, expires_at),
        INDEX idx_expires (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── ADSGRAM BOOST HISTORIAL ───────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS adsgram_boost_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        activated_at DATETIME NOT NULL,
        boost_date DATE NOT NULL,
        INDEX idx_user_date (user_id, boost_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── SISTEMA PTS (Onclicka) ────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS user_pts (
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci PRIMARY KEY,
        pts_balance INT DEFAULT 0,
        pts_total_earned INT DEFAULT 0,
        pts_today INT DEFAULT 0,
        last_pts_date DATE DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS pts_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        amount INT NOT NULL,
        action VARCHAR(50) NOT NULL,
        description VARCHAR(200),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_date (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS pts_ranking (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        period_type VARCHAR(20) NOT NULL,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        pts_earned INT DEFAULT 0,
        final_rank INT DEFAULT NULL,
        reward_doge DECIMAL(10,4) DEFAULT NULL,
        UNIQUE KEY unique_user_period (user_id, period_type, period_start),
        INDEX idx_period (period_type, period_start)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── BOOSTS ONCLICKA ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS onclicka_boosts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        multiplier FLOAT DEFAULT 2.0,
        activated_at DATETIME NOT NULL,
        expires_at DATETIME NOT NULL,
        INDEX idx_user_expires (user_id, expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS onclicka_boost_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        boost_date DATE NOT NULL,
        activated_at DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── CHECK-IN DIARIO ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS daily_checkin (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        checkin_date DATE NOT NULL,
        base_reward INT NOT NULL,
        doubled TINYINT(1) DEFAULT 0,
        total_reward INT NOT NULL,
        streak INT DEFAULT 1,
        UNIQUE KEY unique_user_date (user_id, checkin_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── COMPETENCIAS PTS ──────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS pts_competitions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        competition_number INT NOT NULL,
        state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
        period_start DATETIME NOT NULL,
        period_end DATETIME NOT NULL,
        ended_at DATETIME DEFAULT NULL,
        distribution_started_at DATETIME DEFAULT NULL,
        distribution_completed_at DATETIME DEFAULT NULL,
        preparation_started_at DATETIME DEFAULT NULL,
        completed_at DATETIME DEFAULT NULL,
        rewards_distributed TINYINT(1) DEFAULT 0,
        pts_reset_done TINYINT(1) DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_state (state),
        INDEX idx_period (period_start, period_end),
        UNIQUE KEY unique_competition_number (competition_number)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS pts_competition_results (
        id INT AUTO_INCREMENT PRIMARY KEY,
        competition_id INT NOT NULL,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        final_position INT NOT NULL,
        pts_earned INT NOT NULL,
        reward_doge DECIMAL(10,4) DEFAULT 0,
        qualified TINYINT(1) DEFAULT 0,
        reward_credited TINYINT(1) DEFAULT 0,
        credited_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_competition (competition_id),
        INDEX idx_user (user_id),
        UNIQUE KEY unique_competition_user (competition_id, user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS pts_competition_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        competition_id INT NOT NULL,
        previous_state VARCHAR(20),
        new_state VARCHAR(20) NOT NULL,
        action VARCHAR(100),
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_competition_log (competition_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS pts_reset_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        competition_id INT NOT NULL,
        users_affected INT NOT NULL DEFAULT 0,
        total_pts_reset BIGINT NOT NULL DEFAULT 0,
        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_competition_reset (competition_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── TAREAS DE ANUNCIOS ────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ad_task_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        task_id VARCHAR(50) NOT NULL,
        ads_watched INT DEFAULT 0,
        total_earned DECIMAL(10,4) DEFAULT 0.0000,
        completed TINYINT(1) DEFAULT 0,
        last_ad_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_task (user_id, task_id),
        INDEX idx_user_id (user_id),
        INDEX idx_task_id (task_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS ad_tasks_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
        task_type VARCHAR(50) NOT NULL,
        ads_watched INT DEFAULT 0,
        ads_target INT DEFAULT 5,
        completed TINYINT(1) DEFAULT 0,
        task_date DATE NOT NULL,
        last_ad_at DATETIME DEFAULT NULL,
        UNIQUE KEY unique_user_task_date (user_id, task_type, task_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS user_ad_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        ads_watched_today INT DEFAULT 0,
        total_ads_watched INT DEFAULT 0,
        total_earnings DECIMAL(20,8) DEFAULT 0.00000000,
        last_ad_date DATE DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS ad_completions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        task_id VARCHAR(50) DEFAULT NULL,
        ad_type VARCHAR(50) DEFAULT 'task_center',
        reward DECIMAL(10,4) NOT NULL,
        completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_task_id (task_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── TOKENS DE ANUNCIOS ────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ad_tokens (
        id INT AUTO_INCREMENT PRIMARY KEY,
        token VARCHAR(64) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        ad_type VARCHAR(20) DEFAULT 'rewarded',
        ad_block_uuid VARCHAR(100) DEFAULT NULL,
        status ENUM('pending','completed','claimed','expired') DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME DEFAULT NULL,
        claimed_at DATETIME DEFAULT NULL,
        expires_at DATETIME NOT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        user_agent TEXT DEFAULT NULL,
        telega_response TEXT DEFAULT NULL,
        INDEX idx_token (token),
        INDEX idx_user_id (user_id),
        INDEX idx_status (status),
        INDEX idx_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── ESTADÍSTICAS DIARIAS DE ANUNCIOS ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ad_daily_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        stat_date DATE NOT NULL,
        ads_requested INT DEFAULT 0,
        ads_completed INT DEFAULT 0,
        ads_claimed INT DEFAULT 0,
        total_earned DECIMAL(20,8) DEFAULT 0.00000000,
        last_ad_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_date (user_id, stat_date),
        INDEX idx_user_id (user_id),
        INDEX idx_stat_date (stat_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── CALLBACKS DE TELEGA ───────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ad_callbacks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        token VARCHAR(64) DEFAULT NULL,
        user_id VARCHAR(50) DEFAULT NULL,
        callback_data TEXT,
        ip_address VARCHAR(50) DEFAULT NULL,
        valid TINYINT(1) DEFAULT 0,
        error_message VARCHAR(255) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_token (token),
        INDEX idx_user_id (user_id),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── SISTEMA SHRINKEARN ────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS shrinkearn_tasks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        token VARCHAR(64) UNIQUE NOT NULL,
        mission_type VARCHAR(50) NOT NULL DEFAULT 'standard_ad',
        reward DECIMAL(10,6) NOT NULL,
        reward_pts INT DEFAULT 0,
        status ENUM('pending','completed','expired','cancelled') DEFAULT 'pending',
        shortened_url VARCHAR(255),
        ip_address VARCHAR(45),
        user_agent VARCHAR(255),
        started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME DEFAULT NULL,
        INDEX idx_user_status (user_id, status),
        INDEX idx_token (token),
        INDEX idx_started (started_at),
        INDEX idx_user_mission (user_id, mission_type, started_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS shrinkearn_daily_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        stat_date DATE NOT NULL,
        missions_started INT DEFAULT 0,
        missions_completed INT DEFAULT 0,
        total_reward DECIMAL(10,6) DEFAULT 0,
        total_pts INT DEFAULT 0,
        UNIQUE KEY unique_user_date (user_id, stat_date),
        INDEX idx_date (stat_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS shrinkearn_config (
        config_key VARCHAR(50) PRIMARY KEY,
        config_value TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── GIGAPUB ───────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS gigapub_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        ads_watched INT DEFAULT 0,
        total_earned DECIMAL(18,8) DEFAULT 0,
        completed TINYINT(1) DEFAULT 0,
        last_ad_at DATETIME NULL,
        progress_date DATE NULL,
        session_token VARCHAR(255) NULL,
        token_created_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_progress_date (progress_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS gigapub_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        session_token VARCHAR(255) NULL,
        status ENUM('started','completed','cancelled','failed') DEFAULT 'started',
        watch_duration INT DEFAULT 0,
        reward_amount DECIMAL(18,8) DEFAULT 0,
        ip_address VARCHAR(45) NULL,
        user_agent VARCHAR(255) NULL,
        fail_reason VARCHAR(100) NULL,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_session_token (session_token),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── MONETAG ───────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS monetag_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        ads_watched INT DEFAULT 0,
        total_earned DECIMAL(18,8) DEFAULT 0,
        completed TINYINT(1) DEFAULT 0,
        last_ad_at DATETIME NULL,
        progress_date DATE NULL,
        session_token VARCHAR(255) NULL,
        token_created_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_progress_date (progress_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS monetag_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        session_token VARCHAR(255) NULL,
        status ENUM('started','completed','cancelled','failed') DEFAULT 'started',
        watch_duration INT DEFAULT 0,
        reward_amount DECIMAL(18,8) DEFAULT 0,
        ip_address VARCHAR(45) NULL,
        user_agent VARCHAR(255) NULL,
        fail_reason VARCHAR(100) NULL,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_session_token (session_token),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── ADEXIUM ───────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS adexium_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        ads_watched INT DEFAULT 0,
        total_earned DECIMAL(18,8) DEFAULT 0,
        completed TINYINT(1) DEFAULT 0,
        last_ad_at DATETIME NULL,
        progress_date DATE NULL,
        session_token VARCHAR(255) NULL,
        token_created_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_progress_date (progress_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS adexium_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        session_token VARCHAR(255) NULL,
        status ENUM('started','completed','cancelled','failed') DEFAULT 'started',
        watch_duration INT DEFAULT 0,
        reward_amount DECIMAL(18,8) DEFAULT 0,
        ip_address VARCHAR(45) NULL,
        user_agent VARCHAR(255) NULL,
        fail_reason VARCHAR(100) NULL,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_session_token (session_token),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── WATCH ADS ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS watch_ads_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        ads_watched INT DEFAULT 0,
        total_earned DECIMAL(18,8) DEFAULT 0,
        completed TINYINT(1) DEFAULT 0,
        last_ad_at DATETIME NULL,
        progress_date DATE NULL,
        session_token VARCHAR(255) NULL,
        token_created_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── REWARD VIDEO ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS reward_video_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        videos_watched INT DEFAULT 0,
        total_earned DECIMAL(18,8) DEFAULT 0,
        completed TINYINT(1) DEFAULT 0,
        last_video_at DATETIME NULL,
        progress_date DATE NULL,
        session_token VARCHAR(255) NULL,
        token_created_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS reward_video_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        session_token VARCHAR(255) NULL,
        status ENUM('started','completed','cancelled','failed') DEFAULT 'started',
        reward_amount DECIMAL(18,8) DEFAULT 0,
        ip_address VARCHAR(45) NULL,
        user_agent VARCHAR(255) NULL,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_session_token (session_token)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── RULETA PTS ────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS roulette_pts_progress (
        user_id VARCHAR(50) PRIMARY KEY,
        total_spins INT DEFAULT 0,
        total_pts_won INT DEFAULT 0,
        last_spin_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS roulette_pts_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        prize INT NOT NULL,
        doubled TINYINT(1) DEFAULT 0,
        final_prize INT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_date (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── RULETA (juego SE) ─────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS roulette_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(64) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        bet_amount DECIMAL(20,8) NOT NULL,
        result VARCHAR(20) DEFAULT NULL,
        multiplier DECIMAL(10,4) DEFAULT 1.0000,
        winnings DECIMAL(20,8) DEFAULT 0.00000000,
        status VARCHAR(20) DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        ended_at DATETIME DEFAULT NULL,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS roulette_spins (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        bet_amount DECIMAL(20,8) NOT NULL,
        result VARCHAR(20) NOT NULL,
        multiplier DECIMAL(10,4) DEFAULT 1.0000,
        winnings DECIMAL(20,8) DEFAULT 0.00000000,
        profit DECIMAL(20,8) DEFAULT 0.00000000,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── MISIONES DE REFERIDOS ─────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS referral_missions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        mission_id VARCHAR(50) NOT NULL UNIQUE,
        title VARCHAR(200) NOT NULL,
        description TEXT DEFAULT NULL,
        required_referrals INT NOT NULL DEFAULT 3,
        reward_amount DECIMAL(20,8) NOT NULL DEFAULT 0.5,
        reward_currency VARCHAR(10) DEFAULT 'DOGE',
        active TINYINT(1) DEFAULT 1,
        display_order INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_mission_id (mission_id),
        INDEX idx_active (active),
        INDEX idx_display_order (display_order)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS referral_mission_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        mission_id VARCHAR(50) NOT NULL,
        referrals_count INT DEFAULT 0,
        status ENUM('in_progress','completed','claimed') DEFAULT 'in_progress',
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME DEFAULT NULL,
        claimed_at DATETIME DEFAULT NULL,
        reward_paid DECIMAL(20,8) DEFAULT 0.00000000,
        UNIQUE KEY unique_user_mission (user_id, mission_id),
        INDEX idx_user_id (user_id),
        INDEX idx_mission_id (mission_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS referral_mission_referrals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        referrer_id VARCHAR(50) NOT NULL,
        referred_id VARCHAR(50) NOT NULL,
        mission_id VARCHAR(50) NOT NULL,
        referred_username VARCHAR(100) DEFAULT NULL,
        is_valid TINYINT(1) DEFAULT 1,
        validation_status VARCHAR(50) DEFAULT 'pending',
        validation_reason TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        validated_at DATETIME DEFAULT NULL,
        UNIQUE KEY unique_mission_referral (referrer_id, referred_id, mission_id),
        INDEX idx_referrer_id (referrer_id),
        INDEX idx_referred_id (referred_id),
        INDEX idx_mission_id (mission_id),
        INDEX idx_is_valid (is_valid)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS referral_mission_audit (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) DEFAULT NULL,
        action VARCHAR(100) NOT NULL,
        mission_id VARCHAR(50) DEFAULT NULL,
        referred_id VARCHAR(50) DEFAULT NULL,
        details TEXT DEFAULT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_action (action),
        INDEX idx_mission_id (mission_id),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── TAREAS DE USUARIOS (Promote) ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS user_tasks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id VARCHAR(50) UNIQUE NOT NULL,
        creator_id VARCHAR(50) NOT NULL,
        task_type ENUM('telegram_channel','telegram_group','website','social','other') DEFAULT 'telegram_channel',
        title VARCHAR(255) NOT NULL,
        description TEXT,
        url VARCHAR(500) NOT NULL,
        channel_username VARCHAR(100) DEFAULT NULL,
        requires_join TINYINT(1) DEFAULT 0,
        package_id VARCHAR(50) NOT NULL,
        price_paid DECIMAL(20,8) NOT NULL,
        max_completions INT NOT NULL,
        current_completions INT DEFAULT 0,
        reward_per_completion DECIMAL(10,4) DEFAULT 0.5,
        status ENUM('pending','active','paused','completed','rejected','expired') DEFAULT 'active',
        rejection_reason TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        approved_at DATETIME DEFAULT NULL,
        completed_at DATETIME DEFAULT NULL,
        expires_at DATETIME DEFAULT NULL,
        INDEX idx_creator (creator_id),
        INDEX idx_status (status),
        INDEX idx_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS user_task_completions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id VARCHAR(50) NOT NULL,
        user_id VARCHAR(50) NOT NULL,
        completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        reward_earned DECIMAL(10,4) DEFAULT 0,
        verified TINYINT(1) DEFAULT 0,
        must_stay_until DATETIME DEFAULT NULL,
        left_channel TINYINT(1) DEFAULT 0,
        left_at DATETIME DEFAULT NULL,
        penalty_applied TINYINT(1) DEFAULT 0,
        penalty_amount DECIMAL(10,4) DEFAULT 0,
        penalty_notified TINYINT(1) DEFAULT 0,
        UNIQUE KEY unique_completion (task_id, user_id),
        INDEX idx_task (task_id),
        INDEX idx_user (user_id),
        INDEX idx_stay (must_stay_until, left_channel)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS user_task_penalties (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        task_id VARCHAR(50) NOT NULL,
        channel_username VARCHAR(100),
        penalty_amount DECIMAL(10,4) NOT NULL,
        reason TEXT,
        notified TINYINT(1) DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user (user_id),
        INDEX idx_notified (notified)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── SISTEMA DE BANS ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ban_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        event_type ENUM('ban','unban','update_reason') NOT NULL,
        reason TEXT,
        admin_id VARCHAR(50),
        related_users JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_event_type (event_type),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS user_device_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        device_hash VARCHAR(100) NOT NULL,
        user_agent TEXT,
        screen_info JSON,
        timezone VARCHAR(50),
        platform VARCHAR(50),
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_device (user_id, device_hash),
        INDEX idx_device_hash (device_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── TRANSACCIONES GENERALES ───────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        tx_id VARCHAR(100) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        tx_type VARCHAR(50) NOT NULL,
        currency VARCHAR(20) DEFAULT 'SE',
        amount DECIMAL(20,8) NOT NULL,
        status VARCHAR(30) DEFAULT 'completed',
        description TEXT DEFAULT NULL,
        reference_id VARCHAR(100) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_tx_type (tx_type),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── SEGURIDAD / FRAUD ─────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS security_events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) DEFAULT NULL,
        event_type VARCHAR(100) NOT NULL,
        severity VARCHAR(20) DEFAULT 'medium',
        ip_address VARCHAR(50) DEFAULT NULL,
        details TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_event_type (event_type),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS fraud_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        fraud_type VARCHAR(100) NOT NULL,
        details TEXT DEFAULT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        device_hash VARCHAR(100) DEFAULT NULL,
        auto_action VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_fraud_type (fraud_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS reoffense_tracking (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        offense_type VARCHAR(100) NOT NULL,
        offense_count INT DEFAULT 1,
        last_offense_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        first_offense_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_offense (user_id, offense_type),
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── HISTORIAL IP ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ip_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        ip_address VARCHAR(50) NOT NULL,
        event_type VARCHAR(50) DEFAULT 'login',
        user_agent TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_ip_address (ip_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── DEVICE FINGERPRINTS ───────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS device_fingerprints (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        fingerprint_hash VARCHAR(100) NOT NULL,
        fingerprint_data JSON DEFAULT NULL,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_fp (user_id, fingerprint_hash),
        INDEX idx_fingerprint_hash (fingerprint_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── BANS ──────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS user_bans (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        reason TEXT DEFAULT NULL,
        banned_by VARCHAR(50) DEFAULT 'system',
        banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME DEFAULT NULL,
        active TINYINT(1) DEFAULT 1,
        INDEX idx_user_id (user_id),
        INDEX idx_active (active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS banned_ips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ip_address VARCHAR(50) NOT NULL UNIQUE,
        reason VARCHAR(255) DEFAULT NULL,
        banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_ip_address (ip_address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS banned_devices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_hash VARCHAR(100) NOT NULL UNIQUE,
        reason VARCHAR(255) DEFAULT NULL,
        banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_device_hash (device_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── CANAL / MEMBRESÍA ─────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS channel_membership_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        channel_username VARCHAR(100) NOT NULL,
        action VARCHAR(50) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_channel (channel_username)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS channel_penalties (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        channel_username VARCHAR(100) NOT NULL,
        penalty_amount DECIMAL(10,4) NOT NULL,
        reason TEXT DEFAULT NULL,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── LOGS ADMIN ────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        admin_id VARCHAR(50) NOT NULL,
        action VARCHAR(200) NOT NULL,
        target_user_id VARCHAR(50) DEFAULT NULL,
        details TEXT DEFAULT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_admin_id (admin_id),
        INDEX idx_target_user (target_user_id),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    """
    CREATE TABLE IF NOT EXISTS admin_actions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        admin_id VARCHAR(50) NOT NULL,
        action_type VARCHAR(100) NOT NULL,
        target_id VARCHAR(100) DEFAULT NULL,
        target_type VARCHAR(50) DEFAULT NULL,
        before_value TEXT DEFAULT NULL,
        after_value TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_admin_id (admin_id),
        INDEX idx_action_type (action_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── AUTH LOGS ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS auth_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        event_type VARCHAR(50) DEFAULT 'login',
        success TINYINT(1) DEFAULT 1,
        ip_address VARCHAR(50) DEFAULT NULL,
        user_agent TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_event_type (event_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── WEB SESSIONS ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS web_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(128) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        user_agent TEXT DEFAULT NULL,
        data JSON DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME DEFAULT NULL,
        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_session_id (session_id),
        INDEX idx_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── WALLET ADDRESSES ──────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS wallet_addresses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        network VARCHAR(20) NOT NULL,
        address VARCHAR(200) NOT NULL,
        is_primary TINYINT(1) DEFAULT 0,
        verified TINYINT(1) DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_address (address)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── ACCOUNT STATES ────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS account_states (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        state VARCHAR(50) DEFAULT 'active',
        locked TINYINT(1) DEFAULT 0,
        lock_reason VARCHAR(255) DEFAULT NULL,
        last_state_change DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_state (state)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── AD TOKENS V2 ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ad_tokens_v2 (
        id INT AUTO_INCREMENT PRIMARY KEY,
        token VARCHAR(64) NOT NULL UNIQUE,
        user_id VARCHAR(50) NOT NULL,
        ad_type VARCHAR(30) DEFAULT 'rewarded',
        ad_network VARCHAR(50) DEFAULT NULL,
        status ENUM('pending','completed','claimed','expired') DEFAULT 'pending',
        reward DECIMAL(10,4) DEFAULT 0.0000,
        reward_pts INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME DEFAULT NULL,
        claimed_at DATETIME DEFAULT NULL,
        expires_at DATETIME NOT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        user_agent TEXT DEFAULT NULL,
        INDEX idx_token (token),
        INDEX idx_user_id (user_id),
        INDEX idx_status (status),
        INDEX idx_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── AD DAILY STATS V2 ─────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS ad_daily_stats_v2 (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        stat_date DATE NOT NULL,
        ad_network VARCHAR(50) DEFAULT NULL,
        ads_watched INT DEFAULT 0,
        ads_completed INT DEFAULT 0,
        total_earned DECIMAL(20,8) DEFAULT 0.00000000,
        total_pts INT DEFAULT 0,
        last_ad_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_date_network (user_id, stat_date, ad_network),
        INDEX idx_user_id (user_id),
        INDEX idx_stat_date (stat_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── USUARIOS (tabla alternativa que usa la app) ───────────────────────────
    """
    CREATE TABLE IF NOT EXISTS usuarioss (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL UNIQUE,
        username VARCHAR(100) DEFAULT NULL,
        first_name VARCHAR(100) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


# ─────────────────────────────────────────────
# CONFIGURACIÓN POR DEFECTO
# ─────────────────────────────────────────────
DEFAULT_CONFIG = [
    ('global_mining_power', '1.0'),
    ('base_mining_rate', '1.0'),
    ('referral_bonus', '1.0'),
    ('referral_commission', '0.05'),
    ('min_withdrawal_usdt', '0.5'),
    ('min_withdrawal_doge', '0.3'),
    ('min_withdrawal_se', '100'),
    ('min_withdrawal_ton', '0.1'),
    ('withdrawal_mode', 'manual'),
    ('se_to_usdt_rate', '0.01'),
    ('se_to_doge_rate', '0.06'),
    ('auto_ban_duplicate_ip', 'false'),
    ('show_promo_fab', 'true'),
    ('admin_password', 'admin123'),
    ('ad_task_cooldown_seconds', '30'),
    ('ad_task_default_reward', '0.1'),
    ('ad_task_max_daily_completions', '50'),
    ('antifraud_enabled', 'true'),
    ('max_accounts_per_ip', '3'),
    ('max_accounts_per_device', '2'),
    ('auto_ban_enabled', 'true'),
    ('ban_related_accounts', 'false'),
    ('min_deposit_doge', '1'),
    ('required_confirmations', '12'),
    ('deposits_enabled', 'true'),
]

DEFAULT_STATS = [
    ('total_starts', 0),
    ('total_claims', 0),
    ('total_tasks_completed', 0),
    ('total_withdrawals', 0),
    ('total_referrals', 0),
    ('validated_referrals', 0),
]

DEFAULT_REFERRAL_MISSIONS = [
    ('mission_3_refs', 'Invitar 3 amigos', 'Invita a 3 nuevos usuarios y gana DOGE', 3, 0.5, 'DOGE', 1),
    ('mission_5_refs', 'Invitar 5 amigos', 'Invita a 5 nuevos usuarios y gana DOGE', 5, 1.0, 'DOGE', 2),
    ('mission_10_refs', 'Invitar 10 amigos', 'Invita a 10 nuevos usuarios y gana DOGE', 10, 2.0, 'DOGE', 3),
]


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────
def init_all_tables():
    """
    Crea todas las tablas de la app si no existen.
    Seguro de llamar múltiples veces (usa IF NOT EXISTS).
    """
    logger.info("=" * 55)
    logger.info("🚀  INICIALIZANDO BASE DE DATOS RAILWAY")
    logger.info("=" * 55)

    if not test_connection():
        logger.error("❌ No se pudo conectar a la base de datos")
        return False

    total = len(ALL_TABLES)
    ok = 0
    errors = 0

    for i, sql in enumerate(ALL_TABLES, 1):
        # Extraer nombre de tabla para el log
        table_name = "tabla"
        for line in sql.split("\n"):
            line = line.strip()
            if "CREATE TABLE IF NOT EXISTS" in line:
                table_name = line.split("CREATE TABLE IF NOT EXISTS")[-1].strip().split("(")[0].strip()
                break
        try:
            execute_query(sql.strip())
            logger.info(f"  ✅ [{i:02d}/{total}] {table_name}")
            ok += 1
        except Exception as e:
            logger.error(f"  ❌ [{i:02d}/{total}] {table_name}: {e}")
            errors += 1

    # Insertar config por defecto
    logger.info("\n📝  Insertando configuración por defecto...")
    for key, value in DEFAULT_CONFIG:
        try:
            execute_query(
                "INSERT INTO config (config_key, config_value) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE config_key = config_key",
                (key, value)
            )
        except Exception:
            pass

    # Insertar stats por defecto
    for key, value in DEFAULT_STATS:
        try:
            execute_query(
                "INSERT INTO stats (stat_key, stat_value) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE stat_key = stat_key",
                (key, value)
            )
        except Exception:
            pass

    # Insertar misiones de referidos por defecto
    for mission_id, title, desc, req, reward, currency, order in DEFAULT_REFERRAL_MISSIONS:
        try:
            execute_query(
                "INSERT IGNORE INTO referral_missions "
                "(mission_id, title, description, required_referrals, reward_amount, reward_currency, display_order, active) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 1)",
                (mission_id, title, desc, req, reward, currency, order)
            )
        except Exception:
            pass

    logger.info("\n" + "=" * 55)
    logger.info(f"📊  RESULTADO: {ok} tablas OK  |  {errors} errores")
    logger.info("=" * 55)

    return errors == 0


# ─────────────────────────────────────────────
# EJECUCIÓN DIRECTA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    success = init_all_tables()
    if success:
        print("\n✅ Base de datos lista para Railway.")
    else:
        print("\n⚠️  Completado con algunos errores. Revisa los logs.")
        import sys; sys.exit(1)
