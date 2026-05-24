"""
SQLite Database Module for OPIP.
Handles persistence of users, scans, breaches, social accounts, and broker opt-outs.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "osint.db")

def get_db_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Scan history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT NOT NULL,
            query_type TEXT NOT NULL, -- 'email', 'username', 'phone', 'domain'
            exposure_score REAL DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Breach records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS breach_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            email TEXT NOT NULL,
            breach_name TEXT NOT NULL,
            breach_date TEXT,
            description TEXT,
            data_classes TEXT, -- JSON array
            pwn_count INTEGER,
            is_verified BOOLEAN,
            source_tool TEXT DEFAULT 'HIBP',
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)
    
    # Social accounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            platform TEXT NOT NULL,
            username TEXT NOT NULL,
            url TEXT,
            status TEXT DEFAULT 'Found',
            source_tool TEXT NOT NULL,
            query_original TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)
    
    # Phone scan results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS phone_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            phone_number TEXT NOT NULL,
            carrier TEXT,
            country TEXT,
            line_type TEXT,
            valid BOOLEAN,
            social_registrations TEXT, -- JSON array
            owner_confirmed BOOLEAN DEFAULT FALSE,
            confirmed_at TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)
    
    # Data broker opt-outs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS broker_optouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            broker_name TEXT NOT NULL,
            profile_url TEXT,
            optout_url TEXT,
            status TEXT DEFAULT 'pending', -- pending, submitted, awaiting_confirmation, confirmed, rejected
            submitted_at TIMESTAMP,
            confirmed_at TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Metadata records (documents, EXIF, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            file_path TEXT,
            source_type TEXT, -- 'document', 'image', 'office'
            metadata_json TEXT, -- Full JSON metadata
            extracted_entities TEXT, -- JSON array of entities found
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully.")

def create_user(name: str, email: str, photo_path: str = None) -> int:
    """Create a new user and return user ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, photo_path) VALUES (?, ?, ?)",
            (name, email, photo_path)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        # User already exists, fetch ID
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return row['id'] if row else -1
    finally:
        conn.close()

def create_scan(user_id: Optional[int], query: str, query_type: str) -> int:
    """Create a new scan record and return scan ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scans (user_id, query, query_type) VALUES (?, ?, ?)",
        (user_id, query, query_type)
    )
    conn.commit()
    scan_id = cursor.lastrowid
    conn.close()
    return scan_id

def save_breach_records(scan_id: int, email: str, breaches: List[Dict[str, Any]]):
    """Save breach results to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for breach in breaches:
        if 'error' in breach or 'warning' in breach:
            continue
        
        data_classes = json.dumps(breach.get('DataClasses', []))
        cursor.execute("""
            INSERT INTO breach_records 
            (scan_id, email, breach_name, breach_date, description, data_classes, pwn_count, is_verified, source_tool)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            email,
            breach.get('Name', 'Unknown'),
            breach.get('BreachDate'),
            breach.get('Description'),
            data_classes,
            breach.get('PwnCount'),
            breach.get('IsVerified', True),
            breach.get('source_tool', 'HIBP')
        ))
    
    conn.commit()
    conn.close()

def save_social_accounts(scan_id: int, accounts: List[Dict[str, Any]], query_original: str):
    """Save social account results to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for account in accounts:
        if 'error' in account or 'warning' in account:
            continue
        
        cursor.execute("""
            INSERT INTO social_accounts 
            (scan_id, platform, username, url, status, source_tool, query_original)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            account.get('platform', 'Unknown'),
            account.get('username', ''),
            account.get('url', ''),
            account.get('status', 'Found'),
            account.get('source_tool', 'Unknown'),
            query_original
        ))
    
    conn.commit()
    conn.close()

def get_user_scans(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent scans for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM scans 
        WHERE user_id = ? OR user_id IS NULL
        ORDER BY completed_at DESC 
        LIMIT ?
    """, (user_id, limit))
    
    scans = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return scans

def get_scan_details(scan_id: int) -> Dict[str, Any]:
    """Get full details of a scan including breaches and social accounts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get scan info
    cursor.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
    scan_row = cursor.fetchone()
    if not scan_row:
        conn.close()
        return {}
    
    scan = dict(scan_row)
    
    # Get breaches
    cursor.execute("SELECT * FROM breach_records WHERE scan_id = ?", (scan_id,))
    breaches = [dict(row) for row in cursor.fetchall()]
    
    # Get social accounts
    cursor.execute("SELECT * FROM social_accounts WHERE scan_id = ?", (scan_id,))
    social_accounts = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    scan['breaches'] = breaches
    scan['social_accounts'] = social_accounts
    return scan

def confirm_phone_ownership(scan_id: int):
    """Confirm phone number ownership after user verification."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE phone_records 
        SET owner_confirmed = TRUE, confirmed_at = CURRENT_TIMESTAMP
        WHERE scan_id = ?
    """, (scan_id,))
    conn.commit()
    conn.close()

def add_broker_optout(user_id: int, broker_name: str, profile_url: str = None, optout_url: str = None):
    """Add a new broker opt-out request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO broker_optouts (user_id, broker_name, profile_url, optout_url, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (user_id, broker_name, profile_url, optout_url))
    conn.commit()
    conn.close()

def get_broker_optouts(user_id: int) -> List[Dict[str, Any]]:
    """Get all broker opt-outs for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM broker_optouts 
        WHERE user_id = ? 
        ORDER BY submitted_at DESC
    """, (user_id,))
    optouts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return optouts

# Initialize DB on module load
if __name__ == "__main__":
    init_db()
