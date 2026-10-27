"""StudyCircle: small, dependency-free web server and SQLite API."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("STUDYCIRCLE_DATA", ROOT / "data"))
DB_PATH = DATA_DIR / "studycircle.sqlite3"
PORT = int(os.environ.get("PORT", "8000"))
UTC_OFFSET_MINUTES = int(os.environ.get("CAMPUS_UTC_OFFSET_MINUTES", "330"))
def campus_now() -> datetime:
    return datetime.now(timezone(timedelta(minutes=UTC_OFFSET_MINUTES)))
COOKIE = "studycircle_session"
SUBJECTS = {"Computer Science", "Mathematics", "Physics", "Economics", "Design", "Biology", "Chemistry", "Other"}


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return salt.hex() + ":" + hashed.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, hash_hex = encoded.split(":", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 310_000).hex()
        return hmac.compare_digest(actual, hash_hex)
    except Exception:
        return False


def initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL,
            date TEXT NOT NULL, time TEXT NOT NULL, location TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', host TEXT NOT NULL,
            capacity INTEGER NOT NULL CHECK(capacity BETWEEN 2 AND 8), created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS attendees (
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            username TEXT NOT NULL COLLATE NOCASE,
            PRIMARY KEY(session_id, username)
          );
          CREATE TABLE IF NOT EXISTS login_sessions (
            token_hash TEXT PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE,
            expires_at INTEGER NOT NULL
          );
          CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS sessions_date_time ON sessions(date, time);
          CREATE INDEX IF NOT EXISTS attendees_username ON attendees(username);
        """)
        seed_marker = db.execute("SELECT value FROM app_meta WHERE key='sample_data_seeded'").fetchone()
        if seed_marker is None:
            now = campus_now()
            today = now.date()
            demo_hash = hash_password("password123")
            demo_users = ["Maya", "Ishaan", "Aarav", "Zoya", "Kabir", "Riya", "Arjun", "Neha"]
            for u in demo_users:
                db.execute(
                    "INSERT OR IGNORE INTO users(username, password_hash, created_at) VALUES(?,?,?)",
                    (u, demo_hash, datetime.now(timezone.utc).isoformat())
                )

            time_slot_1 = (now + timedelta(hours=2)).strftime("%H:%M")
            time_slot_2 = (now + timedelta(hours=4)).strftime("%H:%M")
            past_date = (today - timedelta(days=1)).isoformat()

            samples = [
                ("seed-1", "Algorithms, slowly and together", "Computer Science", today.isoformat(), time_slot_1, "Central Library · Quiet Zone", "Working through graph problems. Bring one question to share.", "Maya", 4, ["Maya", "Arjun", "Neha"]),
                ("seed-2", "Linear algebra problem hour", "Mathematics", today.isoformat(), time_slot_2, "Block B · Room 204", "Eigenvalues and transformations, with lots of practice.", "Ishaan", 5, ["Ishaan", "Riya"]),
                ("seed-3", "Physics: mechanics recap", "Physics", (today + timedelta(days=1)).isoformat(), "10:00", "Science Building · 1st floor", "A relaxed review before the next quiz.", "Aarav", 4, ["Aarav", "Maya", "Kabir"]),
                ("seed-4", "Design critique & tea", "Design", (today + timedelta(days=2)).isoformat(), "15:00", "Studio 3 · Design Wing", "Bring a work in progress for kind, useful feedback.", "Zoya", 6, ["Zoya", "Neha"]),
                ("seed-5", "Microeconomics study sprint", "Economics", (today + timedelta(days=3)).isoformat(), "11:30", "Café Commons", "Supply, demand and problem sets. 50-minute focus blocks.", "Kabir", 4, ["Kabir"]),
                ("seed-6", "Cell biology flashcards", "Biology", (today + timedelta(days=4)).isoformat(), "13:00", "Life Sciences · Seminar 2", "Active recall session. Add your tricky terms to the deck.", "Riya", 5, ["Riya", "Aarav", "Ishaan"]),
                ("seed-past", "Operating Systems review", "Computer Science", past_date, "14:00", "Tech Lab 101", "Completed session on virtual memory and page replacement algorithms.", "Maya", 4, ["Maya", "Ishaan", "Arjun"]),
            ]
            for sid, title, subject, day_str, start, place, description, host, cap, attendees in samples:
                db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?)", (sid, title, subject, day_str, start, place, description, host, cap, datetime.now(timezone.utc).isoformat()))
                db.executemany("INSERT INTO attendees(session_id, username) VALUES(?,?)", [(sid, name) for name in attendees])
            db.execute("INSERT INTO app_meta(key,value) VALUES('sample_data_seeded','1')")


def clean_text(value: object, label: str, limit: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Enter a valid {label}.")
    result = value.strip()
    if required and not result:
        raise ValueError(f"{label.capitalize()} is required.")
    if len(result) > limit:
        raise ValueError(f"{label.capitalize()} must be {limit} characters or fewer.")
    return result


class Handler(SimpleHTTPRequestHandler):
    server_version = "StudyCircle/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def json_response(self, status: int, value: object, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if extra_headers:
            for key, val in extra_headers.items():
                self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 16_000:
                raise ValueError("Request body is missing or too large.")
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Request must be a JSON object.")
            return data
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Request contains invalid JSON.")

    def origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlparse(origin).netloc.lower() == self.headers.get("Host", "").lower()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def user(self) -> str | None:
        raw_cookie = self.headers.get("Cookie", "")
        token = next((part.split("=", 1)[1] for part in raw_cookie.split(";") if part.strip().startswith(COOKIE + "=")), None)
        if not token or len(token) > 200:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with connect() as db:
            row = db.execute("SELECT username FROM login_sessions WHERE token_hash=? AND expires_at>?", (digest, int(time.time()))).fetchone()
            return row["username"] if row else None

    def require_user(self) -> str | None:
        user = self.user()
        if user is None:
            self.json_response(401, {"error": "Sign in to continue."})
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            if path == "/api/me":
                user = self.user()
                return self.json_response(200, {"user": user})
            if path == "/api/sessions":
                user = self.require_user()
                if user is None: return
                with connect() as db:
                    rows = db.execute("SELECT * FROM sessions ORDER BY date, time").fetchall()
                    result = []
                    for row in rows:
                        attendees = [a[0] for a in db.execute("SELECT username FROM attendees WHERE session_id=? ORDER BY rowid", (row["id"],))]
                        item = dict(row)
                        item.update(attendees=attendees, isJoined=user.casefold() in [a.casefold() for a in attendees], isHost=user.casefold() == row["host"].casefold())
                        result.append(item)
                return self.json_response(200, {"sessions": result})
            return self.json_response(404, {"error": "That endpoint does not exist."})
        if path == "/": self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.origin_ok(): return self.json_response(403, {"error": "Request origin was not accepted."})
        try:
            data = self.read_json()
            if path in ("/api/register", "/api/login"):
                username = clean_text(data.get("username"), "username", 24)
                password = data.get("password")
                if not re.fullmatch(r"[A-Za-z0-9_-]{2,24}", username):
                    return self.json_response(400, {"error": "Use 2–24 letters, numbers, underscores, or hyphens for your username."})
                if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
                    return self.json_response(400, {"error": "Password must be between 8 and 128 characters."})
                with connect() as db:
                    if path == "/api/register":
                        encoded = hash_password(password)
                        try:
                            db.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)", (username, encoded, datetime.now(timezone.utc).isoformat()))
                        except sqlite3.IntegrityError:
                            return self.json_response(409, {"error": "That username is already taken."})
                    row = db.execute("SELECT username,password_hash FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone()
                    if not row: return self.json_response(401, {"error": "Username or password is incorrect."})
                    if not verify_password(password, row["password_hash"]):
                        return self.json_response(401, {"error": "Username or password is incorrect."})
                    token = secrets.token_urlsafe(32)
                    db.execute("INSERT INTO login_sessions(token_hash,username,expires_at) VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["username"], int(time.time()) + 60 * 60 * 24 * 14))
                secure_setting = os.environ.get("COOKIE_SECURE")
                use_secure_cookie = secure_setting == "1" if secure_setting is not None else self.headers.get("X-Forwarded-Proto", "http").lower() == "https"
                secure = "; Secure" if use_secure_cookie else ""
                cookie = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600{secure}"
                return self.json_response(200, {"user": row["username"]}, {"Set-Cookie": cookie})
            user = self.require_user()
            if user is None: return
            if path == "/api/sessions":
                title = clean_text(data.get("title"), "session name", 60)
                subject = clean_text(data.get("subject"), "subject", 40)
                if subject not in SUBJECTS: raise ValueError("Choose a listed subject.")
                place = clean_text(data.get("location"), "location", 50)
                description = clean_text(data.get("description", ""), "description", 180, required=False)
                day, start = clean_text(data.get("date"), "date", 10), clean_text(data.get("time"), "time", 5)
                try: begins = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M")
                except ValueError: raise ValueError("Choose a valid date and time.")
                if begins.replace(tzinfo=campus_now().tzinfo) <= campus_now(): raise ValueError("Choose a start time in the future.")
                capacity = data.get("capacity")
                if not isinstance(capacity, int) or not 2 <= capacity <= 8: raise ValueError("Group size must be between 2 and 8.")
                sid = secrets.token_urlsafe(12)
                with connect() as db:
                    conflict = db.execute("SELECT 1 FROM sessions WHERE host=? COLLATE NOCASE AND date=? AND time=?", (user, day, start)).fetchone()
                    if conflict: return self.json_response(409, {"error": "You already host a session at that time."})
                    db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?)", (sid, title, subject, day, start, place, description, user, capacity, datetime.now(timezone.utc).isoformat()))
                    db.execute("INSERT INTO attendees(session_id,username) VALUES(?,?)", (sid, user))
                return self.json_response(201, {"id": sid})
            match = re.fullmatch(r"/api/sessions/([A-Za-z0-9_-]+)/(join|leave)", path)
            if match:
                sid, action = match.groups()
                with connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
                    if not row: return self.json_response(404, {"error": "Session not found."})
                    if action == "join":
                        sess_dt = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M").replace(tzinfo=campus_now().tzinfo)
                        if sess_dt <= campus_now():
                            return self.json_response(400, {"error": "This session has already taken place."})
                        existing = db.execute("SELECT 1 FROM attendees WHERE session_id=? AND username=? COLLATE NOCASE", (sid, user)).fetchone()
                        if existing: return self.json_response(409, {"error": "You already have a seat in this circle."})
                        conflict = db.execute("""
                            SELECT s.title FROM attendees a
                            JOIN sessions s ON a.session_id = s.id
                            WHERE a.username = ? COLLATE NOCASE AND s.date = ? AND s.time = ?
                        """, (user, row["date"], row["time"])).fetchone()
                        if conflict:
                            return self.json_response(409, {"error": f"Schedule conflict: you are already in ‘{conflict['title']}’ at that time."})
                        count = db.execute("SELECT COUNT(*) FROM attendees WHERE session_id=?", (sid,)).fetchone()[0]
                        if count >= row["capacity"]: return self.json_response(409, {"error": "This circle is full."})
                        db.execute("INSERT INTO attendees(session_id,username) VALUES(?,?)", (sid, user))
                    else:
                        if user.casefold() == row["host"].casefold():
                            return self.json_response(400, {"error": "Hosts cannot leave their own session. Cancel the session instead."})
                        db.execute("DELETE FROM attendees WHERE session_id=? AND username=? COLLATE NOCASE", (sid, user))
                return self.json_response(200, {"ok": True})
            if path == "/api/logout":
                user = self.user()
                if user:
                    raw = self.headers.get("Cookie", "")
                    token = next((part.split("=", 1)[1] for part in raw.split(";") if part.strip().startswith(COOKIE + "=")), "")
                    with connect() as db: db.execute("DELETE FROM login_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
                return self.json_response(200, {"ok": True}, {"Set-Cookie": f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})
            return self.json_response(404, {"error": "That endpoint does not exist."})
        except ValueError as exc:
            return self.json_response(400, {"error": str(exc)})
        except (sqlite3.Error, OSError) as exc:
            print(f"Application error: {exc}")
            return self.json_response(500, {"error": "Something went wrong while saving. Please try again."})

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not self.origin_ok(): return self.json_response(403, {"error": "Request origin was not accepted."})
        user = self.require_user()
        if user is None: return
        match = re.fullmatch(r"/api/sessions/([A-Za-z0-9_-]+)", path)
        if not match: return self.json_response(404, {"error": "That endpoint does not exist."})
        try:
            with connect() as db:
                cur = db.execute("DELETE FROM sessions WHERE id=? AND host=? COLLATE NOCASE", (match.group(1), user))
                if cur.rowcount == 0:
                    exists = db.execute("SELECT 1 FROM sessions WHERE id=?", (match.group(1),)).fetchone()
                    return self.json_response(403 if exists else 404, {"error": "Only the host can cancel this session." if exists else "Session not found."})
            return self.json_response(200, {"ok": True})
        except sqlite3.Error as exc:
            print(f"Application error: {exc}")
            return self.json_response(500, {"error": "Something went wrong while cancelling. Please try again."})

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        super().end_headers()


if __name__ == "__main__":
    initialize()
    print(f"StudyCircle running at http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
