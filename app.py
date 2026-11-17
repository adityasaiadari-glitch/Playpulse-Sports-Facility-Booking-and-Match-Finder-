"""
PlayPulse  -  Sports Facility Booking & Match Finder
CP Lab Mini Project (Flask)

HOW THE PIECES FIT
    Browser (HTML pages in templates/)
        |  GET pages  /  POST forms
        v
    app.py  (this file)
        - PAGE routes   -> render HTML templates
        - API  routes   -> /api/...  return JSON (GET, POST, DELETE)
        |
        v
    backend/services.py -> backend/models.py -> data/*.json

The HTML forms submit directly to the /api/... routes.
Each API route answers in two ways:
    * JSON client (Postman, curl, JS)  -> JSON response + status code
    * HTML form from our own pages     -> redirect to the right page + flash message
So the frontend is integrated with the backend THROUGH the API.

Run:   pip install -r requirements.txt
       python app.py      ->  open http://127.0.0.1:5000
Demo login:  demo@playpulse.in  /  Demo@1234
"""
import csv
import io
import os
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, Response, flash, jsonify, redirect, render_template, request, session,
                   url_for)

from backend import analytics, services, slots, storage
from backend.exceptions import AuthError, NotFoundError, PermissionDenied, PlayPulseError
from backend.models import SKILLS, SPORTS
from backend.validators import HTML_PATTERNS

app = Flask(__name__)
app.secret_key = os.environ.get("PLAYPULSE_SECRET", "change-this-secret-in-production")
app.permanent_session_lifetime = timedelta(days=7)

storage.ensure_data()            # create demo users/bookings/games on first run


# ===========================================================================
# Helpers
# ===========================================================================
def wants_json():
    """True when the caller expects JSON (API client) instead of an HTML page."""
    if request.is_json or request.args.get("format") == "json":
        return True
    if request.path.startswith("/api"):
        # HTML forms always send one of these content types; anything else is an API client
        return request.mimetype not in ("application/x-www-form-urlencoded", "multipart/form-data")
    return False


def form_data():
    """Read input from either a JSON body or an HTML form."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def current_user():
    email = session.get("user")
    return services.get_user(email) if email else None


def current_area():
    return session.get("area", services.DEFAULT_AREA)


def login_required(view):
    """DECORATOR (Unit II): wraps a route so only logged-in users can reach it."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            raise AuthError("Please log in first")
        return view(*args, **kwargs)
    return wrapper


def respond(payload, status=200, page=None, message=None):
    """Send JSON to API clients, or flash + redirect for HTML forms."""
    if wants_json():
        return jsonify(payload), status
    if message:
        flash(message, "success")
    return redirect(page or url_for("home"))


# ===========================================================================
# Error handling  (Unit IV) - ONE place catches every custom exception
# ===========================================================================
@app.errorhandler(PlayPulseError)
def handle_app_error(err):
    if wants_json():
        return jsonify({"error": err.message, "type": type(err).__name__}), err.status
    flash(err.message, "error")
    if isinstance(err, AuthError) and current_user() is None:
        if request.method == "GET":
            back = request.full_path.rstrip("?")
        else:                                   # a form was posted: go back to the page it came from
            ref = urlparse(request.referrer or "/")
            back = ref.path + ("?" + ref.query if ref.query else "")
        return redirect(url_for("login_page", next=back))
    if isinstance(err, NotFoundError) and request.method == "GET":
        return render_template("404.html", message=err.message), 404
    return redirect(request.referrer or url_for("home"))


@app.errorhandler(404)
def page_not_found(err):
    if wants_json():
        return jsonify({"error": "Not found"}), 404
    return render_template("404.html", message="We couldn't find that page."), 404


@app.errorhandler(405)
def method_not_allowed(err):
    return jsonify({"error": "Method not allowed"}), 405


# ===========================================================================
# Template helpers (available inside every HTML page)
# ===========================================================================
@app.context_processor
def inject_globals():
    return {
        "user": current_user(), "area": current_area(), "AREAS": services.AREAS,
        "SPORTS": SPORTS, "SKILLS": SKILLS, "patterns": HTML_PATTERNS, "slots": slots,
        "today_iso": slots.today().isoformat(),
        "max_iso": (slots.today() + timedelta(days=slots.MAX_DAYS_AHEAD)).isoformat(),
    }


@app.template_filter("inr")
def inr(amount):
    return f"₹{int(amount):,}"


@app.template_filter("pdate")
def pdate(date_str):
    return slots.pretty_date(slots.parse_date(date_str))


@app.template_filter("hour")
def hour_filter(hour):
    return slots.hour_label(int(hour))


# ===========================================================================
# PAGE ROUTES (return HTML)
# ===========================================================================
@app.route("/")
def home():
    venues = services.search_venues(area=current_area(), sort="recommended")
    u = current_user()
    games = services.recommended_games(u, 3) if u else services.list_games(include_full=False)[:3]
    counts = {k: sum(1 for v in services.load_venues() if k in v.sports) for k in SPORTS}
    return render_template("home.html", venues=venues[:4], nearby=sorted(venues, key=lambda v: v.distance_km)[:4],
                           games=games, venue_map={v.id: v for v in venues}, counts=counts,
                           stats=services.site_stats())


@app.route("/set-area", methods=["POST"])
def set_area():
    area = request.form.get("area")
    if area in services.AREAS:
        session["area"] = area
        flash(f"Showing distances from {area}", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/venues")
def venues_page():
    sport = request.args.get("sport") or None
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "recommended")
    if sport and sport not in SPORTS:
        sport = None
    venues = services.search_venues(sport, current_area(), query, sort)
    return render_template("venues.html", venues=venues, sport=sport, q=query, sort=sort)


@app.route("/venues/<int:venue_id>")
def venue_page(venue_id):
    venue = services.get_venue(venue_id, current_area())
    games = [g for g in services.list_games() if g.venue_id == venue.id]
    u = current_user()
    my_review = next((r for r in venue.reviews if u and r["name"] == u.name), None)
    return render_template("venue.html", venue=venue, games=games, my_review=my_review)


@app.route("/venues/<int:venue_id>/book")
def book_page(venue_id):
    venue = services.get_venue(venue_id, current_area())
    sport = request.args.get("sport") or venue.main_sport()
    if sport not in venue.sports:
        sport = venue.main_sport()
    try:
        day = slots.check_bookable_date(slots.parse_date(request.args.get("date") or slots.today().isoformat()))
    except PlayPulseError as err:
        flash(err.message, "error")
        day = slots.today()
    grid = services.slot_grid(venue, sport, day)
    return render_template("book.html", venue=venue, sport=sport, day=day, grid=grid,
                           days=slots.next_days(7), price=venue.price_for(sport, day),
                           any_open=any(s["status"] in ("open", "last") for s in grid))


@app.route("/bookings/<booking_id>")
@login_required
def booking_page(booking_id):
    booking = services.get_booking(booking_id)
    if booking.user_email != current_user().email:
        raise PermissionDenied("That booking belongs to someone else")
    return render_template("booking_done.html", b=booking, venue=services.get_venue(booking.venue_id))


@app.route("/my-bookings")
@login_required
def my_bookings_page():
    u = current_user()
    upcoming, past = services.user_bookings(u.email)
    venue_map = {v.id: v for v in services.load_venues(current_area())}
    interest = {b.id: services.waiting_interest(b.venue_id, b.sport, b.date, b.hour) for b in upcoming}
    return render_template("my_bookings.html", upcoming=upcoming, past=past, venue_map=venue_map,
                           games=services.user_games(u.email), interest=interest)


@app.route("/my-bookings.csv")
@login_required
def my_bookings_csv():
    """Download your bookings as a CSV file (Unit IV: Working with CSV files)."""
    upcoming, past = services.user_bookings(current_user().email)
    venues = {v.id: v.name for v in services.load_venues()}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Booking ID", "Venue", "Sport", "Date", "Start", "Hours", "Amount", "Status"])
    for b in upcoming + past:
        writer.writerow([b.id, venues.get(b.venue_id), SPORTS[b.sport][0], b.date,
                         slots.hour_label(b.hour), b.duration, b.amount, b.status])
    return Response(buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=my_playpulse_bookings.csv"})


@app.route("/games")
def games_page():
    sport = request.args.get("sport") or None
    skill = request.args.get("skill") or None
    date_str = request.args.get("date") or None
    games = services.list_games(sport, skill, date_str)
    u = current_user()
    return render_template("games.html", games=games, sport=sport, skill=skill, date=date_str,
                           venue_map={v.id: v for v in services.load_venues(current_area())},
                           recommended=services.recommended_games(u) if u else [],
                           days=slots.next_days(7))


@app.route("/games/new")
@login_required
def host_game_page():
    return render_template("host_game.html", venues=services.search_venues(area=current_area()),
                           prefill=request.args)


@app.route("/games/<game_id>")
def game_page(game_id):
    game = services.get_game(game_id)
    u = current_user()
    return render_template("game.html", g=game, venue=services.get_venue(game.venue_id, current_area()),
                           joined=bool(u and game.has_player(u.email)),
                           is_host=bool(u and game.host_email == u.email))


@app.route("/venues/<int:venue_id>/group-booking")
def corporate_page(venue_id):
    return render_template("corporate.html", venue=services.get_venue(venue_id, current_area()))


@app.route("/login")
def login_page():
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/signup")
def signup_page():
    return render_template("signup.html")


@app.route("/insights")
def insights_page():
    return render_template("insights.html", data=analytics.build_insights())


@app.route("/developers")
def developers_page():
    return render_template("developers.html")


# ===========================================================================
# API ROUTES  (/api/...)  -  JSON in, JSON out
# ===========================================================================
@app.route("/api")
def api_index():
    return jsonify({
        "name": "PlayPulse API", "version": "1.0",
        "endpoints": [
            "GET    /api/venues?sport=&q=&sort=recommended|distance|rating|price",
            "GET    /api/venues/<id>",
            "GET    /api/venues/<id>/slots?sport=&date=YYYY-MM-DD",
            "POST   /api/venues/<id>/reviews      {stars, text}",
            "POST   /api/auth/signup              {name, email, phone, skill, favourite_sport, password, confirm}",
            "POST   /api/auth/login               {email, password}",
            "POST   /api/auth/logout",
            "GET    /api/auth/me",
            "GET    /api/bookings",
            "POST   /api/bookings                 {venue_id, sport, date, hour, duration}",
            "GET    /api/bookings/<id>",
            "DELETE /api/bookings/<id>            (also POST /api/bookings/<id>/cancel)",
            "GET    /api/games?sport=&skill=&date=",
            "POST   /api/games                    {venue_id, sport, date, hour, skill, total_spots, notes}",
            "GET    /api/games/<id>",
            "POST   /api/games/<id>/join",
            "POST   /api/games/<id>/leave",
            "POST   /api/enquiries                {venue_id, company, contact_name, email, phone, sport, people, message}",
        ],
    })


# ----- venues -----
@app.route("/api/venues", methods=["GET"])
def api_venues():
    venues = services.search_venues(request.args.get("sport"), current_area(),
                                    request.args.get("q"), request.args.get("sort", "recommended"))
    return jsonify({"count": len(venues), "area": current_area(),
                    "venues": [v.public_dict() for v in venues]})


@app.route("/api/venues/<int:venue_id>", methods=["GET"])
def api_venue(venue_id):
    return jsonify(services.get_venue(venue_id, current_area()).public_dict())


@app.route("/api/venues/<int:venue_id>/slots", methods=["GET"])
def api_slots(venue_id):
    venue = services.get_venue(venue_id)
    sport = request.args.get("sport") or venue.main_sport()
    day = slots.parse_date(request.args.get("date") or slots.today().isoformat())
    return jsonify({"venue_id": venue.id, "sport": sport, "date": day.isoformat(),
                    "slots": services.slot_grid(venue, sport, day)})


@app.route("/api/venues/<int:venue_id>/reviews", methods=["POST"])
@login_required
def api_review(venue_id):
    data = form_data()
    venue = services.rate_venue(current_user(), venue_id, data.get("stars"), data.get("text"))
    return respond({"rating": venue.rating, "rating_count": venue.rating_count}, 201,
                   url_for("venue_page", venue_id=venue_id) + "#reviews", "Thanks for rating this venue!")


# ----- auth -----
@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    d = form_data()
    user = services.register(d.get("name"), d.get("email"), d.get("phone"), d.get("skill"),
                             d.get("favourite_sport"), d.get("password"), d.get("confirm"))
    session.permanent = True
    session["user"] = user.email
    return respond({"user": user.public_dict()}, 201, url_for("home"),
                   f"Welcome to PlayPulse, {user.first_name}! 🎉")


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    d = form_data()
    user = services.login(d.get("email"), d.get("password"))
    session.permanent = True
    session["user"] = user.email
    nxt = d.get("next") or ""
    page = nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("home")   # only local redirects
    return respond({"user": user.public_dict()}, 200, page, f"Welcome back, {user.first_name}!")


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    return respond({"ok": True}, 200, url_for("home"), "You have been logged out")


@app.route("/api/auth/me", methods=["GET"])
@login_required
def api_me():
    return jsonify(current_user().public_dict())


# ----- bookings -----
@app.route("/api/bookings", methods=["GET", "POST"])
@login_required
def api_bookings():
    u = current_user()
    if request.method == "GET":
        upcoming, past = services.user_bookings(u.email)
        return jsonify({"upcoming": [b.to_dict() for b in upcoming], "past": [b.to_dict() for b in past]})
    d = form_data()
    b = services.create_booking(u, d.get("venue_id"), d.get("sport"), d.get("date"),
                                d.get("hour"), d.get("duration", 1))
    return respond(b.to_dict(), 201, url_for("booking_page", booking_id=b.id), "Booking confirmed! ✅")


@app.route("/api/bookings/<booking_id>", methods=["GET", "DELETE"])
@login_required
def api_booking(booking_id):
    if request.method == "DELETE":
        return api_cancel(booking_id)
    b = services.get_booking(booking_id)
    if b.user_email != current_user().email:
        raise PermissionDenied("That booking belongs to someone else")
    return jsonify(b.to_dict())


@app.route("/api/bookings/<booking_id>/cancel", methods=["POST"])
@login_required
def api_cancel(booking_id):
    b = services.cancel_booking(current_user(), booking_id)
    return respond(b.to_dict(), 200, url_for("my_bookings_page"), f"Booking {b.id} cancelled")


# ----- games -----
@app.route("/api/games", methods=["GET", "POST"])
def api_games():
    if request.method == "GET":
        games = services.list_games(request.args.get("sport"), request.args.get("skill"),
                                    request.args.get("date"))
        return jsonify({"count": len(games), "games": [g.public_dict() for g in games]})
    u = current_user()
    if u is None:
        raise AuthError("Please log in to host a game")
    d = form_data()
    g = services.create_game(u, d.get("venue_id"), d.get("sport"), d.get("date"), d.get("hour"),
                             d.get("skill"), d.get("total_spots"), d.get("notes"))
    return respond(g.public_dict(), 201, url_for("game_page", game_id=g.id),
                   "Game created and court booked! Share the link with friends.")


@app.route("/api/games/<game_id>", methods=["GET"])
def api_game(game_id):
    return jsonify(services.get_game(game_id).public_dict())


@app.route("/api/games/<game_id>/join", methods=["POST"])
@login_required
def api_join(game_id):
    g = services.join_game(current_user(), game_id)
    return respond(g.public_dict(), 200, url_for("game_page", game_id=g.id), "You're in! See you on court 🙌")


@app.route("/api/games/<game_id>/leave", methods=["POST"])
@login_required
def api_leave(game_id):
    g = services.leave_game(current_user(), game_id)
    return respond(g.public_dict(), 200, url_for("game_page", game_id=g.id), "You left the game")


# ----- group / corporate enquiries -----
@app.route("/api/enquiries", methods=["POST"])
def api_enquiry():
    d = form_data()
    row = services.save_enquiry(d.get("venue_id"), d.get("company"), d.get("contact_name"),
                                d.get("email"), d.get("phone"), d.get("sport"), d.get("people"),
                                d.get("message"))
    return respond(row, 201, url_for("venue_page", venue_id=row["venue_id"]),
                   "Enquiry sent! The venue will contact you within 24 hours.")


if __name__ == "__main__":
    app.run(debug=True)
