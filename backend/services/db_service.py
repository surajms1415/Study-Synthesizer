import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "stats.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def execute_query(query: str, params=(), fetch=False, fetchall=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    result = None
    if fetch:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
        
    conn.commit()
    conn.close()
    return result

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rating TEXT NOT NULL,
            comment TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            document_name TEXT,
            source_type TEXT,
            source_url TEXT,
            created_at TEXT NOT NULL,
            last_accessed_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL,
            content_hash TEXT
        )
    """)
    conn.commit()
    conn.close()

def increment_download():
    now = datetime.utcnow().isoformat()
    execute_query("INSERT INTO downloads (timestamp) VALUES (?)", (now,))

def add_feedback(rating: str, comment: str = None):
    now = datetime.utcnow().isoformat()
    execute_query("INSERT INTO feedback (rating, comment, timestamp) VALUES (?, ?, ?)", (rating, comment, now))

def get_stats():
    total_downloads = execute_query("SELECT COUNT(*) FROM downloads", fetch=True)[0]
    thumbs_up = execute_query("SELECT COUNT(*) FROM feedback WHERE rating = 'up'", fetch=True)[0]
    thumbs_down = execute_query("SELECT COUNT(*) FROM feedback WHERE rating = 'down'", fetch=True)[0]
    
    recent_rows = execute_query("SELECT rating, comment, timestamp FROM feedback WHERE comment IS NOT NULL AND comment != '' ORDER BY id DESC LIMIT 5", fetchall=True)
    
    recent_comments = [
        {"rating": row[0], "comment": row[1], "timestamp": row[2]}
        for row in recent_rows
    ]
    
    return {
        "downloads": total_downloads,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "recent_comments": recent_comments
    }

def get_all_feedback():
    rows = execute_query("SELECT id, rating, comment, timestamp FROM feedback ORDER BY id DESC", fetchall=True)
    return [
        {"id": row[0], "rating": row[1], "comment": row[2], "timestamp": row[3]}
        for row in rows
    ]

def delete_feedback(feedback_id: int):
    execute_query("DELETE FROM feedback WHERE id = ?", (feedback_id,))

# --- Document Lifecycle Management ---
from datetime import timedelta

def register_document(document_id: str, task_id: str, document_name: str, source_type: str, source_url: str = None, content_hash: str = None):
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=48)
    
    execute_query("""
        INSERT INTO documents (document_id, task_id, document_name, source_type, source_url, created_at, last_accessed_at, expires_at, status, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        ON CONFLICT(document_id) DO UPDATE SET
            last_accessed_at=excluded.last_accessed_at,
            expires_at=excluded.expires_at,
            status='active'
    """, (
        document_id, task_id, document_name, source_type, source_url or "",
        now.isoformat(), now.isoformat(), expires_at.isoformat(), content_hash or ""
    ))

def touch_task(task_id: str):
    """Refreshes last_accessed_at for all documents associated with a task"""
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=48)
    execute_query("""
        UPDATE documents 
        SET last_accessed_at = ?, expires_at = ?
        WHERE task_id = ?
    """, (now.isoformat(), expires_at.isoformat(), task_id))

def get_expired_documents() -> list:
    now = datetime.utcnow().isoformat()
    # Find all documents where expires_at <= current_time
    rows = execute_query("SELECT document_id, task_id FROM documents WHERE expires_at <= ?", (now,), fetchall=True)
    if not rows:
        return []
    return [{"document_id": r[0], "task_id": r[1]} for r in rows]

def delete_document_record(document_id: str):
    execute_query("DELETE FROM documents WHERE document_id = ?", (document_id,))
    
def get_task_documents(task_id: str) -> list:
    rows = execute_query("SELECT document_id FROM documents WHERE task_id = ?", (task_id,), fetchall=True)
    return [r[0] for r in rows]
