import sqlite3
from passlib.hash import pbkdf2_sha256

def create_user(username, password):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    hashed = pbkdf2_sha256.hash(password)

    try:
        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed)
        )
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

    if user and pbkdf2_sha256.verify(password, user[1]):
        return user[0]

    return None
