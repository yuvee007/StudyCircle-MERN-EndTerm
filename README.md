# StudyCircle

> **Find your people. Finish your work.**  
> A lightweight, collaborative campus study circle discovery and reservation platform built for university students.

> **Demo Video Link: https://drive.google.com/file/d/1HUYawlkK9n7BPySoPxukicR83LyiwQYy/view?usp=sharing**  


[![Tests: Passing](https://img.shields.io/badge/tests-9%20passed-success)](test_server.py)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](server.py)
[![Zero Runtime Dependencies](https://img.shields.io/badge/dependencies-0%20runtime-brightgreen)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/license-MIT-informational)](LICENSE)

---

## 1. Problem Statement

University students frequently struggle with isolated, inefficient studying. While students know that studying together increases accountability, focus, and retention, coordinating small-group study sessions on campus is broken:
- **Discovery Friction**: Students don't know who else is studying the same subject, preparing for the same quiz, or tackling the same problem set right now.
- **Coordination Breakdown**: Chat groups and forum posts quickly get buried, timeslots conflict, and students show up only to find study rooms overcrowded or full.
- **Unreliable Group Sizing**: Effective study groups must remain small (2–6 students) to maintain focus; open invites inevitably lead either to zero attendees or distracting crowds.

StudyCircle solves this by providing a unified campus coordination platform where students can discover focused study circles by subject and time, inspect verified agendas and member lists, reserve limited seats with strict capacity guarantees, and host their own study sprints without double-booking.

---

## 2. Target Users

- **Undergraduate & Graduate University Students** preparing for midterms, finals, coding problem sets, or design critiques.
- **Student Study Hosts & Peer Mentors** organizing focused, small-group review sessions.
- **Campus Study Groups & Working Pairs** needing small, bounded circles with guaranteed seat caps.

---

## 3. Product Solution & Key Workflows

StudyCircle is a complete, full-stack web application designed around 5 essential engineering workflows:

### Workflow 1: Authentication & Evaluator-Friendly Identity Switcher
- **Secure Credentials**: Passwords hashed using standard `PBKDF2-HMAC-SHA256` with 310,000 iterations and per-user 16-byte cryptographically random salts (`secrets.token_bytes`).
- **Session Protection**: Random 32-byte opaque tokens; server stores only the SHA-256 token digest. Delivered via `HttpOnly`, `SameSite=Lax` cookies with auto-detecting `Secure` flag.
- **1-Click Evaluator Demo Logins**: Dedicated demo login buttons on the sign-in screen allow evaluators to instantly test pre-seeded roles:
  - **Maya**: Host of Computer Science circle
  - **Ishaan**: Host of Mathematics circle
  - **Aarav**: Member of Physics circle
  - **+ Guest**: Instant random student account generation

### Workflow 2: Study Circle Discovery & Multi-Facet Filtering
- **Live Search**: Instant client-side search across session title, subject, campus location, host name, and study agenda.
- **Subject Filtering**: Filter across 8 academic subjects (Computer Science, Mathematics, Physics, Economics, Design, Biology, Chemistry, Other).
- **Time Horizon Filtering**: Filter by *Any time*, *Today*, or *Upcoming*.
- **Open Seats Filter**: 1-click toggle to filter out full circles and see only sessions with free capacity.
- **Multi-Mode Sorting**: Sort circles by *Soonest first*, *Latest first*, or *Most seats available*.

### Workflow 3: Atomic Seat Reservation & Concurrency Management
- **Atomic Transactions**: Seat reservations use `BEGIN IMMEDIATE` database transactions in SQLite to eliminate race conditions and prevent overbooking under concurrent requests.
- **Time-Conflict Guard**: Prevents a student from joining two overlapping study circles scheduled for the exact same date and time.
- **Anti-Double-Booking**: Prevents duplicate reservations by the same student.
- **Past-Session Protection**: Server blocks reservation attempts on sessions whose start time has already passed.
- **Dynamic Capacity UI**: Real-time progress bars and capacity badges showing filled vs. open seats.

### Workflow 4: Session Lifecycle & Conflict-Protected Hosting
- **Server-Side Validation**: Enforces mandatory fields, listed subjects, capacity limits (2–8 students), and future start times based on campus timezone offset.
- **Host Schedule Conflict Detection**: Prevents a host from creating two overlapping sessions at the same date and time.
- **Ownership Authorization**: Only the verified host of a session can cancel it (`DELETE /api/sessions/:id`).
- **Host Role Integrity**: Hosts cannot leave their own session without cancelling, ensuring circles are never orphaned.
- **Cascading Deletion**: Cancelling a session cleanly removes all attendee reservations via SQLite `ON DELETE CASCADE`.

### Workflow 5: Real-Time Live Campus Sync & Circle Sharing
- **Live Sync Polling**: Background synchronization fetches updates every 12 seconds so concurrent bookings across different students or browser windows appear live without page reloads.
- **Circle Details Modal**: Complete session view showing study agenda, campus room directions, confirmed member chips with role badges (Host / You), and 1-click clipboard invite generator.
- **Web Audio Micro-interactions**: Zero-dependency audio chime feedback for successful joins, creates, and leaves.

---

## 4. Technical Architecture

StudyCircle is deliberately engineered to be **dependency-free**, lightweight, and robust:

```text
[ Browser Client (HTML5 / Vanilla CSS / ES6+ JS / Web Audio) ]
                              │
                    HTTP REST API (JSON)
                    Session Cookie (HttpOnly)
                              │
                              ▼
          [ Python 3 ThreadingHTTPServer (server.py) ]
          ├── Request Router & Security Filter (Origin, CSP, Framing)
          ├── PBKDF2-HMAC-SHA256 Password Hashing & Token Verification
          ├── Business Logic & Validation (Timezones, Overlaps, Host Guards)
          └── Transactional Data Access Layer
                              │
                         SQLite 3
                 (data/studycircle.sqlite3)
          ├── users (id, username, password_hash, created_at)
          ├── sessions (id, title, subject, date, time, location, ...)
          ├── attendees (session_id, username) [FK CASCADE]
          ├── login_sessions (token_hash, username, expires_at)
          └── app_meta (key, value)
```

### Architecture Highlights
- **No Third-Party Runtime Dependencies**: Runs entirely on Python 3 standard library (`http.server`, `sqlite3`, `hashlib`, `hmac`, `secrets`). No heavy frameworks or vulnerable node/pip dependencies.
- **ACID Database Guarantees**: SQLite configured with `PRAGMA foreign_keys = ON` and explicit `BEGIN IMMEDIATE` transaction boundaries on seat updates.
- **Security Headers**: Responses include `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, and `Cache-Control: no-store` on all API endpoints.

---

## 5. Technology Stack

| Layer | Technology | Engineering Rationale |
|---|---|---|
| **Frontend Structure** | Semantic HTML5 | Accessible, SEO-friendly, clean DOM hierarchy |
| **Styling & Design** | Vanilla CSS3 (Custom Design System) | Modern CSS variables, responsive grid, glassmorphism, micro-animations, zero Tailwind dependency bloat |
| **Frontend Logic** | Vanilla ES6+ JavaScript | Fast, zero bundle overhead, reactive state rendering, Web Audio API synthesis |
| **Backend Server** | Python 3.10+ `ThreadingHTTPServer` | Multi-threaded HTTP server handling concurrent requests with standard library simplicity |
| **Persistence** | SQLite3 | Embedded ACID database with foreign keys, compound indexes, and atomic locking |
| **Authentication** | PBKDF2-HMAC-SHA256 & Opaque Tokens | NIST-compliant password security (310,000 rounds) and HttpOnly token digests |
| **Testing** | Python `unittest` | Automated end-to-end integration test suite covering auth, concurrency, conflict checks, and lifecycle |
| **Containerization** | Docker (`python:3.12-slim`) | Self-contained, portable container ready for local or cloud deployment |

---

## 6. Local Setup & Quick Start

### Prerequisites
- Python 3.10 or newer (verify with `python --version` or `py --version`)
- Modern web browser (Chrome, Edge, Firefox, Safari)

### Run in 3 Steps
1. Open a terminal in this project directory:
   ```bash
   cd "Study Circle - End Term Project"
   ```
2. Start the StudyCircle server:
   ```bash
   python server.py
   ```
   *(Windows users can also use `py server.py`)*
3. Open your browser and navigate to:
   ```text
   http://localhost:8000
   ```
   - On the login screen, click **Maya** or **Ishaan** to log in instantly with 1 click, or click **Create account** to sign up.

---

## 7. Running Automated Tests

StudyCircle includes a full automated test suite verifying every endpoint, validation rule, concurrency boundary, and security check:

```bash
python -m unittest test_server.py -v
```

### Verified Test Cases:
1. `test_01_seed_data_and_demo_users_exist`: Seed data and demo user authentication
2. `test_02_register_validation`: Username constraints, password length, and duplicate rejection
3. `test_03_register_and_login_flow`: Successful registration, subsequent login, and wrong password rejection
4. `test_04_unauthenticated_rejected`: 401 Unauthorized protection on protected endpoints
5. `test_05_create_session_validation_and_success`: Subject validation, future date/time enforcement, capacity bounds (2–8), duplicate host time slots, and host leave guards
6. `test_06_join_leave_and_capacity_concurrency`: Atomic seat booking, duplicate join prevention, overbooking capacity limits, and seat freeing on leave
7. `test_07_schedule_conflict_prevention`: Prevents students from joining two conflicting circles at the same date and time
8. `test_08_cancel_session_authorization`: Host cancellation allowed (200), non-host rejected (403), cascading attendee deletion
9. `test_09_logout_invalidates_session`: Session token destruction upon logout

---

## 8. Configuration & Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port for the HTTP server to bind to |
| `STUDYCIRCLE_DATA` | `./data` | Directory where `studycircle.sqlite3` database is persisted |
| `CAMPUS_UTC_OFFSET_MINUTES` | `330` | Timezone offset in minutes (+05:30 IST). Controls future-time calculations and sample dates |
| `COOKIE_SECURE` | Auto-detected | `1` forces the `Secure` cookie flag; `0` disables it. By default, auto-detects `X-Forwarded-Proto: https` |

---

## 9. Docker Deployment

To build and run with Docker:

```bash
# Build the container image
docker build -t studycircle .

# Run container with a persistent data volume
docker run --rm -p 8000:8000 -v studycircle-data:/data studycircle
```

Access the app at `http://localhost:8000`.

---

## 10. Submission Information (For Official Submission Form)

```text
Project Name:
StudyCircle

Student Name:
[Enter Your Full Name Here]

Problem Statement:
University students struggle to find peers studying the same subject at the same time and place, leading to isolated studying, coordination chaos in chat groups, and overcrowded study spaces. StudyCircle provides a focused campus platform where students discover academic circles, reserve capacity-capped seats, and host study sprints without scheduling conflicts.

GitHub Repository:
[Your GitHub Repository URL]

Deployed Application / Build:
http://localhost:8000  (or your deployed cloud URL)

Demo Video:
[Your 3-5 Minute Demo Video URL]

Tech Stack:
Python 3 (ThreadingHTTPServer, SQLite3, hashlib PBKDF2), Semantic HTML5, Vanilla CSS3 (Custom Design System), Vanilla ES6+ JavaScript, Web Audio API, Docker.

Major Features:
1. Secure Authentication & Evaluator 1-Click Demo Login (PBKDF2-HMAC-SHA256, HttpOnly session cookies)
2. Live Study Circle Discovery with Real-time Search, Multi-subject Filtering, and Open-Seats Toggle
3. Atomic Capacity & Concurrency Management (Transactions prevent overbooking; schedule conflict detection)
4. Session Details Modal with Focus Agendas, Confirmed Attendee Badges, and Clipboard Invite Generator
5. Host Management with Protected Lifecycle (Host cancellation, cascade deletion, host-leave guards)
6. Real-time Live Campus Sync & Browser State Persistence
```
