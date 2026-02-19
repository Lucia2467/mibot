# ============================================
# SALLY-E Bot / DOGE PIXEL - Environment Configuration
# ============================================
# Copy this file to .env and fill in your values
# NEVER commit .env to version control!

# ============== DATABASE (MySQL) ==============
MYSQL_HOST=Isaax23.mysql.pythonanywhere-services.com
MYSQL_DATABASE=Isaax23$sally_db
MYSQL_USER=Isaax23
MYSQL_PASSWORD=Zulia*22

# ============== TELEGRAM BOT ==============
BOT_TOKEN=8392033822:AAG4kZBJCynL4UnmC7zYnvupfRZtBH8MZDk
BOT_USERNAME=SallyEbot
OFFICIAL_CHANNEL=@SallyE_Comunity
SUPPORT_GROUP=https://t.me/Soporte_Sally

# ============== WEB APPLICATION ==============
WEBAPP_URL=https://isaax23.pythonanywhere.com
SECRET_KEY=31354923

# ============== ADMIN ==============
# Comma-separated list of Telegram user IDs
ADMIN_IDS=5515244003

# ============== WALLET (BSC/BEP20) ==============
# Your wallet address that holds USDT/DOGE for withdrawals
ADMIN_ADDRESS=0x4e6FAC5144a345Cac1bb819d2f0964331925edbA

# Private key WITHOUT 0x prefix
# KEEP THIS SECRET! Never share or commit!
ADMIN_PRIVATE_KEY=4abdf8e2d82ce5f4ff89c8f9f093baef824734af303701c9ab1862348198a205

# BSC RPC endpoint
BSC_RPC=https://bsc-dataseed.binance.org/

# ============== TON NETWORK CONFIGURATION ==============
# Your TON wallet address (user-friendly format: EQ... or UQ...)
# This is the SOURCE wallet from which all TON payments will be sent
TON_WALLET_ADDRESS=

# TON wallet mnemonic (24 words, space-separated)
# CRITICAL: KEEP THIS SECRET! NEVER share or expose!
# Required for automatic payment processing
# Example: word1 word2 word3 ... word24
TON_WALLET_MNEMONIC=

# TonCenter API Key (get from @tonapibot on Telegram)
# Free tier: 1 request/second, 10 requests/second with API key
TON_API_KEY=

# Use testnet instead of mainnet (true/false)
# Set to 'true' for testing before going live
TON_TESTNET=false

# Optional: External payment service (for enhanced security)
# If configured, transactions will be signed by an external service
# instead of using the mnemonic directly
TON_PAYMENT_SERVICE_URL=
TON_PAYMENT_SERVICE_KEY=

# ============== WITHDRAWAL SETTINGS ==============
# Mode: 'manual' (admin approval) or 'automatic' (instant)
WITHDRAWAL_MODE=manual

# Minimum withdrawal amounts
MIN_WITHDRAWAL_USDT=0.5
MIN_WITHDRAWAL_DOGE=0.3
MIN_WITHDRAWAL_TON=0.1

# Maximum withdrawal amounts (per transaction)
MAX_WITHDRAWAL_TON=100

# TON withdrawal fee (in TON)
TON_WITHDRAWAL_FEE=0.01

# ============== MINING SETTINGS ==============
# Base mining rate per hour
BASE_MINING_RATE=0.1

# Global mining power multiplier
GLOBAL_MINING_POWER=1.0

# Referral bonus in S-E
REFERRAL_BONUS=1.0

# ============== SWAP RATES ==============
# S-E to crypto conversion rates
SE_TO_USDT_RATE=0.01
SE_TO_DOGE_RATE=0.06
SE_TO_TON_RATE=0.01

# ============================================
# IMPORTANT SECURITY NOTES:
# ============================================
# 1. NEVER share your TON_WALLET_MNEMONIC with anyone
# 2. Store a backup of your mnemonic in a secure offline location
# 3. Consider using an external payment service for production
# 4. Always test with TON_TESTNET=true before going live
# 5. Monitor your wallet balance regularly
# 6. Set up wallet balance alerts
# ============================================
