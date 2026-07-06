import sqlite3
import sys
from pathlib import Path

import bcrypt

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data.db import USERS_DB_PATH

conn = sqlite3.connect(USERS_DB_PATH)
conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT
)
""")


def create_user(username, plain_password, role="manager"):
    hashed = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt())
    conn.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
        (username, hashed.decode(), role),
    )
    conn.commit()
    print(f"Created user '{username}' with a securely hashed password.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create a manager login for Staffing Copilot")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--role", default="manager")
    args = parser.parse_args()
    create_user(args.username, args.password, role=args.role)
