"""
db_wrapper.py - Database wrapper with transaction support
Provides safe transaction handling with automatic commit/rollback
"""

from contextlib import contextmanager
from db import get_db_connection

class DBWrapper:
    """
    Database wrapper that provides transaction support
    
    Usage:
        wrapper = DBWrapper()
        with wrapper.transaction() as cursor:
            cursor.execute("INSERT INTO ...")
            cursor.execute("UPDATE ...")
        # Auto-commits on success, auto-rollback on error
    """
    
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions
        Commits on successful exit, rolls back on exception
        """
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            connection.autocommit = False
            cursor = connection.cursor(buffered=True)
            
            yield cursor
            
            connection.commit()
            
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except:
                    pass
            raise e
            
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if connection:
                try:
                    connection.autocommit = True
                except:
                    pass
    
    @contextmanager
    def cursor(self):
        """
        Context manager for simple cursor operations (auto-commit mode)
        """
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor(buffered=True)
            
            yield cursor
            
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass

def execute(sql, params=None, fetch=False):
    """
    Execute a single SQL statement
    
    Args:
        sql: SQL query string
        params: Query parameters
        fetch: If True, return fetched results
    
    Returns:
        Results if fetch=True, else number of affected rows
    """
    wrapper = DBWrapper()
    with wrapper.cursor() as cursor:
        cursor.execute(sql, params or ())
        if fetch:
            return cursor.fetchall()
        return cursor.rowcount

def execute_many(sql, params_list):
    """
    Execute multiple SQL statements with different parameters
    
    Args:
        sql: SQL query string
        params_list: List of parameter tuples
    
    Returns:
        Total number of affected rows
    """
    wrapper = DBWrapper()
    total = 0
    with wrapper.transaction() as cursor:
        for params in params_list:
            cursor.execute(sql, params)
            total += cursor.rowcount
    return total

def fetch_one(sql, params=None):
    """
    Fetch a single row
    
    Returns:
        Single row tuple or None
    """
    wrapper = DBWrapper()
    with wrapper.cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchone()

def fetch_all(sql, params=None):
    """
    Fetch all rows
    
    Returns:
        List of row tuples
    """
    wrapper = DBWrapper()
    with wrapper.cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchall()

class TransactionScope:
    """
    Alternative transaction scope for multi-operation transactions
    
    Usage:
        scope = TransactionScope()
        try:
            scope.begin()
            scope.execute("INSERT INTO ...")
            scope.execute("UPDATE ...")
            scope.commit()
        except:
            scope.rollback()
            raise
        finally:
            scope.close()
    """
    
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    def begin(self):
        """Start a new transaction"""
        self.connection = get_db_connection()
        self.connection.autocommit = False
        self.cursor = self.connection.cursor(buffered=True)
        return self
    
    def execute(self, sql, params=None):
        """Execute a query within the transaction"""
        if not self.cursor:
            raise Exception("Transaction not started. Call begin() first.")
        self.cursor.execute(sql, params or ())
        return self.cursor.rowcount
    
    def fetchone(self):
        """Fetch one row from last query"""
        return self.cursor.fetchone() if self.cursor else None
    
    def fetchall(self):
        """Fetch all rows from last query"""
        return self.cursor.fetchall() if self.cursor else []
    
    def commit(self):
        """Commit the transaction"""
        if self.connection:
            self.connection.commit()
    
    def rollback(self):
        """Rollback the transaction"""
        if self.connection:
            try:
                self.connection.rollback()
            except:
                pass
    
    def close(self):
        """Close cursor and restore auto-commit"""
        if self.cursor:
            try:
                self.cursor.close()
            except:
                pass
            self.cursor = None
        if self.connection:
            try:
                self.connection.autocommit = True
            except:
                pass
            self.connection = None
    
    def __enter__(self):
        return self.begin()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False
