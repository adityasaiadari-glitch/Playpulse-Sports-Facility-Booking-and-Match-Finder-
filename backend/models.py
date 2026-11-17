"""
Classes for the app's main objects  (Unit II: Object-Oriented Programming)

Concepts used here:
  - Classes & objects, __init__ and self
  - Inheritance + super():      Facility  ->  Venue
  - Method overriding:          Venue.summary() overrides Facility.summary()
  - Polymorphism:               every class has to_dict(), used the same way
  - Encapsulation:              User keeps the password hash "private" (_password_hash)
  - @property:                  computed attributes like venue.rating
  - Class attribute:            SPORTS (shared by all Venue objects)
  - Operator overloading:       __lt__ lets us sort bookings by start time
  - __str__ / __repr__:         readable printing
"""
from datetime import date

from werkzeug.security import check_password_hash, generate_password_hash

from . import slots

# sport key -> (display name, icon)
SPORTS = {
    "badminton": ("Badminton", "🏸"),
    "football": ("Football", "⚽"),
    "cricket": ("Box Cricket", "🏏"),
    "pickleball": ("Pickleball", "🥎"),
    "tennis": ("Tennis", "🎾"),
    "basketball": ("Basketball", "🏀"),
    "table_tennis": ("Table Tennis", "🏓"),
    "swimming": ("Swimming", "🏊"),
}

SKILLS = ["Beginner", "Intermediate", "Advanced"]


class Facility:
    """General sports facility (parent class)."""

    def __init__(self, id, name, area, address, opens, closes):
        self.id = id
        self.name = name
        self.area = area
        self.address = address
        self.opens = opens            # opening hour (24-hour clock)
        self.closes = closes          # closing hour

    def timing(self):
        return f"{slots.hour_label(self.opens)} – {slots.hour_label(self.closes)}"

    def summary(self):
        return f"{self.name} ({self.area})"

    def __str__(self):
        return self.summary()


class Venue(Facility):
    """A bookable venue with several sports. Inherits from Facility."""

    SPORTS = SPORTS                    # class attribute shared by all venues

    def __init__(self, data):
        super().__init__(data["id"], data["name"], data["area"], data["address"],
                         data["opens"], data["closes"])         # call parent __init__
        self.lat = data["lat"]
        self.lng = data["lng"]
        self.sports = data["sports"]           # {sport: {"courts": 2, "weekday": 400, "weekend": 500}}
        self.amenities = data.get("amenities", [])
        self.about = data.get("about", "")
        self.featured = data.get("featured", False)
        self.surface = data.get("surface", "")
        self.reviews = data.get("reviews", [])  # list of {"name", "stars", "text", "date"}
        self.distance_km = None                 # filled in later by services

    # ----- computed properties -----
    @property
    def rating(self):
        if not self.reviews:
            return 0.0
        return round(sum(r["stars"] for r in self.reviews) / len(self.reviews), 2)

    @property
    def rating_count(self):
        return len(self.reviews)

    @property
    def min_price(self):
        return min(p["weekday"] for p in self.sports.values())

    def price_for(self, sport, d):
        info = self.sports[sport]
        return info["weekend"] if slots.is_weekend(d) else info["weekday"]

    def sport_list(self):
        """[(key, name, icon), ...] for the sports this venue offers."""
        return [(k, SPORTS[k][0], SPORTS[k][1]) for k in self.sports]

    def main_sport(self):
        return next(iter(self.sports))          # first sport key (uses an iterator)

    # ----- method overriding -----
    def summary(self):
        names = ", ".join(SPORTS[s][0] for s in self.sports)
        return f"{self.name} ({self.area}) – {names}"

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "area": self.area, "address": self.address,
            "lat": self.lat, "lng": self.lng, "opens": self.opens, "closes": self.closes,
            "sports": self.sports, "amenities": self.amenities, "about": self.about,
            "featured": self.featured, "surface": self.surface, "reviews": self.reviews,
        }

    def public_dict(self):
        """What the API shows to the outside world."""
        d = self.to_dict()
        d.update(rating=self.rating, rating_count=self.rating_count, min_price=self.min_price,
                 timing=self.timing(), distance_km=self.distance_km)
        return d


class User:
    """A player. The password is never stored in plain text (encapsulation)."""

    def __init__(self, name, email, phone, skill, favourite_sport, password_hash, joined):
        self.name = name
        self.email = email
        self.phone = phone
        self.skill = skill
        self.favourite_sport = favourite_sport
        self._password_hash = password_hash     # "_" = internal, don't touch from outside
        self.joined = joined

    @classmethod
    def create(cls, name, email, phone, skill, favourite_sport, password):
        """Alternative constructor that hashes the password first."""
        return cls(name, email, phone, skill, favourite_sport,
                   generate_password_hash(password), date.today().isoformat())

    def check_password(self, password):
        return check_password_hash(self._password_hash, password)

    @property
    def first_name(self):
        return self.name.split()[0]

    @property
    def initials(self):
        return "".join(part[0] for part in self.name.split()[:2]).upper()

    def to_dict(self):
        return {"name": self.name, "email": self.email, "phone": self.phone, "skill": self.skill,
                "favourite_sport": self.favourite_sport, "password_hash": self._password_hash,
                "joined": self.joined}

    def public_dict(self):
        d = self.to_dict()
        d.pop("password_hash")                  # never send the hash to the browser
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d["email"], d["phone"], d["skill"], d["favourite_sport"],
                   d["password_hash"], d["joined"])


class Booking:
    def __init__(self, id, user_email, venue_id, sport, date_str, hour, duration, amount,
                 status="confirmed", created_at="", game_id=None):
        self.id = id
        self.user_email = user_email
        self.venue_id = venue_id
        self.sport = sport
        self.date = date_str            # stored as "YYYY-MM-DD"
        self.hour = hour
        self.duration = duration
        self.amount = amount
        self.status = status
        self.created_at = created_at
        self.game_id = game_id

    @property
    def day(self):
        return slots.parse_date(self.date)

    def hours(self):
        return list(range(self.hour, self.hour + self.duration))

    def is_upcoming(self):
        return self.status == "confirmed" and not slots.is_past(self.day, self.hour)

    def cancellable(self):
        return self.status == "confirmed" and slots.can_cancel(self.day, self.hour)

    # operator overloading: lets sorted(bookings) order them by date and time
    def __lt__(self, other):
        return (self.date, self.hour) < (other.date, other.hour)

    def __repr__(self):
        return f"Booking({self.id}, {self.sport}, {self.date} {self.hour}:00)"

    def to_dict(self):
        return dict(id=self.id, user_email=self.user_email, venue_id=self.venue_id, sport=self.sport,
                    date=self.date, hour=self.hour, duration=self.duration, amount=self.amount,
                    status=self.status, created_at=self.created_at, game_id=self.game_id)

    @classmethod
    def from_dict(cls, d):
        return cls(d["id"], d["user_email"], d["venue_id"], d["sport"], d["date"], d["hour"],
                   d["duration"], d["amount"], d.get("status", "confirmed"),
                   d.get("created_at", ""), d.get("game_id"))


class Game:
    """An open match that other players can join (the Match Finder)."""

    def __init__(self, id, host_email, sport, venue_id, date_str, hour, skill, total_spots,
                 cost_per_head, notes, players, booking_id=None, status="open"):
        self.id = id
        self.host_email = host_email
        self.sport = sport
        self.venue_id = venue_id
        self.date = date_str
        self.hour = hour
        self.skill = skill
        self.total_spots = total_spots
        self.cost_per_head = cost_per_head
        self.notes = notes
        self.players = players          # list of {"email", "name"}
        self.booking_id = booking_id
        self.status = status            # open / cancelled

    @property
    def day(self):
        return slots.parse_date(self.date)

    @property
    def spots_left(self):
        return self.total_spots - len(self.players)

    def is_full(self):
        return self.spots_left <= 0

    def has_player(self, email):
        return any(p["email"] == email for p in self.players)

    def is_upcoming(self):
        return self.status == "open" and not slots.is_past(self.day, self.hour)

    def __len__(self):                  # len(game) -> number of players joined
        return len(self.players)

    def __lt__(self, other):
        return (self.date, self.hour) < (other.date, other.hour)

    def to_dict(self):
        return dict(id=self.id, host_email=self.host_email, sport=self.sport, venue_id=self.venue_id,
                    date=self.date, hour=self.hour, skill=self.skill, total_spots=self.total_spots,
                    cost_per_head=self.cost_per_head, notes=self.notes, players=self.players,
                    booking_id=self.booking_id, status=self.status)

    def public_dict(self):
        d = self.to_dict()
        d["players"] = [{"name": p["name"]} for p in self.players]   # hide emails
        d.pop("host_email")
        d["spots_left"] = self.spots_left
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d["id"], d["host_email"], d["sport"], d["venue_id"], d["date"], d["hour"],
                   d["skill"], d["total_spots"], d["cost_per_head"], d.get("notes", ""),
                   d["players"], d.get("booking_id"), d.get("status", "open"))
