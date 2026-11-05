import sqlite3
from pathlib import Path
from datetime import date
import json

DB_PATH = Path(__file__).resolve().parent / "study_planner.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            exam_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            daily_hours INTEGER NOT NULL DEFAULT 3,
            start_time TEXT NOT NULL DEFAULT '17:00',
            planning_days INTEGER NOT NULL DEFAULT 7
        );
        INSERT OR IGNORE INTO settings (id, daily_hours, start_time, planning_days)
        VALUES (1, 3, '17:00', 7);
        """)

def add_subject(name, difficulty, exam_date, topic_names):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO subjects(name, difficulty, exam_date) VALUES (?, ?, ?)",
            (name, difficulty, exam_date),
        )
        subject_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO topics(subject_id, title) VALUES (?, ?)",
            [(subject_id, t) for t in topic_names],
        )

def list_subjects():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM subjects ORDER BY exam_date, name").fetchall()
        result = []
        for row in rows:
            topics = conn.execute(
                "SELECT title, status FROM topics WHERE subject_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            result.append({
                "id": row["id"], "name": row["name"],
                "difficulty": row["difficulty"], "exam_date": row["exam_date"],
                "topics": [t["title"] for t in topics],
                "completed_topics": sum(1 for t in topics if t["status"] == "completed"),
                "total_topics": len(topics),
            })
        return result

def get_subjects_for_planner():
    with get_connection() as conn:
        subjects = conn.execute("SELECT * FROM subjects ORDER BY exam_date").fetchall()
        result = []
        for subject in subjects:
            topics = conn.execute(
                "SELECT title, status FROM topics WHERE subject_id = ? ORDER BY id",
                (subject["id"],),
            ).fetchall()
            result.append({
                "name": subject["name"],
                "difficulty": subject["difficulty"],
                "exam_date": subject["exam_date"],
                "topics": [{"title": t["title"], "status": t["status"]} for t in topics],
            })
        return result

def delete_subject(subject_id):
    with get_connection() as conn:
        subject = conn.execute("SELECT name FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if subject:
            conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
            conn.execute("DELETE FROM sessions WHERE subject=?", (subject["name"],))

def get_settings():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return dict(row)

def save_settings(daily_hours, start_time, planning_days):
    with get_connection() as conn:
        conn.execute(
            "UPDATE settings SET daily_hours=?, start_time=?, planning_days=? WHERE id=1",
            (daily_hours, start_time, planning_days),
        )

def get_sessions(session_date):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE session_date=? ORDER BY start_time, id",
            (session_date,),
        ).fetchall()
        return [dict(r) for r in rows]

def save_sessions(sessions):
    if not sessions:
        return
    with get_connection() as conn:
        conn.executemany("""
            INSERT INTO sessions
            (session_date, subject, topic, start_time, duration_minutes, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, [
            (
                s["date"], s["subject"], s["topic"], s["start_time"],
                int(s["duration_minutes"]), s.get("notes", ""),
            )
            for s in sessions
        ])
        # Sync topic-level completion with any sessions already marked completed.
        for s in sessions:
            conn.execute(
                "UPDATE topics SET status='pending' WHERE title=? AND subject_id IN "
                "(SELECT id FROM subjects WHERE name=?)",
                (s["topic"], s["subject"]),
            )

def update_session_status(session_id, status):
    if status not in {"pending", "completed", "skipped"}:
        return
    with get_connection() as conn:
        row = conn.execute("SELECT subject, topic FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return
        conn.execute("UPDATE sessions SET status=? WHERE id=?", (status, session_id))
        if status == "completed":
            conn.execute(
                "UPDATE topics SET status='completed' WHERE title=? AND subject_id IN "
                "(SELECT id FROM subjects WHERE name=?)",
                (row["topic"], row["subject"]),
            )
        elif status == "pending":
            conn.execute(
                "UPDATE topics SET status='pending' WHERE title=? AND subject_id IN "
                "(SELECT id FROM subjects WHERE name=?)",
                (row["topic"], row["subject"]),
            )

def get_pending_topics():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT s.name AS subject, s.difficulty, s.exam_date, t.title AS topic
            FROM topics t JOIN subjects s ON s.id=t.subject_id
            WHERE t.status != 'completed'
            ORDER BY s.exam_date
        """).fetchall()
        return [dict(r) for r in rows]

def get_progress_summary():
    with get_connection() as conn:
        topic_rows = conn.execute("""
            SELECT t.status, s.id AS subject_id, s.name
            FROM topics t JOIN subjects s ON s.id=t.subject_id
        """).fetchall()
        completed = sum(1 for r in topic_rows if r["status"] == "completed")
        total = len(topic_rows)
        pending = total - completed
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        subject_progress = []
        for subject in conn.execute("SELECT id, name FROM subjects ORDER BY name").fetchall():
            rows = conn.execute(
                "SELECT status FROM topics WHERE subject_id=?", (subject["id"],)
            ).fetchall()
            subject_completed = sum(1 for r in rows if r["status"] == "completed")
            subject_progress.append({
                "name": subject["name"], "completed": subject_completed, "total": len(rows)
            })
        return {
            "completed": completed, "pending": pending, "total_topics": total,
            "total_sessions": session_count,
            "completion_pct": round((completed / total) * 100) if total else 0,
            "subject_progress": subject_progress,
        }

def clear_future_plan(from_date, keep_completed=False):
    with get_connection() as conn:
        if keep_completed:
            conn.execute(
                "DELETE FROM sessions WHERE session_date>=? AND status!='completed'",
                (from_date,),
            )
        else:
            conn.execute("DELETE FROM sessions WHERE session_date>=?", (from_date,))
