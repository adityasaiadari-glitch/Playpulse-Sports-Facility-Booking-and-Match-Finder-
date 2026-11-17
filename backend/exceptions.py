"""
Custom exceptions  (Unit IV: Raising custom exceptions)

Every error our app can raise inherits from PlayPulseError, so app.py can
catch them all in ONE place (an error handler) - just like catching a parent
class in the exception hierarchy also catches its children.

Each class carries an HTTP status code that the API sends back.
"""


class PlayPulseError(Exception):
    """Parent of all app errors."""
    status = 400                      # HTTP 400 = Bad Request (default)

    def __init__(self, message):
        super().__init__(message)     # store the message in Exception
        self.message = message


class ValidationError(PlayPulseError):
    """User typed something invalid (bad email, weak password...)."""
    status = 400


class AuthError(PlayPulseError):
    """Wrong login details or not logged in."""
    status = 401                      # 401 = Unauthorized


class PermissionDenied(PlayPulseError):
    """Logged in, but not allowed to do this (e.g. cancel someone else's booking)."""
    status = 403                      # 403 = Forbidden


class NotFoundError(PlayPulseError):
    """Venue / booking / game id does not exist."""
    status = 404


class SlotUnavailableError(PlayPulseError):
    """All courts are already booked for that time."""
    status = 409                      # 409 = Conflict


class GameFullError(PlayPulseError):
    """No spots left in a match."""
    status = 409


class CancellationNotAllowedError(PlayPulseError):
    """Too late to cancel (less than 2 hours before start) or already cancelled."""
    status = 409
