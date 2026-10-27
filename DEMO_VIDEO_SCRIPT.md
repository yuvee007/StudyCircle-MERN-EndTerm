# StudyCircle — 3–5 Minute Demo Video Walkthrough Script

Use this script to record your final project demonstration video. Keep the demo between 3 to 5 minutes, speak clearly, and show the application working in the browser.

---

## Video Outline (Target Duration: ~3:30)

| Timestamp | Section | Visual on Screen | Key Points to Cover |
|---|---|---|---|
| **0:00 - 0:35** | **1. Problem & Product Overview** | App Sign-in Page | • University student coordination problem<br>• Fragmentation in chat groups, full rooms<br>• StudyCircle: small, focused circles with seat guarantees |
| **0:35 - 1:15** | **2. Evaluator Demo Login & Discovery** | Auth page & 1-click login into Discover View | • Security: PBKDF2 hashing & HttpOnly cookies<br>• Show 1-click demo login as **Maya** (Host)<br>• Hero statistics (happening today, open seats)<br>• Live search & subject filters & open-seats toggle |
| **1:15 - 2:00** | **3. Circle Inspection & Seat Reservation** | Session Card & Details Modal | • Click session card to open **Session Details Modal**<br>• Show study agenda, location, and confirmed member avatars<br>• Click **Share Circle** (copies invite to clipboard)<br>• Click **Join circle →** on an open session<br>• Show reactive seat count decrement & audio chime |
| **2:00 - 2:45** | **4. Hosting a Circle & Conflict Prevention** | My Sessions View & Create Modal | • Open **My sessions** (show Upcoming, Hosting, Past tabs)<br>• Click **＋ Create session**<br>• Fill in details (subject, group size 2-8, location, notes)<br>• Submit and show live update in calendar<br>• Explain backend validation: future time enforcement, capacity caps, host schedule conflict prevention |
| **2:45 - 3:15** | **5. Concurrency, Ownership & Cancellation** | Host view & Cancel flow | • Show that only the Host has the **Cancel circle** button<br>• Explain SQLite `BEGIN IMMEDIATE` atomic concurrency (prevents overbooking)<br>• Cancel a hosted session; show cascading attendee deletion<br>• Demonstrate profile popover and sign out |
| **3:15 - 3:35** | **6. Architecture, Automated Tests & Wrap-Up** | Terminal with `test_server.py` | • Zero runtime dependency Python 3 + SQLite architecture<br>• Show automated test suite passing (`python -m unittest test_server.py -v`)<br>• Conclude |

---

## Word-for-Word Narration Script

### [0:00 - 0:35] 1. Problem & Product Overview
> *"Hello evaluators. This is StudyCircle, an application designed to solve one of the biggest everyday challenges for university students: finding study partners, staying focused, and reserving collaborative study spaces on campus.*  
> *Often, students want to work together on tough subjects like Algorithms or Linear Algebra, but coordination on chat groups is chaotic. Groups end up either with zero attendees or overcrowded rooms where no real studying happens.*  
> *StudyCircle solves this by organizing small, bounded study circles of 2 to 8 students with guaranteed seat caps, verified agendas, and real-time scheduling conflict prevention."*

---

### [0:35 - 1:15] 2. Evaluator Demo Login & Discovery
> *(On screen: Auth page at http://localhost:8000)*  
> *"Under the hood, StudyCircle uses standard PBKDF2-HMAC-SHA256 password hashing with per-user 16-byte random salts and secure HttpOnly session cookies.*  
> *To make evaluation seamless, we built a 1-click demo switcher. I'll click **Maya**, who is pre-seeded as a Computer Science host.*  
> *(Click Maya -> Enter Discover page)*  
> *We are now in the Discover dashboard. At a glance, students see live campus statistics: sessions happening today, open seats, and active study groups.*  
> *Below that is our responsive filter bar. We can search in real-time across titles, subjects, locations, or hosts, filter by specific academic disciplines, or toggle 'Open seats only' to immediately eliminate full circles."*

---

### [1:15 - 2:00] 3. Circle Inspection & Seat Reservation
> *(Click on a session card)*  
> *"Let's click on this session card. This opens our **Session Details Modal**.*  
> *Here students see the exact study agenda, campus building location, circle size, and confirmed attendees with their initials and host badges.*  
> *Students can also click **Share Circle** to copy a pre-formatted invite link and summary to their clipboard to share with classmates.*  
> *(Close modal, then click 'Join circle' on Linear Algebra)*  
> *Now, let's join an open session. When I click **Join circle**, the server performs an atomic transaction to reserve my seat, prevents any duplicate reservations, and validates that I don't have an existing session at that exact time. Notice the button instantly updates to 'Joined', and the available seats count decrements in real-time."*

---

### [2:00 - 2:45] 4. Hosting a Circle & Conflict Prevention
> *(Click 'My sessions' in the sidebar)*  
> *"Navigating to **My sessions**, students have a personalized calendar categorized into Upcoming, Hosting, and Past completed sessions.*  
> *Now let's host a new study circle.*  
> *(Click '+ Create session')*  
> *Our creation modal enforces strict validation: session titles, recognized subjects, group capacities between 2 and 8, and mandatory future start times.*  
> *Let's name this 'Systems & Compilers Review', set the subject to Computer Science, capacity to 4, and location to 'Tech Hub Room 204'.*  
> *(Click Create session)*  
> *As soon as we create it, the circle goes live across campus, the host is automatically enrolled, and it appears in our hosting calendar."*

---

### [2:45 - 3:15] 5. Concurrency, Ownership & Cancellation
> *"Security and role-based authorization are strictly enforced. As the host, Maya has the authorization to cancel her session.*  
> *Non-hosts cannot cancel sessions, and hosts cannot orphan their circle by simply leaving—they must cancel, which triggers a clean SQLite cascading deletion for all reserved attendees.*  
> *(Click Cancel session -> Confirm)*  
> *The session is removed cleanly from everyone's calendar.*  
> *We also have a quick profile popover at the top-right showing our active circle count and 1-click Sign Out."*

---

### [3:15 - 3:35] 6. Automated Testing & Conclusion
> *(Switch to terminal window)*  
> *"Finally, StudyCircle includes a comprehensive automated test suite testing authentication, concurrency limits, scheduling conflicts, and session lifecycles.*  
> *(Run: `python -m unittest test_server.py -v`)*  
> *All 9 integration tests pass in under 5 seconds with zero external dependencies.*  
> *Thank you for your time, and we hope you enjoy exploring StudyCircle!"*
