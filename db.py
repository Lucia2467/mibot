"""
🔌 DB.PY - Database Connection Pool Manager
Configured for Railway MySQL using environment variables.
"""

import os
import logging
import time
from contextlib import contextmanager
from threading import Lock

import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# PASSWORD VALIDATION
# ============================================

_mysql_password = os.getenv('MYSQLPASSWORD', '')

if not _mysql_password:
    logger.warning("⚠️ WARNING: MYSQLPASSWORD environment variable is missing or empty!")
    logger.warning("⚠️ Database connections will fail without a password.")
    logger.warning("⚠️ Please set MYSQLPASSWORD in your Railway environment variables.")

# ============================================
# DATABASE CONFIGURATION
# ============================================

DB_CONFIG = {
    'host': os.getenv('MYSQLHOST'),
    'database': os.getenv('MYSQLDATABASE'),
    'user': os.getenv('MYSQLUSER'),
    'password': os.getenv('MYSQLPASSWORD'),
    'port': int(os.getenv('MYSQLPORT', 3306)),
    'charset': 'utf8mb4',
    'autocommit': True,
}

# Pool settings
POOL_SIZE = 3
POOL_NAME = 'sally_pool'
MAX_RETRIES = 3
RETRY_DELAY = 0.5


def _get_friendly_error_message(error):
    """Convert MySQL errors to human-friendly messages"""
    error_str = str(error).lower()
    error_code = getattr(error, 'errno', None)

    if 'can\'t connect' in error_str or 'connection refused' in error_str or error_code == 2003:
        return "❌ Cannot connect to database server. Check MYSQLHOST is correct."

    if 'unknown database' in error_str or error_code == 1049:
        return "❌ Database does not exist. Check MYSQLDATABASE is correct."

    if 'access denied' in error_str or error_code == 1045:
        return "❌ Access denied. Check MYSQLUSER and MYSQLPASSWORD are correct."

    if 'timeout' in error_str or 'timed out' in error_str or error_code == 2013:
        return "❌ Connection timed out. Server may be overloaded or unreachable."

    if 'pool exhausted' in error_str or 'failed getting connection' in error_str:
        return "❌ Connection pool exhausted. Too many concurrent connections."

    if 'too many connections' in error_str or error_code == 1040:
        return "❌ Too many connections to MySQL server. Please wait and retry."

    if 'authentication' in error_str:
        return "❌ Authentication failed. Check your password is correct."

    return f"❌ Database error: {error}"


def _create_direct_connection():
    """Create a direct connection without pooling (fallback)"""
    if not _mysql_password:
        raise MySQLError("Cannot connect: MYSQLPASSWORD is not set")

    config = {
        'host': DB_CONFIG['host'],
        'database': DB_CONFIG['database'],
        'user': DB_CONFIG['user'],
        'password': DB_CONFIG['password'],
        'port': DB_CONFIG['port'],
        'charset': DB_CONFIG.get('charset', 'utf8mb4'),
        'autocommit': DB_CONFIG.get('autocommit', True),
    }

    return mysql.connector.connect(**config)


class DatabasePool:
    """
    Singleton database connection pool manager.
    Thread-safe with automatic reconnection.
    """
    _instance = None
    _lock = Lock()
    _pool = None
    _initialized = False
    _pool_failed = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._create_pool()
                    DatabasePool._initialized = True

    def _create_pool(self):
        """Create the connection pool"""
        if not _mysql_password:
            logger.error("❌ Cannot create pool: MYSQLPASSWORD is not set")
            self._pool = None
            self._pool_failed = True
            return

        try:
            pool_config = {
                'host': DB_CONFIG['host'],
                'database': DB_CONFIG['database'],
                'user': DB_CONFIG['user'],
                'password': DB_CONFIG['password'],
                'port': DB_CONFIG['port'],
                'charset': DB_CONFIG.get('charset', 'utf8mb4'),
                'autocommit': DB_CONFIG.get('autocommit', True),
            }

            self._pool = pooling.MySQLConnectionPool(
                pool_name=POOL_NAME,
                pool_size=POOL_SIZE,
                pool_reset_session=True,
                **pool_config
            )
            self._pool_failed = False
            logger.info(f"✅ Database pool created: {POOL_NAME} (size: {POOL_SIZE})")

        except MySQLError as e:
            friendly_msg = _get_friendly_error_message(e)
            logger.error(f"Pool creation failed: {friendly_msg}")
            self._pool = None
            self._pool_failed = True

        except Exception as e:
            logger.error(f"❌ Unexpected error creating pool: {e}")
            self._pool = None
            self._pool_failed = True

    def get_connection(self):
        """Get a connection from the pool with retry logic and fallback"""
        last_error = None

        if not _mysql_password:
            raise MySQLError("Cannot connect: MYSQLPASSWORD environment variable is not set. Please configure your Railway environment variables.")

        for attempt in range(MAX_RETRIES):
            try:
                if self._pool is not None:
                    conn = self._pool.get_connection()

                    if conn.is_connected():
                        return conn
                    else:
                        try:
                            conn.reconnect()
                            return conn
                        except:
                            conn.close()
                            raise MySQLError("Connection lost and reconnect failed")

                elif not self._pool_failed:
                    self._create_pool()
                    if self._pool is not None:
                        continue

                logger.warning(f"⚠️ Using fallback direct connection (attempt {attempt + 1})")
                conn = _create_direct_connection()
                if conn.is_connected():
                    return conn

            except MySQLError as e:
                last_error = e
                friendly_msg = _get_friendly_error_message(e)
                logger.warning(f"⚠️ Connection attempt {attempt + 1}/{MAX_RETRIES} failed: {friendly_msg}")

                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

                    if "pool exhausted" in str(e).lower():
                        self._pool = None
                        self._pool_failed = False
                        self._create_pool()

            except Exception as e:
                last_error = MySQLError(str(e))
                logger.warning(f"⚠️ Connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")

                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

        if last_error:
            friendly_msg = _get_friendly_error_message(last_error)
            logger.error(f"All connection attempts failed: {friendly_msg}")
            raise MySQLError(friendly_msg)
        else:
            raise MySQLError("❌ Failed to establish database connection after all retries")

    def release_connection(self, conn):
        """Release a connection back to the pool"""
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    @property
    def is_connected(self):
        """Check if pool has active connections"""
        try:
            conn = self.get_connection()
            result = conn.is_connected()
            self.release_connection(conn)
            return result
        except Exception:
            return False


# Global pool instance
_db_pool = None


def get_pool():
    """Get the global database pool instance"""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool()
    return _db_pool


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically releases connection when done.

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users")
    """
    pool = get_pool()
    conn = None
    try:
        conn = pool.get_connection()
        yield conn
    except MySQLError as e:
        friendly_msg = _get_friendly_error_message(e)
        logger.error(f"Database error: {friendly_msg}")
        raise
    finally:
        if conn:
            pool.release_connection(conn)


@contextmanager
def get_cursor(dictionary=True, buffered=True):
    """
    Context manager for database cursor.
    Automatically handles connection and cursor lifecycle.

    Usage:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
    """
    with get_db_connection() as conn:
        cursor = None
        try:
            cursor = conn.cursor(dictionary=dictionary, buffered=buffered)
            yield cursor
            conn.commit()
        except MySQLError as e:
            conn.rollback()
            friendly_msg = _get_friendly_error_message(e)
            logger.error(f"Cursor error: {friendly_msg}")
            raise
        finally:
            if cursor:
                cursor.close()


def execute_query(query, params=None):
    """
    Execute a query and return the result.

    Intended for INSERT/UPDATE/DELETE operations.
    Use get_cursor() with fetchone()/fetchall() for SELECT queries.

    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)

    Returns:
        lastrowid for INSERT, rowcount for UPDATE/DELETE
    """
    with get_cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.lastrowid if cursor.lastrowid else cursor.rowcount


def execute_many(query, params_list):
    """
    Execute a query with multiple parameter sets.

    Args:
        query: SQL query string
        params_list: List of parameter tuples/dicts

    Returns:
        Number of affected rows
    """
    with get_cursor() as cursor:
        cursor.executemany(query, params_list)
        return cursor.rowcount


def test_connection():
    """Test database connectivity"""
    try:
        if not _mysql_password:
            logger.error("❌ Database test failed: MYSQLPASSWORD is not set")
            return False

        with get_cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            if result and result.get('test') == 1:
                logger.info("✅ Database connection test successful")
                return True
    except MySQLError as e:
        friendly_msg = _get_friendly_error_message(e)
        logger.error(f"Database connection test failed: {friendly_msg}")
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
    return False


# Test connection on module load
if __name__ == "__main__":
    test_connection()
