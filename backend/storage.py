"""
File storage  (Unit IV: File handling, JSON, CSV, exceptions)

All app data lives in the data/ folder as JSON files - this is SERIALIZATION:
Python lists/dicts  --json.dump-->  text file  --json.load-->  Python lists/dicts
"""
import csv
import json
import os
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def path(name):
    return os.path.join(DATA_DIR, name)


def load_json(name, default):
    """Read a JSON file. If it is missing or damaged, return the default instead of crashing."""
    try:
        with open(path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        # file is corrupted -> keep a copy for inspection and start fresh
        os.replace(path(name), path(name + ".broken"))
        return default


def save_json(name, data):
    """
    Write safely: first to a temporary file, then rename it over the real one.
    If the program crashes mid-write, the old file is still intact
    (remember: opening with "w" erases the file immediately!).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path(name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path(name))


def append_csv(name, fieldnames, row):
    """Append one row to a CSV file, writing the header the first time."""
    new_file = not os.path.exists(path(name))
    with open(path(name), "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def read_csv(name):
    try:
        with open(path(name), newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------------------
# Demo data: created automatically the first time the app runs
# ---------------------------------------------------------------------------
DEMO_PASSWORD = "Demo@1234"

DEMO_USERS = [
    ("Demo Player", "demo@playpulse.in", "9876543210", "Intermediate", "badminton"),
    ("Riya Sharma", "riya@playpulse.in", "9811122233", "Advanced", "badminton"),
    ("Arjun Mehta", "arjun@playpulse.in", "9822233344", "Intermediate", "football"),
    ("Kabir Singh", "kabir@playpulse.in", "9833344455", "Beginner", "cricket"),
    ("Neha Gupta", "neha@playpulse.in", "9844455566", "Intermediate", "tennis"),
    ("Ishaan Rao", "ishaan@playpulse.in", "9855566677", "Advanced", "basketball"),
]


def ensure_data():
    """Create users/bookings/games JSON files with demo data if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(path("users.json")):
        return
    venues = load_json("venues.json", [])
    rng = random.Random(42)                       # fixed seed -> same demo data every time

    users = [{"name": n, "email": e, "phone": p, "skill": s, "favourite_sport": f,
              "password_hash": generate_password_hash(DEMO_PASSWORD),
              "joined": (date.today() - timedelta(days=rng.randint(10, 90))).isoformat()}
             for n, e, p, s, f in DEMO_USERS]

    bookings, used = [], {}                       # used[(venue, sport, date, hour)] = courts taken
    emails = [u["email"] for u in users]

    def try_book(venue, sport, d, hour, email, game_id=None):
        key = (venue["id"], sport, d.isoformat(), hour)
        if used.get(key, 0) >= venue["sports"][sport]["courts"]:
            return None
        used[key] = used.get(key, 0) + 1
        price = venue["sports"][sport]["weekend" if d.weekday() >= 5 else "weekday"]
        b = {"id": f"PP{len(bookings) + 1:05d}", "user_email": email, "venue_id": venue["id"],
             "sport": sport, "date": d.isoformat(), "hour": hour, "duration": 1, "amount": price,
             "status": "confirmed", "created_at": datetime.now().isoformat(timespec="seconds"),
             "game_id": game_id}
        bookings.append(b)
        return b

    # past 28 days of bookings (gives the Insights charts something to show)
    for days_ago in range(28, 0, -1):
        d = date.today() - timedelta(days=days_ago)
        for _ in range(rng.randint(4, 9)):
            v = rng.choice(venues)
            sport = rng.choice(list(v["sports"]))
            hour = rng.choice([6, 7, 8, 17, 18, 19, 20, 21, rng.randint(v["opens"], v["closes"] - 1)])
            if v["opens"] <= hour < v["closes"]:
                b = try_book(v, sport, d, hour, rng.choice(emails))
                if b and rng.random() < 0.08:
                    b["status"] = "cancelled"

    # some upcoming bookings so slot grids show "booked" slots
    for days_ahead in range(0, 5):
        d = date.today() + timedelta(days=days_ahead)
        for _ in range(rng.randint(5, 9)):
            v = rng.choice(venues)
            sport = rng.choice(list(v["sports"]))
            hour = rng.choice([18, 19, 20, 21])
            if v["opens"] <= hour < v["closes"]:
                try_book(v, sport, d, hour, rng.choice(emails[1:]))

    # open games (Match Finder) over the next few days
    game_plans = [
        ("riya@playpulse.in", "badminton", 1, 19, "Advanced", 4, "Doubles, bring your own racket. Feathers provided."),
        ("arjun@playpulse.in", "football", 1, 20, "Intermediate", 10, "5-a-side friendly. Wear studs/turf shoes."),
        ("kabir@playpulse.in", "cricket", 2, 18, "Beginner", 8, "Tennis-ball box cricket, everyone bats & bowls."),
        ("neha@playpulse.in", "tennis", 2, 7, "Intermediate", 2, "Morning singles rally, 1 hour."),
        ("ishaan@playpulse.in", "basketball", 3, 19, "Advanced", 6, "3v3 half court, competitive."),
        ("riya@playpulse.in", "pickleball", 3, 18, "Beginner", 4, "New to pickleball? Come learn, paddles available."),
    ]
    games = []
    names = {u["email"]: u["name"] for u in users}
    for host, sport, ahead, hour, skill, spots, notes in game_plans:
        venue = next((v for v in venues if sport in v["sports"] and v["opens"] <= hour < v["closes"]), None)
        if not venue:
            continue
        d = date.today() + timedelta(days=ahead)
        gid = f"G{len(games) + 1:04d}"
        b = try_book(venue, sport, d, hour, host, game_id=gid)
        if not b:
            continue
        players = [{"email": host, "name": names[host]}]
        for e in rng.sample([x for x in emails if x not in (host, "demo@playpulse.in")],
                            k=min(spots - 2, rng.randint(1, 3))):
            players.append({"email": e, "name": names[e]})
        price = venue["sports"][sport]["weekend" if d.weekday() >= 5 else "weekday"]
        games.append({"id": gid, "host_email": host, "sport": sport, "venue_id": venue["id"],
                      "date": d.isoformat(), "hour": hour, "skill": skill, "total_spots": spots,
                      "cost_per_head": round(price / spots), "notes": notes, "players": players,
                      "booking_id": b["id"], "status": "open"})

    save_json("users.json", users)
    save_json("bookings.json", bookings)
    save_json("games.json", games)
