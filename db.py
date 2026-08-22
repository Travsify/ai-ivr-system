"""
Multi-Tenant SQLite Database Manager.
Handles Users, Passwords, User-Scoped Custom Departments, Custom Voices, Persistent Workspace Settings, Call History, and Transcripts.
"""

import sqlite3
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "ivr_calls.db")


def init_db():
    """Initializes SQLite database schema for Multi-Tenant SaaS with safe auto-migration."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT,
            created_at TEXT
        )
    """)
    
    # User Departments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            dept_id TEXT NOT NULL,
            name TEXT NOT NULL,
            digit TEXT NOT NULL,
            voice TEXT NOT NULL,
            hold_music TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            greeting TEXT NOT NULL,
            UNIQUE(user_id, dept_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # User Persistent Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            company_name TEXT,
            selected_voice TEXT,
            selected_hold_music TEXT,
            router_greeting TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # User Custom Voices Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_custom_voices (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            voice_name TEXT NOT NULL,
            voice_code TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Call Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_logs (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            caller_phone TEXT,
            start_time TEXT,
            end_time TEXT,
            initial_department TEXT,
            final_department TEXT,
            status TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(call_logs)")
    columns = [info[1] for info in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE call_logs ADD COLUMN user_id TEXT DEFAULT 'demo_user'")
    
    # Call Transcripts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TEXT,
            speaker TEXT,
            department TEXT,
            message TEXT,
            FOREIGN KEY (session_id) REFERENCES call_logs(session_id)
        )
    """)
    
    # Custom Audio File Mappings Table (tracks uploaded audio files per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_audio_mappings (
            user_id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            uploaded_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Autonomous Sales & Deals Pipeline Table ($1B Unicorn Architecture)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT UNIQUE NOT NULL,
            call_sid TEXT,
            user_id TEXT NOT NULL,
            caller_phone TEXT,
            department TEXT,
            pickup_address TEXT,
            delivery_address TEXT,
            pickup_date TEXT,
            vehicle_type TEXT,
            price_quoted REAL,
            status TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def create_user(email: str, password_hash: str, company_name: str = "My Business") -> Dict[str, Any]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO users (id, email, password_hash, company_name, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, email.lower().strip(), password_hash, company_name, now))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("Email address already registered.")
    
    conn.close()
    return {"id": user_id, "email": email, "company_name": company_name}


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, email, company_name, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_settings(user_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_user_settings(user_id: str, company_name: str, selected_voice: str, selected_hold_music: str, router_greeting: str):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO user_settings (user_id, company_name, selected_voice, selected_hold_music, router_greeting, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, company_name, selected_voice, selected_hold_music, router_greeting, now))
    
    conn.commit()
    conn.close()


def save_user_custom_voice(user_id: str, voice_name: str, voice_code: str) -> Dict[str, Any]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    voice_id = f"custom_voice_{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO user_custom_voices (id, user_id, voice_name, voice_code, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (voice_id, user_id, voice_name, voice_code, now))
    
    conn.commit()
    conn.close()
    return {"id": voice_id, "user_id": user_id, "voice_name": voice_name, "voice_code": voice_code}


def get_user_custom_voices(user_id: str) -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, voice_name, voice_code, created_at FROM user_custom_voices WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_departments(user_id: str) -> Dict[str, Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_departments WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        from departments import DEFAULT_DEPARTMENTS
        return DEFAULT_DEPARTMENTS
        
    depts = {}
    for r in rows:
        d = dict(r)
        depts[d["dept_id"]] = d
    return depts


def save_user_department(user_id: str, dept_id: str, name: str, digit: str, voice: str, system_prompt: str, greeting: str, hold_music: str = "smooth_jazz"):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO user_departments (user_id, dept_id, name, digit, voice, hold_music, system_prompt, greeting)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, dept_id, name, digit, voice, hold_music, system_prompt, greeting))
    
    conn.commit()
    conn.close()


def record_call_start(session_id: str, caller_phone: str, initial_department: str = "router", user_id: str = "demo_user"):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO call_logs (session_id, user_id, caller_phone, start_time, initial_department, final_department, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    """, (session_id, user_id, caller_phone, now, initial_department, initial_department))
    
    conn.commit()
    conn.close()


def record_transcript(session_id: str, speaker: str, department: str, message: str):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO call_transcripts (session_id, timestamp, speaker, department, message)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, now, speaker, department, message))
    
    conn.commit()
    conn.close()


def update_call_status(session_id: str, final_department: str, status: str = "completed"):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        UPDATE call_logs
        SET end_time = ?, final_department = ?, status = ?
        WHERE session_id = ?
    """, (now, final_department, status, session_id))
    
    conn.commit()
    conn.close()


def get_all_call_logs(user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute("""
            SELECT session_id, caller_phone, start_time, end_time, initial_department, final_department, status
            FROM call_logs
            WHERE user_id = ?
            ORDER BY start_time DESC
            LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
            SELECT session_id, caller_phone, start_time, end_time, initial_department, final_department, status
            FROM call_logs
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_call_transcripts(session_id: str) -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, speaker, department, message
        FROM call_transcripts
        WHERE session_id = ?
        ORDER BY id ASC
    """, (session_id,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_custom_audio_mapping(user_id: str, file_id: str, original_filename: str):
    """Persist a mapping from user_id to uploaded audio file so it survives restarts."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO custom_audio_mappings (user_id, file_id, original_filename, uploaded_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, file_id, original_filename, now))
    conn.commit()
    conn.close()


def get_user_custom_audio_mapping(user_id: str) -> Optional[Dict[str, Any]]:
    """Get the custom audio mapping for a specific user."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_audio_mappings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_custom_audio_mappings() -> List[Dict[str, Any]]:
    """Get all custom audio mappings for startup reload."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_audio_mappings")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_deal(user_id: str, booking_id: str, caller_phone: str, department: str, pickup: str, delivery: str, date: str, vehicle: str, price: float, status: str = "CLOSED_WON", call_sid: str = None) -> Dict[str, Any]:
    """Saves or updates an autonomous deal in the sales pipeline."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO deals (booking_id, call_sid, user_id, caller_phone, department, pickup_address, delivery_address, pickup_date, vehicle_type, price_quoted, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (booking_id, call_sid, user_id, caller_phone, department, pickup, delivery, date, vehicle, price, status, now, now))
    
    conn.commit()
    conn.close()
    return {
        "booking_id": booking_id,
        "user_id": user_id,
        "caller_phone": caller_phone,
        "department": department,
        "pickup": pickup,
        "delivery": delivery,
        "date": date,
        "vehicle": vehicle,
        "price": price,
        "status": status,
        "created_at": now
    }


def get_user_deals(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all deals recorded for a specific user."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deals WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_deals() -> List[Dict[str, Any]]:
    """Retrieves all deals in system for admin/pipeline stats."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deals ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_db()
