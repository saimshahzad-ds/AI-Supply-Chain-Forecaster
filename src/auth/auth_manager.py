# src/auth/auth_manager.py
import sqlite3
import bcrypt
import os

def _get_db_path():
    search_paths = [
        os.path.join(os.getcwd(), "database", "scm_forecaster.db"),
        os.path.join(os.getcwd(), "scm_forecaster.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "database", "scm_forecaster.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "scm_forecaster.db"),
    ]
    for p in search_paths:
        if os.path.exists(p):
            return os.path.abspath(p)
    return os.path.abspath(search_paths[0])

DB_PATH = _get_db_path()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    # hashed may be stored as bytes or string — handle both
    if isinstance(hashed, str):
        hashed = hashed.encode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def create_user(username, password, role, full_name="", email=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        hashed = hash_password(password)
        cursor.execute(
            "INSERT INTO User (username, password_hash, role, full_name, email) VALUES (?, ?, ?, ?, ?)",
            (username, hashed, role, full_name, email)
        )
        conn.commit()
        return True, "User created successfully!"
    except sqlite3.IntegrityError:
        return False, "Username already exists!"
    finally:
        conn.close()

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username, password_hash, role, full_name FROM User WHERE username = ?",
        (username,)
    )
    user = cursor.fetchone()
    conn.close()

    if user and check_password(password, user[2]):
        return {
            "user_id": user[0],
            "username": user[1],
            "role": user[3],
            "full_name": user[4]
        }
    return None

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username, full_name, email, role, created_at FROM User ORDER BY created_at DESC"
    )
    users = cursor.fetchall()
    conn.close()
    return users

def delete_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM User WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_user_role(user_id, new_role):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE User SET role = ? WHERE user_id = ?", (new_role, user_id))
    conn.commit()
    conn.close()

def create_default_admin():
    """Automatically creates the master admin account on startup if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM User WHERE username = 'Admin'")
    
    if not cursor.fetchone():
        hashed_pw = hash_password("Admin123")
        cursor.execute(
            "INSERT INTO User (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
            ("Admin", hashed_pw, "Admin", "Master Admin")
        )
        conn.commit()
    conn.close()