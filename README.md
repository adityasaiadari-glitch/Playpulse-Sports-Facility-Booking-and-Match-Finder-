# 🏸 PlayPulse: Sports Facility Booking & Match Finder

**CP Lab Mini Project** · Python + Flask

PlayPulse lets players **book sports venues** (badminton courts, football turfs, cricket boxes, pools…) and **find or host open matches** with players at their skill level.

---

## 1. Run it in 3 steps

```bash
pip install -r requirements.txt     # Flask, numpy, pandas, matplotlib
python app.py                       # starts the server
```
Open **http://127.0.0.1:5000** in your browser.

**Demo login:** `demo@playpulse.in` / `Demo@1234`
(other demo users: riya@, arjun@, kabir@, neha@, ishaan@ … all `@playpulse.in`, same password)

On the first run the app creates demo users, ~190 bookings and 6 open games in `data/`.
**To reset everything**, delete `data/users.json`, `data/bookings.json`, `data/games.json` (keep `venues.json!`) and restart.

**Run the automated tests:** `python test_app.py` (18 tests, uses a temporary copy of the data).

---

## 2. Features

| Feature | Where |
|---|---|
| Home page: hero, live "games looking for players" board, search, sport tiles, top picks, nearest venues | `/` |
| Choose your area → every venue shows its distance from you | 📍 selector in the top bar |
| Browse venues with filters (sport, search) and sorting (recommended / nearest / rating / price) | `/venues` |
| Venue page: rating, quick facts, price chart per sport, amenities, map, reviews, open games | `/venues/<id>` |
| Book a slot: choose sport → date → time from a live slot grid (free / last court / booked / passed) | `/venues/<id>/book` |
| Booking ticket + WhatsApp share | `/bookings/<id>` |
| My bookings: upcoming / past, cancel (free until 2 h before), **download as CSV** | `/my-bookings` |
| **Match Finder**: filter open games, recommended games for your level, join / leave | `/games`, `/games/<id>` |
| Host a game: books the court and lists the game, cost split per player | `/games/new` |
| Rate a venue (1–5 stars + review) | venue page |
| Group / corporate enquiry → saved in `data/enquiries.csv` | `/venues/<id>/group-booking` |
| Sign up with validated name, phone and **password rules**; log in / log out | `/signup`, `/login` |
| **Insights**: KPIs + 4 charts made with NumPy, pandas, Matplotlib | `/insights` |
| **REST API** (JSON) with GET / POST / DELETE + API docs page | `/api`, `/developers` |

---

## 3. How it meets the lab evaluation (Class Test 2)

| Stage | What to show |
|---|---|
| **a. Backend in Python** | The `backend/` package: classes in `models.py`, rules in `services.py` (availability check, double-booking prevention, cancellation window, game full checks), JSON storage, regex validation, custom exceptions. |
| **b. Flask app with routes & HTTP methods; deploy API** | `app.py`: page routes (GET) + API routes under `/api` using **GET, POST and DELETE**, returning JSON with proper status codes (200, 201, 400, 401, 403, 404, 409). Deployment steps are in section 7. |
| **c. Frontend integrated through the API** | Every HTML form posts **directly to an `/api/...` route**. Each API route answers JSON clients with JSON, and browser forms with a redirect + message (see `respond()` and `wants_json()` in `app.py`). So the website and Postman/curl use the **same API**. |
| **d. Discussion** | Use the syllabus map (section 4) and viva questions (section 8). |

### Request flow (draw this in the viva)
```
Browser form ──POST /api/bookings──► app.py route ──► services.create_booking()
                                                        │  validate date (datetime)
                                                        │  check courts free
                                                        │  raise SlotUnavailableError if not
                                                        ▼
                                                  data/bookings.json  (json.dump)
Browser ◄── 302 redirect to /bookings/PP00042 (ticket page)
Postman ◄── 201 Created  {"id": "PP00042", ...}   (same route, JSON client)
```

---

## 4. Syllabus map (every unit is used)

| Unit | Concept | Where in the code |
|---|---|---|
| **I** | Variables, operators, if/elif/else, loops, functions, default & keyword args | everywhere, e.g. `services.slot_grid()` |
| | Lists, tuples, dictionaries, sets | `SPORTS` dict, `AREAS` dict of tuples, set in `site_stats()` |
| | Arbitrary arguments `*args, **kwargs` | `login_required` wrapper in `app.py` |
| **II** | Classes, objects, `__init__`, `self` | `backend/models.py` |
| | Inheritance + `super()` + method overriding | `Venue(Facility)`, `Venue.summary()` |
| | Encapsulation | `User._password_hash`, never sent out (`public_dict()`) |
| | Polymorphism, `@property`, `@classmethod` | `to_dict()` in every class, `venue.rating`, `User.create()` |
| | Operator overloading | `Booking.__lt__`, `Game.__lt__` (lets `sorted()` work), `Game.__len__` |
| | Generator (`yield`) | `slots.hour_slots()` |
| | Lambda, `map()`, `filter()`, `sorted(key=)` | `services.search_venues()`, `distance_km()`, `recommended_games()` |
| | **Decorator** | `@login_required` in `app.py` |
| | Modules & packages (`__init__.py`) | the `backend/` package |
| **III** | NumPy | `analytics.py`: `np.sum`, `np.mean`, `np.where` |
| | Strings | formatting labels, `split()`, `title()`, f-strings |
| | **Regular expressions** | `validators.py`: name, email, phone, password (lookaheads), date |
| | **Dates & times** | `slots.py`: `strptime`, `strftime`, `timedelta`, weekday pricing, 2-hour cancel rule |
| | pandas Series/DataFrame, filtering, **groupby + aggregation** | `analytics.py`: bookings per sport, revenue per venue, weekday vs weekend |
| **IV** | File handling (`with open`, modes) | `storage.py` (safe write: temp file + `os.replace`) |
| | **JSON** serialization / deserialization | `load_json()` / `save_json()` |
| | **CSV** read / write | `enquiries.csv` (`DictWriter`), "Download bookings" CSV |
| | try / except / finally, specific exceptions | `parse_date()`, `load_json()` (FileNotFoundError, JSONDecodeError) |
| | **Custom exceptions + raise** | `exceptions.py`: 7 classes with HTTP status codes; one handler in `app.py` |
| **V** | Flask app, routes, dynamic routes `<int:venue_id>` | `app.py` |
| | HTTP methods GET / POST / DELETE | `/api/bookings`, `/api/bookings/<id>` |
| | `request` (args, form, get_json, method) & responses (jsonify, redirect, status codes) | `app.py` |
| | Templates (Jinja2): `{{ }}`, `{% for %}`, `{% if %}`, inheritance, macros, filters | `templates/` |
| | HTML forms & input attributes (`pattern`, `required`, `min`, `max`, `type=date`…) | `signup.html`, `book.html`, `host_game.html` |
| | **Matplotlib** (bar, barh, line, pie) | `analytics.py` → shown on `/insights` |

---

## 5. Project structure

```
playpulse/
├── app.py               Flask app: page routes + /api routes + error handling
├── wsgi.py              entry point for hosting (PythonAnywhere)
├── requirements.txt
├── test_app.py          18 automated tests
├── backend/
│   ├── __init__.py      makes backend a package
│   ├── models.py        Facility, Venue, User, Booking, Game classes
│   ├── services.py      business rules (booking, games, auth, search)
│   ├── storage.py       JSON / CSV files + demo data
│   ├── validators.py    regex validation
│   ├── slots.py         dates, times, slot generator
│   ├── exceptions.py    custom exceptions
│   └── analytics.py     NumPy + pandas + Matplotlib
├── data/
│   └── venues.json      8 venues (other files are created automatically)
├── templates/           HTML pages (Jinja2)
└── static/
    ├── style.css        all styling
    └── charts/          generated chart images
```

---

## 6. Suggested split for 4 members

| Member | Owns | Explains in the viva |
|---|---|---|
| 1 | `models.py`, `exceptions.py`, `slots.py` | OOP, inheritance, custom exceptions, datetime, generator |
| 2 | `services.py`, `storage.py`, `validators.py` | booking rules, JSON/CSV, regex & password rules |
| 3 | `app.py` (routes + API) + `developers.html` | Flask routes, GET/POST/DELETE, status codes, decorator, API demo in Postman |
| 4 | `templates/`, `style.css`, `analytics.py` | HTML forms & attributes, Jinja, CSS, pandas groupby, Matplotlib charts |

---

## 7. Deploying the API (free) on PythonAnywhere

1. Create a free account at pythonanywhere.com.
2. **Files** tab → upload the project zip → open a **Bash console**:
   ```bash
   unzip playpulse.zip && cd playpulse
   pip install --user -r requirements.txt
   ```
3. **Web** tab → *Add a new web app* → *Manual configuration* → choose your Python version.
4. Set **Source code** to `/home/<username>/playpulse`.
5. Open the **WSGI configuration file** and replace its contents with:
   ```python
   import sys
   sys.path.insert(0, "/home/<username>/playpulse")
   from app import app as application
   ```
6. Under **Static files** add: URL `/static/` → Directory `/home/<username>/playpulse/static`.
7. Click **Reload**. Your site and API are live at `https://<username>.pythonanywhere.com` (try `/api`).
8. Before deploying, set a real secret key (any long random text) in the Web tab's environment or edit `app.secret_key`.

---

## 8. Likely viva questions (with short answers)

1. **How do you stop two people booking the same court?** `create_booking()` counts confirmed bookings for that venue/sport/date/hour and compares with the number of courts. If full, it raises `SlotUnavailableError` (HTTP 409).
2. **Why validate on the server if the HTML has `pattern`?** Anyone can bypass the browser (DevTools, curl). The browser check is for convenience; the server check (`validators.py`) is for security.
3. **How are passwords stored?** As a salted hash (`generate_password_hash` from Werkzeug, which comes with Flask), never as plain text. Login compares with `check_password_hash`.
4. **What's the difference between your page routes and API routes?** Page routes return HTML (`render_template`). API routes return JSON (`jsonify`) and status codes. HTML forms submit to the API routes.
5. **Why GET for search but POST for booking?** GET only reads data and can be bookmarked (filters show in the URL). POST changes data (creates a booking) and keeps form data out of the URL.
6. **What does `@login_required` do?** It's a decorator that runs before the route; if no user is in the session it raises `AuthError`, which becomes a redirect to the login page (or 401 JSON for API clients).
7. **Why one error handler instead of try/except in every route?** All our exceptions inherit from `PlayPulseError`, so `@app.errorhandler(PlayPulseError)` catches every child class in one place, the same idea as the exception hierarchy.
8. **Why save to a temp file then rename?** Opening a file in `"w"` mode erases it immediately. If the program crashed mid-write we would lose all bookings. Writing to a temp file and renaming makes the save all-or-nothing.
9. **What does pandas `groupby` do on the Insights page?** Groups bookings by sport (or venue) and aggregates with `count()` / `sum()` / `mean()`, the "split → apply → combine" pattern.
10. **How is distance calculated?** The haversine formula on latitude/longitude (`services.distance_km`), giving straight-line km.
11. **What is `__lt__` used for?** Operator overloading: defining `<` for Booking/Game lets `sorted()` order them by date and time.
12. **What happens when a host cancels the booking of a game?** `cancel_booking()` also marks the linked game as cancelled, because hosting a game is built on top of a booking.
