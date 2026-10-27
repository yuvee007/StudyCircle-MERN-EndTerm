"""Comprehensive unit and integration test suite for StudyCircle server."""
import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

# Point to temporary database directory for isolation
TEMP_DIR = tempfile.mkdtemp(prefix="studycircle_test_")
os.environ["STUDYCIRCLE_DATA"] = TEMP_DIR
os.environ["COOKIE_SECURE"] = "0"
os.environ["PORT"] = "9998"

import server


class StudyCircleAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.DATA_DIR = server.Path(TEMP_DIR)
        server.DB_PATH = server.DATA_DIR / "studycircle.sqlite3"
        server.initialize()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 9998), server.Handler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    def request(self, method, path, body=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", 9998)
        headers = {"Host": "127.0.0.1:9998"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))
        else:
            data = None
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        set_cookie = res.getheader("Set-Cookie")
        cookie_header = None
        if set_cookie:
            cookie_header = set_cookie.split(";")[0]
        return res.status, parsed, cookie_header

    def test_01_seed_data_and_demo_users_exist(self):
        # Demo user Maya should be able to log in with password123
        status, body, cookie = self.request("POST", "/api/login", {"username": "Maya", "password": "password123"})
        self.assertEqual(status, 200)
        self.assertEqual(body.get("user"), "Maya")
        self.assertIsNotNone(cookie)

        # /api/me should confirm authenticated user
        status, body, _ = self.request("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("user"), "Maya")

        # /api/sessions should return list of sessions
        status, body, _ = self.request("GET", "/api/sessions", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("sessions", body)
        self.assertGreater(len(body["sessions"]), 0)

    def test_02_register_validation(self):
        # Username too short
        status, body, _ = self.request("POST", "/api/register", {"username": "a", "password": "password123"})
        self.assertEqual(status, 400)

        # Invalid username characters
        status, body, _ = self.request("POST", "/api/register", {"username": "bad name!", "password": "password123"})
        self.assertEqual(status, 400)

        # Password too short
        status, body, _ = self.request("POST", "/api/register", {"username": "newuser", "password": "123"})
        self.assertEqual(status, 400)

        # Duplicate username (Maya is seeded)
        status, body, _ = self.request("POST", "/api/register", {"username": "Maya", "password": "password123"})
        self.assertEqual(status, 409)

    def test_03_register_and_login_flow(self):
        status, body, cookie = self.request("POST", "/api/register", {"username": "TestStudent", "password": "validpassword123"})
        self.assertEqual(status, 200)
        self.assertEqual(body.get("user"), "TestStudent")
        self.assertIsNotNone(cookie)

        # Logging in again
        status, body, new_cookie = self.request("POST", "/api/login", {"username": "TestStudent", "password": "validpassword123"})
        self.assertEqual(status, 200)
        self.assertIsNotNone(new_cookie)

        # Wrong password
        status, body, _ = self.request("POST", "/api/login", {"username": "TestStudent", "password": "wrongpassword"})
        self.assertEqual(status, 401)

    def test_04_unauthenticated_rejected(self):
        status, body, _ = self.request("GET", "/api/sessions")
        self.assertEqual(status, 401)

        status, body, _ = self.request("POST", "/api/sessions", {"title": "Test"})
        self.assertEqual(status, 401)

    def test_05_create_session_validation_and_success(self):
        _, _, cookie = self.request("POST", "/api/login", {"username": "TestStudent", "password": "validpassword123"})

        # Invalid subject
        future_day = (server.campus_now().date() + timedelta(days=2)).isoformat()
        status, body, _ = self.request("POST", "/api/sessions", {
            "title": "Quantum Physics",
            "subject": "Astronomy Not Listed",
            "date": future_day,
            "time": "14:00",
            "location": "Lab 1",
            "capacity": 4
        }, cookie=cookie)
        self.assertEqual(status, 400)

        # Past date
        past_day = (server.campus_now().date() - timedelta(days=2)).isoformat()
        status, body, _ = self.request("POST", "/api/sessions", {
            "title": "Past Session",
            "subject": "Physics",
            "date": past_day,
            "time": "14:00",
            "location": "Lab 1",
            "capacity": 4
        }, cookie=cookie)
        self.assertEqual(status, 400)

        # Capacity out of bounds
        status, body, _ = self.request("POST", "/api/sessions", {
            "title": "Big Group",
            "subject": "Physics",
            "date": future_day,
            "time": "14:00",
            "location": "Lab 1",
            "capacity": 20
        }, cookie=cookie)
        self.assertEqual(status, 400)

        # Valid creation
        status, body, _ = self.request("POST", "/api/sessions", {
            "title": "Quantum Mechanics Deep Dive",
            "subject": "Physics",
            "date": future_day,
            "time": "14:00",
            "location": "Room 302",
            "description": "Solving problem sheet 4.",
            "capacity": 3
        }, cookie=cookie)
        self.assertEqual(status, 201)
        created_id = body.get("id")
        self.assertIsNotNone(created_id)

        # Duplicate session hosting at the exact same time
        status, body, _ = self.request("POST", "/api/sessions", {
            "title": "Conflicting Host Session",
            "subject": "Physics",
            "date": future_day,
            "time": "14:00",
            "location": "Elsewhere",
            "capacity": 4
        }, cookie=cookie)
        self.assertEqual(status, 409)

        # Host cannot leave their own session
        status, body, _ = self.request("POST", f"/api/sessions/{created_id}/leave", {}, cookie=cookie)
        self.assertEqual(status, 400)
        self.assertIn("Cancel the session", body.get("error", ""))

    def test_06_join_leave_and_capacity_concurrency(self):
        # Register student A, B, C
        _, _, cookie_a = self.request("POST", "/api/register", {"username": "StudentA", "password": "password123"})
        _, _, cookie_b = self.request("POST", "/api/register", {"username": "StudentB", "password": "password123"})
        _, _, cookie_c = self.request("POST", "/api/register", {"username": "StudentC", "password": "password123"})

        future_day = (server.campus_now().date() + timedelta(days=5)).isoformat()
        # StudentA hosts a session with capacity 2 (StudentA is host + 1 open seat)
        status, body, _ = self.request("POST", "/api/sessions", {
            "title": "Pair Coding Algorithms",
            "subject": "Computer Science",
            "date": future_day,
            "time": "16:00",
            "location": "Lab 204",
            "capacity": 2
        }, cookie=cookie_a)
        self.assertEqual(status, 201)
        sid = body["id"]

        # StudentB joins (fills the 2nd seat)
        status, body, _ = self.request("POST", f"/api/sessions/{sid}/join", {}, cookie=cookie_b)
        self.assertEqual(status, 200)

        # StudentB tries to join again -> 409 already has a seat
        status, body, _ = self.request("POST", f"/api/sessions/{sid}/join", {}, cookie=cookie_b)
        self.assertEqual(status, 409)

        # StudentC tries to join -> circle is full (capacity 2 reached)
        status, body, _ = self.request("POST", f"/api/sessions/{sid}/join", {}, cookie=cookie_c)
        self.assertEqual(status, 409)
        self.assertIn("full", body.get("error", "").lower())

        # StudentB leaves -> seat becomes available
        status, body, _ = self.request("POST", f"/api/sessions/{sid}/leave", {}, cookie=cookie_b)
        self.assertEqual(status, 200)

        # StudentC can now join!
        status, body, _ = self.request("POST", f"/api/sessions/{sid}/join", {}, cookie=cookie_c)
        self.assertEqual(status, 200)

    def test_07_schedule_conflict_prevention(self):
        _, _, cookie_x = self.request("POST", "/api/register", {"username": "StudentX", "password": "password123"})
        _, _, cookie_y = self.request("POST", "/api/register", {"username": "StudentY", "password": "password123"})
        future_day = (server.campus_now().date() + timedelta(days=6)).isoformat()

        # Session 1 at 11:00
        status, b1, _ = self.request("POST", "/api/sessions", {
            "title": "Calculus Workshop",
            "subject": "Mathematics",
            "date": future_day,
            "time": "11:00",
            "location": "Hall A",
            "capacity": 4
        }, cookie=cookie_x)
        sid1 = b1["id"]

        # Session 2 at 11:00 hosted by StudentY
        status, b2, _ = self.request("POST", "/api/sessions", {
            "title": "Economics Forum",
            "subject": "Economics",
            "date": future_day,
            "time": "11:00",
            "location": "Hall B",
            "capacity": 4
        }, cookie=cookie_y)
        sid2 = b2["id"]

        # Register StudentZ and join Session 1
        _, _, cookie_z = self.request("POST", "/api/register", {"username": "StudentZ", "password": "password123"})
        status, _, _ = self.request("POST", f"/api/sessions/{sid1}/join", {}, cookie=cookie_z)
        self.assertEqual(status, 200)

        # StudentZ tries to join Session 2 at the exact same date & time -> 409 Schedule conflict
        status, body, _ = self.request("POST", f"/api/sessions/{sid2}/join", {}, cookie=cookie_z)
        self.assertEqual(status, 409)
        self.assertIn("conflict", body.get("error", "").lower())

    def test_08_cancel_session_authorization(self):
        _, _, cookie_host = self.request("POST", "/api/register", {"username": "HostPerson", "password": "password123"})
        _, _, cookie_other = self.request("POST", "/api/register", {"username": "OtherPerson", "password": "password123"})

        future_day = (server.campus_now().date() + timedelta(days=7)).isoformat()
        status, b, _ = self.request("POST", "/api/sessions", {
            "title": "Design Sprint",
            "subject": "Design",
            "date": future_day,
            "time": "15:00",
            "location": "Studio",
            "capacity": 3
        }, cookie=cookie_host)
        sid = b["id"]

        # Non-host cannot cancel -> 403 Forbidden
        status, body, _ = self.request("DELETE", f"/api/sessions/{sid}", cookie=cookie_other)
        self.assertEqual(status, 403)

        # Host cancels -> 200 OK
        status, body, _ = self.request("DELETE", f"/api/sessions/{sid}", cookie=cookie_host)
        self.assertEqual(status, 200)

        # Now session does not exist -> 404
        status, body, _ = self.request("DELETE", f"/api/sessions/{sid}", cookie=cookie_host)
        self.assertEqual(status, 404)

    def test_09_logout_invalidates_session(self):
        status, _, cookie = self.request("POST", "/api/login", {"username": "Maya", "password": "password123"})
        self.assertEqual(status, 200)

        # Logout
        status, _, logout_cookie = self.request("POST", "/api/logout", {}, cookie=cookie)
        self.assertEqual(status, 200)

        # Requesting /api/me with old cookie -> user is None
        status, body, _ = self.request("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIsNone(body.get("user"))


if __name__ == "__main__":
    unittest.main()
