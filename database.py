import sqlite3
import pandas as pd
import re
import os
import time

DB_FILE = "clients.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

# Try to import psycopg2 for PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

_connection_pool = None
_db_initialized = False

class PostgreSQLPlaceholderCursor:
    """Wraps PostgreSQL cursor to translate SQLite '?' placeholders to '%s' dynamically."""
    def __init__(self, cursor):
        self._cursor = cursor
    def execute(self, query, params=None):
        if params is not None:
            query = query.replace("?", "%s")
        return self._cursor.execute(query, params)
    def __getattr__(self, name):
        return getattr(self._cursor, name)

class PostgreSQLPlaceholderConnection:
    """Wraps PostgreSQL connection to standardise row dict factories and cursors."""
    def __init__(self, conn, pool=None):
        self._conn = conn
        self._pool = pool
    def cursor(self):
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return PostgreSQLPlaceholderCursor(cursor)
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        if self._pool is not None:
            try:
                self._pool.putconn(self._conn)
            except Exception:
                self._conn.close()
        else:
            self._conn.close()
    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_pg_pool_streamlit(db_url):
    import streamlit as st
    @st.cache_resource
    def _create_pool(url):
        import psycopg2.pool
        return psycopg2.pool.ThreadedConnectionPool(1, 20, url)
    return _create_pool(db_url)

def get_db_connection():
    """Returns database connection. Checks for DATABASE_URL to connect to PostgreSQL (Supabase)."""
    global _connection_pool
    if DATABASE_URL and PSYCOPG2_AVAILABLE:
        # Check if running inside Streamlit
        is_streamlit = False
        try:
            from streamlit.runtime import exists
            is_streamlit = exists()
        except ImportError:
            pass
            
        if is_streamlit:
            pool = get_pg_pool_streamlit(DATABASE_URL)
        else:
            if _connection_pool is None:
                import psycopg2.pool
                _connection_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
            pool = _connection_pool
            
        conn = pool.getconn()
        return PostgreSQLPlaceholderConnection(conn, pool)
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database and create clients & messages tables. Supports both SQLite and PostgreSQL schemas."""
    global _db_initialized
    if _db_initialized:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL and PSYCOPG2_AVAILABLE:
        # PostgreSQL schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                client_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(30) NOT NULL,
                category VARCHAR(50),
                status VARCHAR(20) DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(30) NOT NULL,
                sender VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                msg_id VARCHAR(100) UNIQUE,
                media_b64 TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Migration: Add media_b64 if column doesn't exist
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS media_b64 TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
    else:
        # SQLite schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                category TEXT,
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                sender TEXT NOT NULL, -- 'client' or 'business'
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                msg_id TEXT UNIQUE,
                media_b64 TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Migration: Add media_b64 if column doesn't exist
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN media_b64 TEXT")
            conn.commit()
        except Exception:
            pass
        
    # Create indexes for fast query execution (eliminates full table scan lookup delays)
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages (phone)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp)")
        conn.commit()
    except Exception as e:
        print(f"Error creating indexes: {e}")
        
    conn.commit()
    conn.close()
    _db_initialized = True

def clean_phone_number(phone, default_country_code="91"):
    """
    Cleans a phone number:
    - Removes spaces, parentheses, dashes, and '+'
    - If the number is 10 digits, prefixes it with the default country code (e.g., 91 for India)
    - Returns a digits-only string
    """
    if not phone or pd.isna(phone):
        return ""
    
    # Cast to string and strip decimals if imported from float
    phone_str = str(phone).strip()
    if phone_str.endswith(".0"):
        phone_str = phone_str[:-2]
        
    # Remove all non-numeric characters
    cleaned = re.sub(r"\D", "", phone_str)
    
    # Auto-add country code if it is exactly 10 digits
    if len(cleaned) == 10 and default_country_code:
        cleaned = f"{default_country_code}{cleaned}"
        
    return cleaned

def add_client(client_id, name, phone, category, status="Active", default_country_code="91"):
    """Adds a new client to the database."""
    cleaned_phone = clean_phone_number(phone, default_country_code)
    if not cleaned_phone:
        raise ValueError("Invalid phone number")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO clients (client_id, name, phone, category, status) VALUES (?, ?, ?, ?, ?)",
            (client_id.strip(), name.strip(), cleaned_phone, category.strip() if category else "General", status)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Client ID must be unique
        raise ValueError(f"Client ID '{client_id}' already exists.")
    finally:
        conn.close()

def update_client(db_id, client_id, name, phone, category, status, default_country_code="91"):
    """Updates an existing client by database row ID."""
    cleaned_phone = clean_phone_number(phone, default_country_code)
    if not cleaned_phone:
        raise ValueError("Invalid phone number")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE clients 
               SET client_id = ?, name = ?, phone = ?, category = ?, status = ? 
               WHERE id = ?""",
            (client_id.strip(), name.strip(), cleaned_phone, category.strip() if category else "General", status, db_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        raise ValueError(f"Client ID '{client_id}' is already taken by another client.")
    finally:
        conn.close()

def delete_clients(ids):
    """Deletes multiple clients by database IDs."""
    if not ids:
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in ids)
    cursor.execute(f"DELETE FROM clients WHERE id IN ({placeholders})", tuple(ids))
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count

def clear_all_clients():
    """Wipes all data from the clients table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='clients'")  # Reset autoincrement
    conn.commit()
    conn.close()

def get_clients_dataframe(search_query="", category_filter="All", status_filter="All", limit=None, offset=None):
    """
    Fetches clients as a Pandas DataFrame with optional filters, search, and pagination.
    Returns: (DataFrame, total_filtered_count)
    """
    conn = get_db_connection()
    
    query = 'SELECT id, client_id as "Client ID", name as "Name", phone as "Phone", category as "Category", status as "Status", created_at as "Created At" FROM clients WHERE 1=1'
    params = []
    
    # Apply category filter
    if category_filter and category_filter != "All":
        query += " AND category = ?"
        params.append(category_filter)
        
    # Apply status filter
    if status_filter and status_filter != "All":
        query += " AND status = ?"
        params.append(status_filter)
        
    # Apply search query
    if search_query:
        query += " AND (client_id LIKE ? OR name LIKE ? OR phone LIKE ? OR category LIKE ?)"
        search_param = f"%{search_query}%"
        params.extend([search_param] * 4)
        
    # Get total count before pagination
    count_query = f"SELECT COUNT(*) FROM ({query})"
    cursor = conn.cursor()
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]
    
    # Add ordering
    query += " ORDER BY id DESC"
    
    # Apply pagination
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        query += " OFFSET ?"
        params.append(offset)
        
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df, total_count

def get_unique_categories():
    """Retrieves list of all unique client categories."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM clients WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

def get_unique_statuses():
    """Retrieves list of all unique client statuses."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT status FROM clients WHERE status IS NOT NULL ORDER BY status ASC")
    statuses = [row[0] for row in cursor.fetchall()]
    conn.close()
    return statuses

def bulk_import(df, default_country_code="91"):
    """
    Imports a dataframe into the SQLite database.
    Standardizes columns: expects 'Name' and 'Phone' (or similar matches).
    Optional columns: 'Client ID', 'Category', 'Status'.
    Automatically generates Client IDs if not present.
    """
    # Standardize column header mappings
    col_mappings = {}
    for col in df.columns:
        col_lower = str(col).lower().replace(" ", "").replace("_", "")
        if "id" in col_lower and "client" in col_lower:
            col_mappings[col] = "client_id"
        elif "name" in col_lower:
            col_mappings[col] = "name"
        elif "phone" in col_lower or "mobile" in col_lower or "number" in col_lower:
            col_mappings[col] = "phone"
        elif "cat" in col_lower:
            col_mappings[col] = "category"
        elif "status" in col_lower:
            col_mappings[col] = "status"
            
    # Rename columns using our mapping
    df_mapped = df.rename(columns=col_mappings)
    
    # Ensure critical columns exist
    if "name" not in df_mapped.columns or "phone" not in df_mapped.columns:
        raise ValueError("The uploaded file must contain 'Name' and 'Phone' columns.")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get last client number for ID generation fallback
    cursor.execute("SELECT COUNT(*) FROM clients")
    existing_count = cursor.fetchone()[0]
    
    success_count = 0
    failed_records = []
    
    for idx, row in df_mapped.iterrows():
        name = str(row["name"]).strip() if not pd.isna(row["name"]) else ""
        phone = str(row["phone"]).strip() if not pd.isna(row["phone"]) else ""
        
        if not name or not phone:
            failed_records.append({"Index": idx + 2, "Reason": "Missing Name or Phone"})
            continue
            
        cleaned_phone = clean_phone_number(phone, default_country_code)
        if not cleaned_phone:
            failed_records.append({"Index": idx + 2, "Name": name, "Reason": f"Invalid phone format: {phone}"})
            continue
            
        # Determine Client ID
        if "client_id" in df_mapped.columns and not pd.isna(row["client_id"]) and str(row["client_id"]).strip():
            client_id = str(row["client_id"]).strip()
        else:
            client_id = f"TPA-{existing_count + success_count + 1:04d}"
            
        category = str(row["category"]).strip() if "category" in df_mapped.columns and not pd.isna(row["category"]) else "General"
        status = str(row["status"]).strip() if "status" in df_mapped.columns and not pd.isna(row["status"]) else "Active"
        if status not in ["Active", "Inactive"]:
            status = "Active"
            
        # Insert or Replace to handle duplicates on Client ID
        try:
            cursor.execute(
                """INSERT INTO clients (client_id, name, phone, category, status)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(client_id) DO UPDATE SET
                       name=excluded.name,
                       phone=excluded.phone,
                       category=excluded.category,
                       status=excluded.status""",
                (client_id, name, cleaned_phone, category, status)
            )
            success_count += 1
        except Exception as e:
            failed_records.append({"Index": idx + 2, "Name": name, "Reason": str(e)})
            
    conn.commit()
    conn.close()
    
    return {
        "success": success_count,
        "failed": len(failed_records),
        "failures": failed_records
    }

def save_message(phone, sender, message, msg_id=None, media_b64=None):
    """Saves an incoming or outgoing chat message to the messages table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Standardize phone number format
        cleaned_phone = clean_phone_number(phone)
        
        # If no message ID is provided, generate a dummy one to satisfy unique constraint
        if not msg_id:
            msg_id = f"local_{cleaned_phone}_{time.time()}"
            
        cursor.execute(
            """INSERT INTO messages (phone, sender, message, msg_id, media_b64)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(msg_id) DO UPDATE SET
                   phone=excluded.phone,
                   sender=excluded.sender,
                   message=excluded.message,
                   media_b64=excluded.media_b64""",
            (cleaned_phone, sender, message.strip(), msg_id, media_b64)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving message: {e}")
        return False
    finally:
        conn.close()

def get_messages_for_phone(phone, limit=50):
    """Retrieves the latest chat messages for a specific phone number (ordered by timestamp)."""
    conn = get_db_connection()
    cleaned_phone = clean_phone_number(phone)
    query = f"""
        SELECT * FROM (
            SELECT sender, message, timestamp, msg_id, media_b64 
            FROM messages 
            WHERE phone = ? 
            ORDER BY timestamp DESC
            LIMIT {limit}
        ) sub
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn, params=[cleaned_phone])
    conn.close()
    return df

def get_conversations(search_query=None, limit=50):
    """
    Retrieves unique conversations (recent messages grouped by phone).
    Optionally filters by name/phone in the database, and limits results for speed.
    """
    conn = get_db_connection()
    
    # Build search condition
    search_cond = ""
    params = []
    if search_query:
        cleaned_q = f"%{search_query}%"
        # Support both SQLite and PostgreSQL placeholder types
        search_cond = "WHERE (m.phone LIKE ? OR COALESCE(c.name, '') LIKE ?)"
        params = [cleaned_q, cleaned_q]
        
    query = f"""
        SELECT m.phone, m.sender, m.message, m.timestamp, c.name
        FROM messages m
        LEFT JOIN clients c ON m.phone = c.phone
        INNER JOIN (
            SELECT phone, MAX(timestamp) as max_ts
            FROM messages
            GROUP BY phone
        ) last_msgs ON m.phone = last_msgs.phone AND m.timestamp = last_msgs.max_ts
        {search_cond}
        ORDER BY m.timestamp DESC
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def save_setting(key, value):
    """Saves a configuration key-value pair to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO settings (key, value)
               VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving setting {key}: {e}")
        return False
    finally:
        conn.close()

def get_setting(key):
    """Retrieves a configuration value by key from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting setting {key}: {e}")
        return None
    finally:
        conn.close()

def get_latest_incoming_message():
    """Retrieves the single latest incoming message from a client."""
    conn = get_db_connection()
    try:
        query = """
            SELECT m.phone, m.message, m.timestamp, m.msg_id, c.name
            FROM messages m
            LEFT JOIN clients c ON m.phone = c.phone
            WHERE m.sender = 'client'
            ORDER BY m.timestamp DESC
            LIMIT 1
        """
        df = pd.read_sql_query(query, conn)
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except Exception as e:
        print(f"Error getting latest incoming message: {e}")
        return None
    finally:
        conn.close()
