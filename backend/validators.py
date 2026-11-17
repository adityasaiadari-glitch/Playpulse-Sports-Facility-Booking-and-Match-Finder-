"""
Input validation with regular expressions  (Unit III: Regex)

The SAME rules are used twice:
  1. In the HTML <input pattern="..."> so the browser checks first (frontend)
  2. Here in Python, because a user can bypass the browser (backend)
Rule of thumb: never trust the client - always validate on the server.
"""
import re

from .exceptions import ValidationError

# name: starts with a letter, then letters/spaces, 2-40 characters
NAME_RE = r"[A-Za-z][A-Za-z ]{1,39}"

# simple email: something@something.domain
EMAIL_RE = r"[\w.+-]+@[\w-]+\.[\w.]+"

# Indian mobile number: 10 digits, starting with 6, 7, 8 or 9
PHONE_RE = r"[6-9]\d{9}"

# password: 8-20 chars, at least one lowercase, one uppercase, one digit,
# one special character. (?=...) are LOOKAHEADS - each checks one rule.
PASSWORD_RE = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@#$%^&+=!_*-])[A-Za-z\d@#$%^&+=!_*-]{8,20}"

# date from an <input type="date"> is always YYYY-MM-DD
DATE_RE = r"\d{4}-\d{2}-\d{2}"

# The same patterns, ready to paste into HTML pattern="" attributes
HTML_PATTERNS = {
    "name": NAME_RE,
    "phone": PHONE_RE,
    "password": PASSWORD_RE,
}


def check(pattern, value, field, message):
    """Raise ValidationError unless the WHOLE value matches the pattern."""
    value = (value or "").strip()
    if not re.fullmatch(pattern, value):
        raise ValidationError(f"{field}: {message}")
    return value


def validate_name(name):
    return check(NAME_RE, name, "Name", "use 2-40 letters and spaces only")


def validate_email(email):
    return check(EMAIL_RE, email, "Email", "enter a valid email like you@mail.com").lower()


def validate_phone(phone):
    return check(PHONE_RE, phone, "Phone", "enter a 10-digit mobile number starting with 6-9")


def validate_password(password):
    # do not strip passwords - spaces at the ends would silently change them
    if not re.fullmatch(PASSWORD_RE, password or ""):
        raise ValidationError("Password: " + "; ".join(missing_password_rules(password or "")))
    return password


def missing_password_rules(password):
    """Return a list of the rules the password breaks (helps the user fix it)."""
    problems = []
    if not 8 <= len(password) <= 20:
        problems.append("must be 8-20 characters")
    if not re.search(r"[a-z]", password):
        problems.append("add a lowercase letter")
    if not re.search(r"[A-Z]", password):
        problems.append("add an uppercase letter")
    if not re.search(r"\d", password):
        problems.append("add a digit")
    if not re.search(r"[@#$%^&+=!_*-]", password):
        problems.append("add a special character (@#$%^&+=!_*-)")
    if re.search(r"[^A-Za-z\d@#$%^&+=!_*-]", password):
        problems.append("remove spaces or unsupported characters")
    return problems or ["invalid password"]
