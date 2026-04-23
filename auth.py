import sqlite3
from passlib.hash import bcrypt

def create_user(username, password):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    hashed = bcrypt.hash(password)

    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    user = c.fetchone()

    conn.close()

    if user and bcrypt.verify(password, user[1]):
        return user[0]  # user_id
    return None