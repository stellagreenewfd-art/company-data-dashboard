# -*- coding: utf-8 -*-
"""
重置/创建管理员账号
用法（在 PythonAnywhere Bash 中执行）：
    cd ~/company-data-dashboard
    source venv/bin/activate
    python tools/reset_admin.py

效果：
- 若 yjdata2026 不存在，则创建为管理员，密码 yj2026
- 若 yjdata2026 已存在，则把该账号改为管理员并更新密码为 yj2026
- 可选：禁用默认 admin 账号（默认不禁用，避免误锁）
"""
import os, sys, sqlite3
from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
DB = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "company.db"))
os.makedirs(DATA_DIR, exist_ok=True)

TARGET_USER = os.environ.get("ADMIN_USER") or "yjdata2026"
TARGET_PASS = os.environ.get("ADMIN_PASS") or "yj2026"
DISABLE_OLD_ADMIN = os.environ.get("DISABLE_OLD_ADMIN", "0") == "1"

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # 确保 users 表存在
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user',
      status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT
    )""")
    ucols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
    if "status" not in ucols:
        c.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

    ph = generate_password_hash(TARGET_PASS)
    r = c.execute("SELECT id FROM users WHERE username=?", (TARGET_USER,)).fetchone()
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if r:
        c.execute("UPDATE users SET password_hash=?, role='admin', status='active' WHERE id=?", (ph, r[0]))
        print(f"[reset_admin] 已更新管理员 {TARGET_USER} / {TARGET_PASS}")
    else:
        c.execute("INSERT INTO users (username, password_hash, role, status, created_at) VALUES (?,?,?,?,?)",
                  (TARGET_USER, ph, "admin", "active", now))
        print(f"[reset_admin] 已创建管理员 {TARGET_USER} / {TARGET_PASS}")

    if DISABLE_OLD_ADMIN:
        c.execute("UPDATE users SET status='rejected' WHERE username='admin' AND username!=?", (TARGET_USER,))
        print("[reset_admin] 已禁用旧 admin 账号")

    conn.commit(); conn.close()
    print("[reset_admin] 完成")

if __name__ == "__main__":
    main()
