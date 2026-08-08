import sqlite3
import pandas as pd
import re
import os

DB_FILE = "clients.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database and create the clients table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

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
    
    query = "SELECT id, client_id as [Client ID], name as [Name], phone as [Phone], category as [Category], status as [Status], created_at as [Created At] FROM clients WHERE 1=1"
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
