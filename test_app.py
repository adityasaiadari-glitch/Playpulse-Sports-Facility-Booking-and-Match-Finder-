"""
Automated tests for PlayPulse  ->  run:  python test_app.py

Uses Flask's built-in test client (a fake browser) and a TEMPORARY copy of the
data folder, so your real data/ files are never touched.
"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

from backend import storage

# point storage at a temporary folder BEFORE the app creates demo data
TMP = tempfile.mkdtemp()
shutil.copy(os.path.join(storage.DATA_DIR, "venues.json"), TMP)
storage.DATA_DIR = TMP

import app as webapp                                   # noqa: E402  (import after patching)
from backend import services, slots                    # noqa: E402

TOMORROW = (date.today() + timedelta(days=1)).isoformat()


class PlayPulseTests(unittest.TestCase):
    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.c = webapp.app.test_client()

    def login(self, email="demo@playpulse.in", password="Demo@1234"):
        return self.c.post("/api/auth/login", json={"email": email, "password": password})

    def free_hour(self, venue_id, sport, day=TOMORROW):
        venue = services.get_venue(venue_id)
        grid = services.slot_grid(venue, sport, slots.parse_date(day))
        return next(s["hour"] for s in grid if s["status"] in ("open", "last"))

    # ---------- pages ----------
    def test_pages_load(self):
        for url in ["/", "/venues", "/venues/1", "/venues/1/book", "/games", "/login",
                    "/signup", "/insights", "/developers", "/venues/1/group-booking"]:
            self.assertEqual(self.c.get(url).status_code, 200, url)

    def test_unknown_venue_is_404(self):
        self.assertEqual(self.c.get("/venues/999").status_code, 404)
        self.assertEqual(self.c.get("/api/venues/999").status_code, 404)

    # ---------- validation (regex) ----------
    def test_signup_rejects_weak_password(self):
        r = self.c.post("/api/auth/signup", json={
            "name": "Test User", "email": "t@x.com", "phone": "9876500000", "skill": "Beginner",
            "favourite_sport": "tennis", "password": "weakpass", "confirm": "weakpass"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("uppercase", r.get_json()["error"])

    def test_signup_rejects_bad_phone(self):
        r = self.c.post("/api/auth/signup", json={
            "name": "Test User", "email": "p@x.com", "phone": "12345", "skill": "Beginner",
            "favourite_sport": "tennis", "password": "Strong@123", "confirm": "Strong@123"})
        self.assertEqual(r.status_code, 400)

    def test_signup_and_login(self):
        r = self.c.post("/api/auth/signup", json={
            "name": "asha verma", "email": "asha@x.com", "phone": "9876511111", "skill": "Beginner",
            "favourite_sport": "badminton", "password": "Strong@123", "confirm": "Strong@123"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["user"]["name"], "Asha Verma")      # title-cased
        self.assertNotIn("password_hash", r.get_json()["user"])            # never leaked
        self.assertEqual(self.c.get("/api/auth/me").get_json()["email"], "asha@x.com")
        dup = self.c.post("/api/auth/signup", json={
            "name": "Asha V", "email": "asha@x.com", "phone": "9876511112", "skill": "Beginner",
            "favourite_sport": "badminton", "password": "Strong@123", "confirm": "Strong@123"})
        self.assertEqual(dup.status_code, 400)

    def test_wrong_password(self):
        self.assertEqual(self.login(password="Wrong@123").status_code, 401)

    def test_api_requires_login(self):
        self.assertEqual(self.c.get("/api/bookings").status_code, 401)

    # ---------- bookings ----------
    def test_booking_flow_and_cancel(self):
        self.login()
        hour = self.free_hour(1, "badminton")
        r = self.c.post("/api/bookings", json={"venue_id": 1, "sport": "badminton",
                                               "date": TOMORROW, "hour": hour, "duration": 1})
        self.assertEqual(r.status_code, 201, r.get_json())
        bid = r.get_json()["id"]
        # same person, same hour -> conflict
        r2 = self.c.post("/api/bookings", json={"venue_id": 1, "sport": "badminton",
                                                "date": TOMORROW, "hour": hour})
        self.assertEqual(r2.status_code, 409)
        # appears in my bookings and in the CSV export
        upcoming = self.c.get("/api/bookings").get_json()["upcoming"]
        self.assertIn(bid, [b["id"] for b in upcoming])
        self.assertIn(bid, self.c.get("/my-bookings.csv").get_data(as_text=True))
        # cancel with DELETE
        r3 = self.c.delete(f"/api/bookings/{bid}")
        self.assertEqual(r3.get_json()["status"], "cancelled")
        self.assertEqual(self.c.delete(f"/api/bookings/{bid}").status_code, 409)   # already cancelled

    def test_slot_becomes_full(self):
        """Venue 6 has ONE cricket court: second booking of the same hour must fail."""
        hour = self.free_hour(6, "cricket")
        self.login("riya@playpulse.in")
        self.assertEqual(self.c.post("/api/bookings", json={"venue_id": 6, "sport": "cricket",
                         "date": TOMORROW, "hour": hour}).status_code, 201)
        self.login("arjun@playpulse.in")
        r = self.c.post("/api/bookings", json={"venue_id": 6, "sport": "cricket", "date": TOMORROW, "hour": hour})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["type"], "SlotUnavailableError")

    def test_cannot_book_past_or_far_future(self):
        self.login()
        past = (date.today() - timedelta(days=1)).isoformat()
        far = (date.today() + timedelta(days=40)).isoformat()
        for d in (past, far, "2026-02-31", "tomorrow"):
            r = self.c.post("/api/bookings", json={"venue_id": 1, "sport": "badminton", "date": d, "hour": 10})
            self.assertEqual(r.status_code, 400, d)

    def test_cannot_cancel_others_booking(self):
        self.login()
        hour = self.free_hour(5, "table_tennis")
        bid = self.c.post("/api/bookings", json={"venue_id": 5, "sport": "table_tennis",
                          "date": TOMORROW, "hour": hour}).get_json()["id"]
        self.login("kabir@playpulse.in")
        self.assertEqual(self.c.delete(f"/api/bookings/{bid}").status_code, 403)

    def test_html_form_redirects(self):
        """An HTML form post gets a redirect to the ticket page, not JSON."""
        self.login()
        hour = self.free_hour(3, "pickleball")
        r = self.c.post("/api/bookings", data={"venue_id": 3, "sport": "pickleball",
                        "date": TOMORROW, "hour": hour, "duration": 1})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/bookings/PP", r.headers["Location"])

    # ---------- games ----------
    def test_host_join_full_leave(self):
        self.login("neha@playpulse.in")
        day = (date.today() + timedelta(days=2)).isoformat()
        hour = self.free_hour(3, "tennis", day)
        r = self.c.post("/api/games", json={"venue_id": 3, "sport": "tennis", "date": day,
                                            "hour": hour, "skill": "Intermediate", "total_spots": 2})
        self.assertEqual(r.status_code, 201, r.get_json())
        gid = r.get_json()["id"]
        self.login()                                                   # demo joins -> game full
        self.assertEqual(self.c.post(f"/api/games/{gid}/join").status_code, 200)
        self.assertEqual(self.c.post(f"/api/games/{gid}/join").status_code, 400)   # already joined
        self.login("kabir@playpulse.in")
        r = self.c.post(f"/api/games/{gid}/join")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["type"], "GameFullError")
        self.login()
        self.assertEqual(self.c.post(f"/api/games/{gid}/leave").get_json()["spots_left"], 1)

    def test_game_needs_valid_sport_for_venue(self):
        self.login()
        r = self.c.post("/api/games", json={"venue_id": 4, "sport": "swimming", "date": TOMORROW,
                                            "hour": 19, "skill": "Beginner", "total_spots": 4})
        self.assertEqual(r.status_code, 400)

    # ---------- reviews & enquiries ----------
    def test_review_updates_rating(self):
        self.login()
        before = self.c.get("/api/venues/8").get_json()["rating_count"]
        r = self.c.post("/api/venues/8/reviews", json={"stars": 5, "text": "Great!"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["rating_count"], before + 1)
        self.assertEqual(self.c.post("/api/venues/8/reviews", json={"stars": 9}).status_code, 400)

    def test_enquiry_saved_to_csv(self):
        r = self.c.post("/api/enquiries", json={"venue_id": 2, "company": "Acme", "contact_name": "Ravi Kumar",
                        "email": "ravi@acme.com", "phone": "9123456789", "sport": "football", "people": 30})
        self.assertEqual(r.status_code, 201)
        rows = storage.read_csv("enquiries.csv")
        self.assertEqual(rows[-1]["company"], "Acme")

    # ---------- API shape ----------
    def test_api_venues_filter_and_sort(self):
        data = self.c.get("/api/venues?sport=badminton&sort=price").get_json()
        prices = [v["min_price"] for v in data["venues"]]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(all("badminton" in v["sports"] for v in data["venues"]))

    def test_insights_builds_charts(self):
        self.assertEqual(self.c.get("/insights").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
