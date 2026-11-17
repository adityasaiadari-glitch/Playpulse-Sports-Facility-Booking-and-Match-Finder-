"""
Business logic  -  the "brain" of PlayPulse.

Flask routes call these functions; these functions use the models and storage.
Errors are signalled by RAISING custom exceptions (see exceptions.py).

Syllabus concepts used here:
  Unit I   : functions, default/keyword arguments, lists, dicts, sets, loops
  Unit II  : objects, lambda, map(), filter(), sorted(key=...), generators
  Unit III : datetime, regex (through validators)
  Unit IV  : JSON storage, CSV, raising & handling exceptions
"""
import math
from datetime import datetime

from . import slots, storage, validators
from .exceptions import (AuthError, CancellationNotAllowedError, GameFullError, NotFoundError,
                         PermissionDenied, SlotUnavailableError, ValidationError)
from .models import SKILLS, SPORTS, Booking, Game, User, Venue

# Areas the user can pick as "my location" -> (latitude, longitude)
AREAS = {
    "Dwarka": (28.5921, 77.0460),
    "Janakpuri": (28.6219, 77.0878),
    "Rajouri Garden": (28.6492, 77.1220),
    "Rohini": (28.7383, 77.0822),
    "Karol Bagh": (28.6519, 77.1909),
    "Saket": (28.5245, 77.2100),
    "Hauz Khas": (28.5494, 77.2001),
    "Vasant Kunj": (28.5200, 77.1590),
}
DEFAULT_AREA = "Dwarka"


# ===========================================================================
# Venues
# ===========================================================================
def distance_km(a, b):
    """Straight-line distance between two (lat, lng) points - the haversine formula."""
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))        # map() applies radians to all 4
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)), 2)       # 6371 km = Earth's radius


def load_venues(area=None):
    venues = [Venue(d) for d in storage.load_json("venues.json", [])]
    origin = AREAS.get(area or DEFAULT_AREA, AREAS[DEFAULT_AREA])
    for v in venues:
        v.distance_km = distance_km(origin, (v.lat, v.lng))
    return venues


def get_venue(venue_id, area=None):
    for v in load_venues(area):
        if v.id == int(venue_id):
            return v
    raise NotFoundError(f"No venue with id {venue_id}")


def save_venue(venue):
    data = storage.load_json("venues.json", [])
    for i, d in enumerate(data):
        if d["id"] == venue.id:
            data[i] = venue.to_dict()
    storage.save_json("venues.json", data)


def search_venues(sport=None, area=None, query=None, sort="recommended"):
    """Filter + sort venues. Uses filter() with lambdas and sorted() with key functions."""
    venues = load_venues(area)
    if sport:
        venues = list(filter(lambda v: sport in v.sports, venues))
    if query:
        q = query.lower().strip()
        venues = [v for v in venues if q in v.name.lower() or q in v.area.lower()]

    sort_keys = {
        "distance": lambda v: v.distance_km,
        "rating": lambda v: -v.rating,              # minus sign -> highest first
        "price": lambda v: v.min_price,
        # recommended: featured first, then good rating, then close by
        "recommended": lambda v: (not v.featured, -v.rating, v.distance_km),
    }
    return sorted(venues, key=sort_keys.get(sort, sort_keys["recommended"]))


def rate_venue(user, venue_id, stars, text):
    try:
        stars = int(stars)
    except (TypeError, ValueError):
        raise ValidationError("Rating: choose 1 to 5 stars")
    if not 1 <= stars <= 5:
        raise ValidationError("Rating: choose 1 to 5 stars")
    text = (text or "").strip()[:300]
    venue = get_venue(venue_id)
    # one review per person: replace an older review by the same user
    venue.reviews = [r for r in venue.reviews if r["name"] != user.name]
    venue.reviews.append({"name": user.name, "stars": stars, "text": text,
                          "date": slots.today().isoformat()})
    save_venue(venue)
    return venue


# ===========================================================================
# Slots & bookings
# ===========================================================================
def load_bookings():
    return [Booking.from_dict(d) for d in storage.load_json("bookings.json", [])]


def save_bookings(bookings):
    storage.save_json("bookings.json", [b.to_dict() for b in bookings])


def courts_taken(bookings, venue_id, sport, date_str, hour):
    """How many courts are already booked for one venue/sport/date/hour."""
    return sum(1 for b in bookings
               if b.status == "confirmed" and b.venue_id == venue_id and b.sport == sport
               and b.date == date_str and hour in b.hours())


def slot_grid(venue, sport, d):
    """Status of every hour of the day for one sport at one venue."""
    if sport not in venue.sports:
        raise ValidationError(f"{venue.name} does not offer {sport}")
    bookings = load_bookings()
    total = venue.sports[sport]["courts"]
    price = venue.price_for(sport, d)
    grid = []
    for hour in slots.hour_slots(venue.opens, venue.closes):        # generator!
        left = total - courts_taken(bookings, venue.id, sport, d.isoformat(), hour)
        if slots.is_past(d, hour):
            status = "past"
        elif left <= 0:
            status = "full"
        elif left == 1 and total > 1:
            status = "last"
        else:
            status = "open"
        grid.append({"hour": hour, "label": slots.hour_label(hour), "status": status,
                     "courts_left": max(left, 0), "price": price})
    return grid


def next_booking_id(bookings):
    numbers = [int(b.id[2:]) for b in bookings if b.id.startswith("PP")]
    return f"PP{max(numbers, default=0) + 1:05d}"


def create_booking(user, venue_id, sport, date_str, hour, duration=1, game_id=None):
    """Book `duration` consecutive hours. Raises an exception if anything is wrong."""
    venue = get_venue(venue_id)
    if sport not in venue.sports:
        raise ValidationError("Choose a sport offered at this venue")
    d = slots.check_bookable_date(slots.parse_date(date_str))
    try:
        hour, duration = int(hour), int(duration)
    except (TypeError, ValueError):
        raise ValidationError("Pick a time slot")
    if duration not in (1, 2, 3):
        raise ValidationError("Duration must be 1, 2 or 3 hours")
    if hour < venue.opens or hour + duration > venue.closes:
        raise ValidationError(f"{venue.name} is open {venue.timing()}")
    if slots.is_past(d, hour):
        raise ValidationError("That time has already passed - pick a later slot")

    bookings = load_bookings()
    courts = venue.sports[sport]["courts"]
    for h in range(hour, hour + duration):
        if courts_taken(bookings, venue.id, sport, d.isoformat(), h) >= courts:
            raise SlotUnavailableError(f"{slots.hour_label(h)} is fully booked for {SPORTS[sport][0]}")
        if any(b.user_email == user.email and b.status == "confirmed" and b.date == d.isoformat()
               and h in b.hours() for b in bookings):
            raise SlotUnavailableError(f"You already have a booking at {slots.hour_label(h)} that day")

    booking = Booking(next_booking_id(bookings), user.email, venue.id, sport, d.isoformat(), hour,
                      duration, venue.price_for(sport, d) * duration,
                      created_at=datetime.now().isoformat(timespec="seconds"), game_id=game_id)
    bookings.append(booking)
    save_bookings(bookings)
    return booking


def get_booking(booking_id):
    for b in load_bookings():
        if b.id == booking_id:
            return b
    raise NotFoundError(f"No booking {booking_id}")


def user_bookings(email):
    mine = [b for b in load_bookings() if b.user_email == email]
    upcoming = sorted(b for b in mine if b.is_upcoming())                 # uses Booking.__lt__
    past = sorted((b for b in mine if not b.is_upcoming()), reverse=True)
    return upcoming, past


def cancel_booking(user, booking_id):
    bookings = load_bookings()
    booking = next((b for b in bookings if b.id == booking_id), None)
    if booking is None:
        raise NotFoundError(f"No booking {booking_id}")
    if booking.user_email != user.email:
        raise PermissionDenied("You can only cancel your own bookings")
    if booking.status != "confirmed":
        raise CancellationNotAllowedError("This booking is already cancelled")
    if not booking.cancellable():
        raise CancellationNotAllowedError(
            f"Free cancellation closes {slots.CANCEL_HOURS_BEFORE} hours before the start time")
    booking.status = "cancelled"
    save_bookings(bookings)
    if booking.game_id:                         # cancelling the court cancels the match too
        games = load_games()
        for g in games:
            if g.id == booking.game_id:
                g.status = "cancelled"
        save_games(games)
    return booking


def waiting_interest(venue_id, sport, date_str, hour):
    """Small 'social proof' number shown when someone is about to cancel:
    how many other confirmed bookings exist for that venue & sport that day."""
    return sum(1 for b in load_bookings() if b.venue_id == venue_id and b.sport == sport
               and b.date == date_str and b.status == "confirmed" and b.hour != hour)


# ===========================================================================
# Users
# ===========================================================================
def load_users():
    return [User.from_dict(d) for d in storage.load_json("users.json", [])]


def get_user(email):
    for u in load_users():
        if u.email == (email or "").lower():
            return u
    return None


def register(name, email, phone, skill, favourite_sport, password, confirm):
    name = validators.validate_name(name)
    email = validators.validate_email(email)
    phone = validators.validate_phone(phone)
    validators.validate_password(password)
    if password != confirm:
        raise ValidationError("Passwords do not match")
    if skill not in SKILLS:
        raise ValidationError("Choose your skill level")
    if favourite_sport not in SPORTS:
        raise ValidationError("Choose your favourite sport")
    users = load_users()
    if any(u.email == email for u in users):
        raise ValidationError("An account with this email already exists - try logging in")
    user = User.create(name.title(), email, phone, skill, favourite_sport, password)
    users.append(user)
    storage.save_json("users.json", [u.to_dict() for u in users])
    return user


def login(email, password):
    user = get_user((email or "").strip())
    if user is None or not user.check_password(password or ""):
        raise AuthError("Incorrect email or password")
    return user


# ===========================================================================
# Games (Match Finder)
# ===========================================================================
def load_games():
    return [Game.from_dict(d) for d in storage.load_json("games.json", [])]


def save_games(games):
    storage.save_json("games.json", [g.to_dict() for g in games])


def get_game(game_id):
    for g in load_games():
        if g.id == game_id:
            return g
    raise NotFoundError(f"No game {game_id}")


def list_games(sport=None, skill=None, date_str=None, include_full=True):
    games = [g for g in load_games() if g.is_upcoming()]
    if sport:
        games = [g for g in games if g.sport == sport]
    if skill:
        games = [g for g in games if g.skill == skill]
    if date_str:
        games = [g for g in games if g.date == date_str]
    if not include_full:
        games = [g for g in games if not g.is_full()]
    return sorted(games)                                      # uses Game.__lt__


def recommended_games(user, limit=3):
    """Open games matching the user's favourite sport or skill level that they haven't joined."""
    candidates = [g for g in list_games(include_full=False) if not g.has_player(user.email)]
    score = lambda g: (g.sport != user.favourite_sport, g.skill != user.skill, g.date, g.hour)
    return sorted(candidates, key=score)[:limit]


def create_game(user, venue_id, sport, date_str, hour, skill, total_spots, notes=""):
    if skill not in SKILLS:
        raise ValidationError("Choose a skill level")
    try:
        total_spots = int(total_spots)
    except (TypeError, ValueError):
        raise ValidationError("Enter the total number of players")
    if not 2 <= total_spots <= 22:
        raise ValidationError("A game needs between 2 and 22 players")
    games = load_games()
    game_id = f"G{max([int(g.id[1:]) for g in games], default=0) + 1:04d}"
    # hosting a game books the court for the host (both features work together)
    booking = create_booking(user, venue_id, sport, date_str, hour, 1, game_id=game_id)
    game = Game(game_id, user.email, sport, int(venue_id), booking.date, booking.hour, skill,
                total_spots, round(booking.amount / total_spots), (notes or "").strip()[:200],
                [{"email": user.email, "name": user.name}], booking.id)
    games.append(game)
    save_games(games)
    return game


def join_game(user, game_id):
    games = load_games()
    game = next((g for g in games if g.id == game_id), None)
    if game is None:
        raise NotFoundError(f"No game {game_id}")
    if not game.is_upcoming():
        raise ValidationError("This game is no longer open")
    if game.has_player(user.email):
        raise ValidationError("You have already joined this game")
    if game.is_full():
        raise GameFullError("Sorry, this game is full")
    game.players.append({"email": user.email, "name": user.name})
    save_games(games)
    return game


def leave_game(user, game_id):
    games = load_games()
    game = next((g for g in games if g.id == game_id), None)
    if game is None:
        raise NotFoundError(f"No game {game_id}")
    if game.host_email == user.email:
        raise ValidationError("You are the host - cancel the booking to cancel the game")
    if not game.has_player(user.email):
        raise ValidationError("You are not part of this game")
    game.players = [p for p in game.players if p["email"] != user.email]
    save_games(games)
    return game


def user_games(email):
    return [g for g in list_games() if g.has_player(email)]


# ===========================================================================
# Corporate / bulk enquiries (saved to a CSV file)
# ===========================================================================
ENQUIRY_FIELDS = ["received", "venue_id", "venue", "company", "contact_name", "email", "phone",
                  "sport", "people", "message"]


def save_enquiry(venue_id, company, contact_name, email, phone, sport, people, message):
    venue = get_venue(venue_id)
    company = (company or "").strip()
    if len(company) < 2:
        raise ValidationError("Company / group name is required")
    row = {
        "received": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "venue_id": venue.id, "venue": venue.name, "company": company,
        "contact_name": validators.validate_name(contact_name),
        "email": validators.validate_email(email),
        "phone": validators.validate_phone(phone),
        "sport": sport if sport in venue.sports else "any",
        "people": people, "message": (message or "").strip()[:500],
    }
    try:
        if not 10 <= int(people) <= 500:
            raise ValidationError("Group size must be between 10 and 500")
    except ValueError:
        raise ValidationError("Group size must be a number")
    storage.append_csv("enquiries.csv", ENQUIRY_FIELDS, row)
    return row


# ===========================================================================
# Small numbers for the home page
# ===========================================================================
def site_stats():
    users = storage.load_json("users.json", [])
    bookings = storage.load_json("bookings.json", [])
    return {
        "venues": len(storage.load_json("venues.json", [])),
        "players": len(users),
        "bookings": sum(1 for b in bookings if b["status"] == "confirmed"),
        "sports": len({s for v in load_venues() for s in v.sports}),     # a SET removes duplicates
        "open_games": len(list_games(include_full=False)),
    }
