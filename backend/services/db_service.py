import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

# Check if using PostgreSQL
IS_POSTGRES = DATABASE_URL and DATABASE_URL.startswith("postgres")

if IS_POSTGRES:
    import psycopg2
    from psycopg2.extras import DictCursor
    # Fix for SQLAlchemy format urls
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "stats.db")

def get_connection():
    if IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(DB_PATH)

def execute_query(query: str, params=(), fetch=False, fetchall=False):
    conn = get_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        # Convert sqlite ? to postgres %s
        query = query.replace("?", "%s")
    
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
    
    if IS_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                rating TEXT NOT NULL,
                comment TEXT,
                timestamp TEXT NOT NULL
            )
        """)
    else:
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
